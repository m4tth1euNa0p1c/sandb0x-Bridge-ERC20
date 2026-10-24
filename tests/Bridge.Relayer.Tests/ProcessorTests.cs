using Bridge.Relayer;

namespace Bridge.Relayer.Tests;

public sealed class ProcessorTests
{
    [Fact]
    public async Task ThreeBlocksAfterInclusionAreRequiredBeforeSigning()
    {
        var f = new Fixture(); f.Add(); f.Rpc.State[f.A.ChainId].Head = 7;
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.WaitingFinality, f.Stored().State); Assert.Empty(f.Signer.Requests); Assert.Equal(0, f.Store.ReservationCount);
        f.Rpc.State[f.A.ChainId].Head = 8; f.Due();
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Single(f.Rpc.State[f.B.ChainId].Broadcasts); Assert.Equal(States.Submitted, f.Stored().State);
    }

    [Fact]
    public async Task OrphanedSourceBurnCannotMint()
    {
        var f = new Fixture(); f.Add(); var state = f.Rpc.State[f.A.ChainId];
        state.Blocks[5] = state.Blocks[5] with { Hash = Fixture.Hash("replacement") };
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.Rejected, f.Stored().State); Assert.Equal("source_reorg", f.Stored().ErrorCode);
        Assert.Empty(f.Signer.Requests); Assert.Empty(f.Rpc.State[f.B.ChainId].Broadcasts);
    }

    [Theory]
    [InlineData(true, "waiting_pause")]
    [InlineData(false, "waiting_gas")]
    public async Task PauseOrEmptyGasBalanceWaitsWithoutNonceThenResumes(bool paused, string expected)
    {
        var f = new Fixture(); f.Add(); var dest = f.Rpc.State[f.B.ChainId];
        if (paused) dest.Paused = true; else dest.Balance = 0;
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(expected, f.Stored().State); Assert.Null(f.Stored().DestinationNonce); Assert.Empty(f.Signer.Requests);
        dest.Paused = false; dest.Balance = 1000000; f.Due();
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(1, dest.MintEffects); Assert.Single(f.Signer.Requests);
    }

    [Fact]
    public async Task CrashAfterSignedPersistenceRestartsWithoutResigningOrReservingAnotherNonce()
    {
        var f = new Fixture(); f.Add();
        await Assert.ThrowsAsync<TestCrash>(() => f.Processor(new CrashAt("after_signed_persisted")).ProcessAsync(f.B, default));
        var original = FakeStore.Clone(f.Stored());
        Assert.NotNull(original.SignedRaw); Assert.NotNull(original.DestinationHash); Assert.Equal(0, original.DestinationNonce); Assert.Empty(f.Rpc.State[f.B.ChainId].Broadcasts);
        f.Due(); await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(original.SignedRaw, Assert.Single(f.Rpc.State[f.B.ChainId].Broadcasts));
        Assert.Single(f.Signer.Requests); Assert.Equal(1, f.Store.ReservationCount);
    }

    [Fact]
    public async Task CrashAfterBroadcastRecoversReceiptAndNeverBroadcastsAgain()
    {
        var f = new Fixture(); f.Add();
        await Assert.ThrowsAsync<TestCrash>(() => f.Processor(new CrashAt("after_broadcast")).ProcessAsync(f.B, default));
        var original = FakeStore.Clone(f.Stored());
        Assert.Equal(States.Prepared, original.State); Assert.Equal(1, f.Rpc.State[f.B.ChainId].MintEffects);
        f.Due(); await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.Finalized, f.Stored().State); Assert.Equal(original.DestinationHash, f.Stored().DestinationHash);
        Assert.Single(f.Rpc.State[f.B.ChainId].Broadcasts); Assert.Single(f.Signer.Requests);
    }

    [Theory]
    [InlineData(1)]
    [InlineData(12)]
    public async Task LostSendResponseReconcilesEvenOnLastAttempt(int maxAttempts)
    {
        var f = new Fixture(maxAttempts); f.Add(); var dest = f.Rpc.State[f.B.ChainId]; dest.LoseSendResponse = true;
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.Retryable, f.Stored().State); Assert.Equal(1, dest.MintEffects);
        f.Due(); await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.Finalized, f.Stored().State); Assert.Single(dest.Broadcasts); Assert.Single(f.Signer.Requests); Assert.Equal(1, f.Store.ReservationCount);
    }

    [Fact]
    public async Task UnminedAmbiguousSendRebroadcastsIdenticalBytes()
    {
        var f = new Fixture(); f.Add(); var dest = f.Rpc.State[f.B.ChainId]; dest.Automine = false; dest.LoseSendResponse = true;
        await f.Processor().ProcessAsync(f.B, default); f.Due();
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(2, dest.Broadcasts.Count); Assert.Equal(dest.Broadcasts[0], dest.Broadcasts[1]); Assert.Single(f.Signer.Requests); Assert.Equal(1, f.Store.ReservationCount); Assert.Equal(0, dest.MintEffects);
    }

    [Fact]
    public async Task ConcurrentApplicationWorkersCannotReserveSameAccountTwice()
    {
        var f = new Fixture(); f.Add(); f.Signer.DelayMilliseconds = 60;
        await Task.WhenAll(Enumerable.Range(0, 8).Select(_ => f.Processor().ProcessAsync(f.B, default)));
        Assert.Single(f.Signer.Requests); Assert.Equal(1, f.Store.ReservationCount); Assert.Single(f.Rpc.State[f.B.ChainId].Broadcasts);
        f.Due(); await f.Processor().ProcessAsync(f.B, default);
        var second = f.Event(nonce: 1); f.Add(second); f.Due(); await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(1, f.Store.Transfers[second.Id].DestinationNonce);
        Assert.Equal(2, f.Store.ReservationCount); Assert.Equal(2, f.Rpc.State[f.B.ChainId].MintEffects);
    }

    [Theory]
    [InlineData("rpc_unavailable")]
    [InlineData("rpc_timeout")]
    [InlineData("rpc_envelope_inconsistent")]
    public async Task RpcFailureBeforeSourceConfirmationDoesNotSign(string code)
    {
        var f = new Fixture(); f.Add(); f.Rpc.Override = (_, _, _) => throw new RpcFailure(code);
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.Retryable, f.Stored().State); Assert.Equal(code, f.Stored().ErrorCode); Assert.Empty(f.Signer.Requests); Assert.Equal(0, f.Store.ReservationCount);
    }

    [Fact]
    public async Task ReceiptWithoutProcessedMappingDemandsIntervention()
    {
        var f = new Fixture(); f.Add(); await f.Processor().ProcessAsync(f.B, default); f.Due();
        f.Rpc.State[f.B.ChainId].Processed.Clear();
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.Intervention, f.Stored().State); Assert.Equal("receipt_without_business_effect", f.Stored().ErrorCode); Assert.Single(f.Rpc.State[f.B.ChainId].Broadcasts);
    }

    [Fact]
    public async Task KnownPendingTransactionTimesOutWithoutReplacement()
    {
        var f = new Fixture(); f.Add(); var dest = f.Rpc.State[f.B.ChainId]; dest.Automine = false;
        await f.Processor().ProcessAsync(f.B, default); dest.KnownTransactions.Add(f.Stored().DestinationHash!);
        f.Stored().LastAttempt = DateTimeOffset.UtcNow.AddHours(-1); f.Due();
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.Intervention, f.Stored().State); Assert.Equal("pending_transaction_timeout_no_replacement", f.Stored().ErrorCode);
        Assert.Single(dest.Broadcasts); Assert.Single(f.Signer.Requests);
    }

    [Fact]
    public async Task MintByAnotherExecutorNeverCausesCompensatoryMint()
    {
        var f = new Fixture(); f.Add(); f.Rpc.State[f.B.ChainId].Processed[f.Event().Id] = 5;
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal("processed_without_owned_receipt", f.Stored().ErrorCode); Assert.Equal(States.Intervention, f.Stored().State);
        Assert.Empty(f.Signer.Requests); Assert.Null(f.Stored().DestinationNonce);
    }

    [Fact]
    public async Task InconsistentAccountNonceAndRateLimitFailWithoutSigning()
    {
        var f = new Fixture(); f.Add(); f.Rpc.State[f.B.ChainId].LatestNonce = 1;
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal("rpc_nonce_inconsistent", f.Stored().ErrorCode); Assert.Empty(f.Signer.Requests);
        f.Rpc.State[f.B.ChainId].LatestNonce = 0; f.Store.RecentAttempts = 10; f.Due();
        await f.Processor().ProcessAsync(f.B, default);
        Assert.Equal(States.WaitingRate, f.Stored().State); Assert.Null(f.Stored().DestinationNonce);
    }
}
