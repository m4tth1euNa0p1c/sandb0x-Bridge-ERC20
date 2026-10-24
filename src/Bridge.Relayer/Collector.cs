namespace Bridge.Relayer;

public sealed class Collector(BridgeConfig config, Chain chain, IBridgeStore store)
{
    public async Task CollectAsync(NetworkConfig source, CancellationToken ct)
    {
        await using var lease = await store.TryLockAsync(74002, source.ChainId, ct);
        if (lease is null) return;
        var head = await chain.Head(source, ct);
        var prior = await store.StoredBlocksAsync(source, ct);
        if (prior.Count > 0)
        {
            var last = await chain.Block(source, prior[0].Number, ct);
            if (last is null || !Abi.Same(last.Hash, prior[0].Hash))
            {
                long? ancestor = null;
                foreach (var old in prior)
                {
                    var current = await chain.Block(source, old.Number, ct);
                    if (current is not null && Abi.Same(current.Hash, old.Hash)) { ancestor = old.Number; break; }
                }
                if (ancestor is null && prior[^1].Number == source.StartBlock) ancestor = source.StartBlock - 1;
                if (ancestor is null) throw new RpcFailure("reorg_exceeds_128_blocks", false);
                await store.RewindAsync(source, ancestor.Value, ct);
            }
        }
        var checkpoint = await store.CheckpointAsync(source, ct);
        var destination = config.Other(source);
        if (checkpoint.NextBlock > head)
        {
            await store.SaveBatchAsync(source, [], [], destination.SignerAddress, head, Chain.FinalizedHeight(source, head), ct);
            return;
        }
        var to = Math.Min(head, checkpoint.NextBlock + 31);
        var blocks = new List<BlockHeader>();
        var previous = checkpoint.NextBlock == 0 ? null : await chain.Block(source, checkpoint.NextBlock - 1, ct);
        for (var number = checkpoint.NextBlock; number <= to; number++)
        {
            var block = await chain.Block(source, number, ct) ?? throw new RpcFailure("canonical_block_missing");
            if (previous is not null && !Abi.Same(block.ParentHash, previous.Hash)) throw new RpcFailure("block_sequence_inconsistent");
            blocks.Add(block);
            previous = block;
        }
        var events = await chain.Events(source, destination, checkpoint.NextBlock, to, ct);
        var byHeight = blocks.ToDictionary(x => x.Number);
        if (events.Any(e => !Abi.Same(byHeight[e.BlockNumber].Hash, e.BlockHash))) throw new RpcFailure("log_block_hash_mismatch");
        // Contract source nonces are monotone and start at zero. This catches a silently
        // truncated/empty getLogs response instead of committing a missing event checkpoint.
        var before = await SourceCount(source, checkpoint.NextBlock - 1, ct);
        if (prior.Count == 0 && checkpoint.NextBlock == source.StartBlock && before != 0)
            throw new RpcFailure("history_anchor_after_first_transfer", false);
        var after = await SourceCount(source, to, ct);
        if (after - before != events.Count || events.Select((e, index) => e.SourceNonce == before + index).Any(ok => !ok))
            throw new RpcFailure("historical_log_coverage_mismatch");
        var lastAgain = await chain.Block(source, to, ct);
        if (lastAgain is null || !Abi.Same(lastAgain.Hash, blocks[^1].Hash)) throw new RpcFailure("reorg_during_collection");
        await store.SaveBatchAsync(source, blocks, events, destination.SignerAddress, head, Chain.FinalizedHeight(source, head), ct);
    }

    private async Task<System.Numerics.BigInteger> SourceCount(NetworkConfig source, long height, CancellationToken ct)
    {
        if (height < 0) return 0;
        var code = (await chain.Query(source, "eth_getCode", ct, source.BridgeAddress, Abi.Hex(height))).GetString();
        return code == "0x" ? 0 : await chain.NextSourceNonce(source, height, ct);
    }
}
