using Bridge.Relayer;

namespace Bridge.Relayer.Tests;

public sealed class ReconciliationTests
{
    [Fact]
    public async Task LostFinalizedMintRequiresInterventionAndBlocksConsumedNonceAccount()
    {
        var f = new Fixture(); f.Add();
        await f.Processor().ProcessAsync(f.B, default); f.Due();
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.Finalized, f.Stored().State);
        var originalNonce = f.Stored().DestinationNonce;
        var originalHash = f.Stored().DestinationHash;
        var destination = f.Rpc.State[f.B.ChainId];
        destination.Completed.Clear(); destination.Processed.Clear(); destination.Receipts.Clear();
        destination.Blocks[17] = destination.Blocks[17] with { Hash = Fixture.Hash("replacement-destination-block") };
        // A different transaction on the replacement branch consumed nonce zero.
        destination.LatestNonce = 1; destination.PendingNonce = 1;
        f.Rpc.State[f.A.ChainId].Supply = 490; destination.Supply = 500; f.CaughtUp();
        var report = await new Reconciler(f.Config, f.Chain, f.Store).RunAsync(default);
        Assert.Equal("inconclusive", report.State);
        Assert.Equal("destination_effect_lost_after_policy_finality", report.Reason);
        Assert.Equal(States.Intervention, f.Stored().State);
        Assert.Equal(originalNonce, f.Stored().DestinationNonce); Assert.Equal(originalHash, f.Stored().DestinationHash);
        Assert.Null(report.Difference); Assert.Single(f.Store.Reports);
        var nextReport = await new Reconciler(f.Config, f.Chain, f.Store).RunAsync(default);
        Assert.Equal("inconclusive", nextReport.State); Assert.Equal(report.Reason, nextReport.Reason);
        f.Add(f.Event(nonce: 1)); f.Due();
        Assert.Null(await f.Store.NextAsync(f.B, default));
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Single(destination.Broadcasts); Assert.Single(f.Signer.Requests); Assert.Equal(1, f.Store.ReservationCount);
    }

    [Fact]
    public async Task BothDirectionsAndInTransitCountExactlyOnce()
    {
        var f = new Fixture(); f.CaughtUp(); var ab = f.Event(amount: 50); var ba = f.Event(f.B, amount: 30); f.Add(ab); f.Add(ba);
        f.Rpc.State[f.A.ChainId].Supply = 800; f.Rpc.State[f.B.ChainId].Supply = 170;
        var b = f.Rpc.State[f.B.ChainId]; b.Processed[ab.Id] = 10; b.Completed[ab.Id] = new(ab.Id, ab.Recipient, ab.Amount, 10, b.Blocks[10].Hash);
        var report = await new Reconciler(f.Config, f.Chain, f.Store).RunAsync(default);
        Assert.Equal("balanced", report.State); Assert.Equal("30", report.InTransit); Assert.Equal("0", report.Difference); Assert.Single(f.Store.Reports);
    }

    [Fact]
    public async Task ExternalIssuanceIsReportedAsMismatch()
    {
        var f = new Fixture(); f.CaughtUp(); f.Rpc.State[f.A.ChainId].Supply = 501;
        var report = await new Reconciler(f.Config, f.Chain, f.Store).RunAsync(default);
        Assert.Equal("mismatch", report.State); Assert.Equal("1", report.Difference); Assert.Contains("external_issuance", report.Reason);
    }

    [Fact]
    public async Task CausallyInconsistentCutIsInconclusiveNotSupplyMismatch()
    {
        var f = new Fixture(); f.CaughtUp(); var e = f.Event(block: 19); f.Add(e);
        var b = f.Rpc.State[f.B.ChainId]; b.Completed[e.Id] = new(e.Id, e.Recipient, e.Amount, 15, b.Blocks[15].Hash); b.Processed[e.Id] = 15; b.Supply += e.Amount;
        var report = await new Reconciler(f.Config, f.Chain, f.Store).RunAsync(default);
        Assert.Equal("inconclusive", report.State); Assert.Equal("destination_mint_without_source_burn_in_cut", report.Reason); Assert.Null(report.Difference);
    }

    [Fact]
    public async Task LaggingCollectorCannotCertifySupply()
    {
        var f = new Fixture();
        var report = await new Reconciler(f.Config, f.Chain, f.Store).RunAsync(default);
        Assert.Equal("inconclusive", report.State); Assert.Equal("collector_behind_checkpoint", report.Reason); Assert.Null(report.Difference);
    }

    [Fact]
    public async Task MissingCompletionLogIsNotSilentlyCountedAsBalanced()
    {
        var f = new Fixture(); f.CaughtUp(); var e = f.Event(); f.Add(e); f.Rpc.State[f.B.ChainId].Processed[e.Id] = 10;
        var report = await new Reconciler(f.Config, f.Chain, f.Store).RunAsync(default);
        Assert.Equal("inconclusive", report.State); Assert.Equal("completion_log_coverage_mismatch", report.Reason);
    }

    [Fact]
    public async Task ChangedCheckpointHashInvalidatesSnapshot()
    {
        var f = new Fixture(); f.CaughtUp(); var reads = 0;
        f.Rpc.Override = (n, method, p) =>
        {
            if (n.ChainId == f.A.ChainId && method == "eth_getBlockByNumber" && (string)p[0]! == Abi.Hex(17) && ++reads == 2)
                return FakeRpc.Json(new { number = Abi.Hex(17), hash = Fixture.Hash("reorg-during-cut"), parentHash = f.Rpc.State[n.ChainId].Blocks[16].Hash });
            return null;
        };
        var report = await new Reconciler(f.Config, f.Chain, f.Store).RunAsync(default);
        Assert.Equal("inconclusive", report.State); Assert.Equal("reorg_during_reconciliation", report.Reason);
    }
}
