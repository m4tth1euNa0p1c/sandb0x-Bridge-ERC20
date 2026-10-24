using System.Numerics;

namespace Bridge.Relayer;

public sealed record BlockHeader(long Number, string Hash, string ParentHash);
public sealed record SourceEvent(string Id, long SourceChain, long DestinationChain, long BlockNumber,
    string BlockHash, string TransactionHash, long LogIndex, string Recipient, BigInteger SourceNonce, BigInteger Amount);
public sealed record Receipt(string TransactionHash, long BlockNumber, string BlockHash, bool Success);
public sealed record Completion(string Id, string Recipient, BigInteger Amount, long BlockNumber, string BlockHash);
public sealed record SignedPayload(string RawTransaction, string TransactionHash, string SignerAddress);
public sealed record SignRequest(long ChainId, string Nonce, string GasPriceWei, int GasLimit, string To, string Data);
public sealed record Checkpoint(long NextBlock, DateTimeOffset? LastCollection, long Head, long Finalized);

public static class States
{
    public const string Observed = "observed", WaitingFinality = "waiting_finality", SourceFinalized = "source_finalized",
        Prepared = "destination_prepared", Submitted = "destination_submitted", Finalized = "destination_finalized",
        WaitingGas = "waiting_gas", WaitingPause = "waiting_pause", WaitingRate = "waiting_rate",
        Retryable = "retryable_failure", Rejected = "rejected", Intervention = "intervention_required";
    public static readonly string[] All = [Observed, WaitingFinality, SourceFinalized, Prepared, Submitted, Finalized, WaitingGas, WaitingPause, WaitingRate, Retryable, Rejected, Intervention];
}

public sealed class Transfer
{
    public required SourceEvent Event { get; init; }
    public required string DestinationSigner { get; init; }
    public string State { get; set; } = States.Observed;
    public string? ErrorCode { get; set; }
    public int Attempts { get; set; }
    public long? DestinationNonce { get; set; }
    public BigInteger? GasPrice { get; set; }
    // Durable transaction bytes are intentionally absent from all endpoint/log DTOs.
    public string? SignedRaw { get; set; }
    public string? DestinationHash { get; set; }
    public long? DestinationBlock { get; set; }
    public string? DestinationBlockHash { get; set; }
    public DateTimeOffset ObservedAt { get; init; } = DateTimeOffset.UtcNow;
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? LastAttempt { get; set; }
    public DateTimeOffset NextAttempt { get; set; } = DateTimeOffset.UtcNow;
}

public sealed record Reconciliation(string State, string? ExpectedSupply, string? SupplyA, string? SupplyB,
    string? InTransit, string? Difference, IReadOnlyDictionary<string, BlockHeader> Cuts,
    DateTimeOffset UpdatedUtc, string? Reason);
public sealed record NetworkView(string Name, long ChainId, long Head, long Finalized, long NextBlock,
    DateTimeOffset? LastCollectionUtc, string GasBalanceWei, bool Paused);
public sealed record TransferSummary(IReadOnlyDictionary<string, long> Counts, double OldestPendingSeconds, long Attempts);

public interface IRpc
{
    Task<System.Text.Json.JsonElement> CallAsync(NetworkConfig network, string method, object?[] parameters, CancellationToken ct);
}

public interface ISigner
{
    Task<SignedPayload> SignAsync(SignRequest request, CancellationToken ct);
}

public interface IBridgeStore
{
    Task InitializeAsync(BridgeConfig configuration, CancellationToken ct);
    Task<IAsyncDisposable?> TryLockAsync(int category, long chainId, CancellationToken ct);
    Task<Checkpoint> CheckpointAsync(NetworkConfig network, CancellationToken ct);
    Task<IReadOnlyList<BlockHeader>> StoredBlocksAsync(NetworkConfig network, CancellationToken ct);
    Task RewindAsync(NetworkConfig network, long ancestor, CancellationToken ct);
    Task SaveBatchAsync(NetworkConfig network, IReadOnlyList<BlockHeader> blocks, IReadOnlyList<SourceEvent> events,
        string destinationSigner, long head, long finalized, CancellationToken ct);
    Task<Transfer?> NextAsync(NetworkConfig destination, CancellationToken ct);
    Task SaveAsync(Transfer transfer, CancellationToken ct);
    Task ReserveNonceAsync(Transfer transfer, long pendingNonce, BigInteger gasPrice, CancellationToken ct);
    Task<int> RecentAttemptsAsync(long destinationChain, CancellationToken ct);
    Task<IReadOnlyList<Transfer>> CanonicalAtAsync(IReadOnlyDictionary<long, long> heights, CancellationToken ct);
    Task<TransferSummary> SummaryAsync(CancellationToken ct);
    Task SaveReconciliationAsync(Reconciliation value, CancellationToken ct);
}

public interface IFaults
{
    void Hit(string point, string transferId);
}

public sealed class LocalFaults : IFaults
{
    public void Hit(string point, string transferId)
    {
        if (Environment.GetEnvironmentVariable("BRIDGE_FAULT_POINT") != point) return;
        var target = Environment.GetEnvironmentVariable("BRIDGE_FAULT_TRANSFER_ID");
        if (target is not null && !target.Equals(transferId, StringComparison.OrdinalIgnoreCase)) return;
        Environment.Exit(point == "after_signed_persisted" ? 91 : 92);
    }
}
