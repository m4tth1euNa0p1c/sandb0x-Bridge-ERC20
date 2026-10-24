using Bridge.Relayer;

namespace Bridge.Relayer.Tests;

public sealed class CollectionTests
{
    [Fact]
    public async Task HistoricalRestartCatchesMissedEventsAndDeduplicatesRepeatedLogs()
    {
        var f = new Fixture(); var a = f.Rpc.State[f.A.ChainId];
        a.Events.AddRange([f.Event(), f.Event(nonce: 1, block: 7)]); a.DuplicateSourceLogs = true;
        await new Collector(f.Config, f.Chain, f.Store).CollectAsync(f.A, default);
        Assert.Equal(2, f.Store.Transfers.Count); Assert.Equal(21, f.Store.Checkpoints[f.A.ChainId].NextBlock);
        await new Collector(f.Config, f.Chain, f.Store).CollectAsync(f.A, default);
        Assert.Equal(2, f.Store.Transfers.Count); Assert.Empty(f.Signer.Requests);
    }

    [Fact]
    public async Task SilentlyTruncatedRpcLogsCannotAdvanceCheckpoint()
    {
        var f = new Fixture(); var a = f.Rpc.State[f.A.ChainId]; a.Events.Add(f.Event()); a.HideSourceLogs = true;
        var error = await Assert.ThrowsAsync<RpcFailure>(() => new Collector(f.Config, f.Chain, f.Store).CollectAsync(f.A, default));
        Assert.Equal("historical_log_coverage_mismatch", error.Code); Assert.Equal(0, f.Store.Checkpoints[f.A.ChainId].NextBlock); Assert.Empty(f.Store.Transfers);
    }

    [Fact]
    public async Task ReorgBeforeFinalityOrphansBurnAndRewindsHistoricalCheckpoint()
    {
        var f = new Fixture(); var a = f.Rpc.State[f.A.ChainId]; a.Head = 5; a.Events.Add(f.Event());
        var collector = new Collector(f.Config, f.Chain, f.Store);
        await collector.CollectAsync(f.A, default);
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.WaitingFinality, f.Stored().State);
        a.Events.Clear(); a.Blocks[5] = a.Blocks[5] with { Hash = Fixture.Hash("new-five") };
        await collector.CollectAsync(f.A, default);
        Assert.Equal(States.Rejected, f.Stored().State); Assert.Equal("source_reorg", f.Stored().ErrorCode);
        Assert.Equal(Fixture.Hash("new-five"), f.Store.Blocks[f.A.ChainId].Single(b => b.Number == 5).Hash);
        Assert.Equal(6, f.Store.Checkpoints[f.A.ChainId].NextBlock); Assert.Empty(f.Signer.Requests);
    }

    [Fact]
    public async Task StartAfterFirstBurnFailsRatherThanClaimingCompleteHistory()
    {
        var f = new Fixture(); var source = f.A with { StartBlock = 8 };
        var config = f.Config with { Networks = [source, f.B] };
        f.Rpc.State[f.A.ChainId].Events.Add(f.Event()); f.Store.Checkpoints[f.A.ChainId] = new(8, null, 0, 0);
        var error = await Assert.ThrowsAsync<RpcFailure>(() => new Collector(config, f.Chain, f.Store).CollectAsync(source, default));
        Assert.Equal("history_anchor_after_first_transfer", error.Code); Assert.Equal(8, f.Store.Checkpoints[f.A.ChainId].NextBlock);
    }

    [Fact]
    public async Task InconsistentParentHashPreventsPartialDatabaseCommit()
    {
        var f = new Fixture(); f.Rpc.State[f.A.ChainId].Blocks[4] = f.Rpc.State[f.A.ChainId].Blocks[4] with { ParentHash = Fixture.Hash("unrelated-parent") };
        var error = await Assert.ThrowsAsync<RpcFailure>(() => new Collector(f.Config, f.Chain, f.Store).CollectAsync(f.A, default));
        Assert.Equal("block_sequence_inconsistent", error.Code); Assert.Equal(0, f.Store.Checkpoints[f.A.ChainId].NextBlock); Assert.Empty(f.Store.Blocks);
    }
}
