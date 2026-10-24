using System.Text.Json;
using Bridge.Relayer;
using Microsoft.Extensions.Logging.Abstractions;

namespace Bridge.Relayer.Tests;

public sealed class StatusTests
{
    [Fact]
    public async Task LiveSnapshotHasObservedNetworkIdentityAndNoTransactionPayloads()
    {
        var f = new Fixture();
        using var service = new RelayerService(f.Config, f.Chain, f.Store, f.Signer, NullLoggerFactory.Instance);
        await service.StartAsync(default);
        try
        {
            await Until(() => service.Snapshot.Ready);
            Assert.Equal(2, service.Snapshot.Networks.Count);
            Assert.All(service.Snapshot.Networks, n => Assert.NotNull(n.LastCollectionUtc));
            Assert.Contains("profile=\"local-fast\"} 1", service.Metrics());
            Assert.Contains("bridge_network_info{network=\"a\",chain_id=\"31337\"} 1", service.Metrics());
            var json = JsonSerializer.Serialize(service.Snapshot, BridgeConfig.Json);
            Assert.DoesNotContain("signedRaw", json); Assert.DoesNotContain("keyFile", json); Assert.DoesNotContain("password", json);
        }
        finally { await service.StopAsync(default); }
        Assert.False(service.Snapshot.Ready); Assert.False(service.Snapshot.Running);
    }

    [Fact]
    public async Task DegradedRpcIsVisibleAndDoesNotRefreshLastSuccessfulCollection()
    {
        var f = new Fixture();
        using var service = new RelayerService(f.Config, f.Chain, f.Store, f.Signer, NullLoggerFactory.Instance);
        await service.StartAsync(default);
        try
        {
            await Until(() => service.Snapshot.Ready);
            var collected = service.Snapshot.Networks.ToDictionary(n => n.Name, n => n.LastCollectionUtc);
            f.Rpc.Override = (_, _, _) => throw new RpcFailure("rpc_unavailable");
            await Until(() => !service.Snapshot.Ready);
            Assert.Equal("rpc_unavailable", service.Snapshot.ErrorCode);
            Assert.All(service.Snapshot.Networks, n => Assert.Equal(collected[n.Name], n.LastCollectionUtc));
            Assert.Contains("bridge_ready 0", service.Metrics());
            var errors = service.Metrics().Split('\n').Single(line => line.StartsWith("bridge_cycle_errors_total{component=\"identity\"}", StringComparison.Ordinal));
            Assert.True(long.Parse(errors.Split(' ')[1], System.Globalization.CultureInfo.InvariantCulture) >= 1);
        }
        finally { await service.StopAsync(default); }
    }

    private static async Task Until(Func<bool> condition)
    {
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(4));
        while (!condition()) await Task.Delay(10, timeout.Token);
    }
}
