using System.Collections.Concurrent;
using System.Globalization;
using System.Text;

namespace Bridge.Relayer;

public sealed record RuntimeStatus(bool Running, bool Ready, string Profile, string CodeVersion, DateTimeOffset UpdatedUtc,
    string? ErrorCode, IReadOnlyList<NetworkView> Networks, TransferSummary Transfers, Reconciliation Reconciliation);

public sealed class RelayerService(BridgeConfig config, Chain chain, IBridgeStore store, ISigner signer, ILoggerFactory logs) : BackgroundService
{
    private readonly ILogger _logger = logs.CreateLogger<RelayerService>();
    private readonly ConcurrentDictionary<string, long> _errors = new();
    private RuntimeStatus _status = new(true, false, config.Profile, Environment.GetEnvironmentVariable("BRIDGE_CODE_VERSION") ?? "unrecorded",
        DateTimeOffset.UtcNow, "starting", [], new(States.All.ToDictionary(s => s, _ => 0L), 0, 0),
        new("unavailable", null, null, null, null, null, new Dictionary<string, BlockHeader>(), DateTimeOffset.UtcNow, "not_run"));
    public RuntimeStatus Snapshot => Volatile.Read(ref _status);
    public bool Stale => DateTimeOffset.UtcNow - Snapshot.UpdatedUtc > TimeSpan.FromSeconds(Math.Max(15, config.RpcTimeoutSeconds * 4));

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var initialized = false;
        var collector = new Collector(config, chain, store);
        var processor = new TransferProcessor(config, chain, store, signer, new LocalFaults(), logs.CreateLogger<TransferProcessor>());
        var reconciler = new Reconciler(config, chain, store);
        var nextReconciliation = DateTimeOffset.MinValue;
        while (!stoppingToken.IsCancellationRequested)
        {
            var component = "database";
            try
            {
                if (!initialized) { await store.InitializeAsync(config, stoppingToken); initialized = true; }
                component = "identity";
                // Both identities must succeed before collecting or executing either direction.
                await Task.WhenAll(config.Networks.Select(n => chain.ValidateIdentity(config, n, stoppingToken)));
                component = "collector";
                await Task.WhenAll(config.Networks.Select(n => collector.CollectAsync(n, stoppingToken)));
                component = "processor";
                await Task.WhenAll(Enumerable.Range(0, config.Workers).SelectMany(_ => config.Networks.Select(n => processor.ProcessAsync(n, stoppingToken))));
                var reconciliation = Snapshot.Reconciliation;
                if (DateTimeOffset.UtcNow >= nextReconciliation)
                {
                    component = "reconciliation";
                    await using var lease = await store.TryLockAsync(74004, 0, stoppingToken);
                    if (lease is not null) reconciliation = await reconciler.RunAsync(stoppingToken);
                    nextReconciliation = DateTimeOffset.UtcNow.AddSeconds(5);
                }
                component = "status";
                var views = new List<NetworkView>();
                foreach (var network in config.Networks)
                {
                    var checkpoint = await store.CheckpointAsync(network, stoppingToken);
                    views.Add(new(network.Name, network.ChainId, checkpoint.Head, checkpoint.Finalized, checkpoint.NextBlock,
                        checkpoint.LastCollection, (await chain.Balance(network, stoppingToken)).ToString(CultureInfo.InvariantCulture), await chain.Paused(network, stoppingToken)));
                }
                var current = Snapshot;
                Volatile.Write(ref _status, current with { Ready = true, UpdatedUtc = DateTimeOffset.UtcNow, ErrorCode = null,
                    Networks = views, Transfers = await store.SummaryAsync(stoppingToken), Reconciliation = reconciliation });
                if (!current.Ready) _logger.LogInformation("relayer_ready {Profile}", config.Profile);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
            catch (Exception error)
            {
                // Never serialize exception objects or provider messages (which may echo raw tx/credentials).
                var code = error switch { RpcFailure rpc => rpc.Code, ConfigurationException c => c.Message, Npgsql.NpgsqlException => "database_unavailable", _ => "unexpected_component_failure" };
                _errors.AddOrUpdate(component, 1, (_, count) => count + 1);
                var current = Snapshot;
                Volatile.Write(ref _status, current with { Ready = false, UpdatedUtc = DateTimeOffset.UtcNow, ErrorCode = code });
                if (current.Ready || current.ErrorCode != code) _logger.LogWarning("relayer_degraded {Component} {ErrorCode} {ErrorType}", component, code, error.GetType().Name);
            }
            try { await Task.Delay(config.PollMilliseconds, stoppingToken); }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
        }
        Volatile.Write(ref _status, Snapshot with { Running = false, Ready = false, UpdatedUtc = DateTimeOffset.UtcNow, ErrorCode = "stopped" });
    }

    public string Metrics()
    {
        var status = Snapshot;
        var result = new StringBuilder();
        void Metric(string name, object value, string labels = "") => result.Append(name).Append(labels).Append(' ').Append(Convert.ToString(value, CultureInfo.InvariantCulture)).Append('\n');
        Metric("bridge_ready", status.Ready && !Stale ? 1 : 0);
        Metric("bridge_status_updated_timestamp_seconds", status.UpdatedUtc.ToUnixTimeSeconds());
        foreach (var network in status.Networks)
        {
            var labels = "{network=\"" + network.Name + "\"}";
            Metric("bridge_network_info", 1, "{network=\"" + network.Name + "\",chain_id=\"" + network.ChainId.ToString(CultureInfo.InvariantCulture) + "\"}");
            Metric("bridge_last_collection_timestamp_seconds", network.LastCollectionUtc?.ToUnixTimeSeconds() ?? 0, labels);
            Metric("bridge_finalized_lag_blocks", Math.Max(0, network.Finalized - network.NextBlock + 1), labels);
            Metric("bridge_chain_head", network.Head, labels);
            Metric("bridge_chain_finalized", network.Finalized, labels);
            Metric("bridge_gas_balance_wei", network.GasBalanceWei, labels);
            Metric("bridge_paused", network.Paused ? 1 : 0, labels);
        }
        foreach (var state in States.All) Metric("bridge_transfers", status.Transfers.Counts.GetValueOrDefault(state), "{state=\"" + state + "\"}");
        Metric("bridge_oldest_pending_seconds", status.Transfers.OldestPendingSeconds);
        Metric("bridge_attempts_pending", status.Transfers.Attempts);
        foreach (var state in new[] { "balanced", "mismatch", "inconclusive", "unavailable" }) Metric("bridge_reconciliation_state", status.Reconciliation.State == state ? 1 : 0, "{state=\"" + state + "\"}");
        Metric("bridge_reconciliation_updated_timestamp_seconds", status.Reconciliation.UpdatedUtc.ToUnixTimeSeconds());
        foreach (var component in new[] { "identity", "collector", "processor", "reconciliation", "database", "status" }) Metric("bridge_cycle_errors_total", _errors.GetValueOrDefault(component), "{component=\"" + component + "\"}");
        var version = status.CodeVersion.Replace("\\", "\\\\", StringComparison.Ordinal).Replace("\"", "\\\"", StringComparison.Ordinal).Replace("\n", "\\n", StringComparison.Ordinal);
        Metric("bridge_code_info", 1, "{version=\"" + version + "\",profile=\"" + status.Profile + "\"}");
        return result.ToString();
    }
}
