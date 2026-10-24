using System.Globalization;
using System.Numerics;

namespace Bridge.Relayer;

public sealed class Reconciler(BridgeConfig config, Chain chain, IBridgeStore store)
{
    public async Task<Reconciliation> RunAsync(CancellationToken ct)
    {
        var cuts = new Dictionary<string, BlockHeader>();
        foreach (var network in config.Networks)
        {
            var head = await chain.Head(network, ct);
            var height = Chain.FinalizedHeight(network, head);
            if ((await store.CheckpointAsync(network, ct)).NextBlock <= height)
                return Inconclusive(cuts, "collector_behind_checkpoint");
            var block = await chain.Block(network, height, ct);
            if (block is null) return Inconclusive(cuts, "checkpoint_block_missing");
            cuts.Add(network.Name, block);
        }
        var supplies = new List<BigInteger>();
        foreach (var network in config.Networks)
            supplies.Add(await chain.Supply(network, cuts[network.Name].Number, ct));
        var transfers = await store.CanonicalAtAsync(config.Networks.ToDictionary(n => n.ChainId, n => cuts[n.Name].Number), ct);
        if (transfers.Select(t => t.Event.Id).Distinct().Count() != transfers.Count)
            return Inconclusive(cuts, "duplicate_transfer_in_reconciliation");
        var completed = new Dictionary<long, IReadOnlyList<Completion>>();
        var burns = transfers.ToDictionary(t => t.Event.Id);
        foreach (var network in config.Networks)
        {
            var logs = await chain.Completions(network, cuts[network.Name].Number, ct);
            foreach (var completion in logs)
            {
                if (!burns.TryGetValue(completion.Id, out var burn))
                    return Inconclusive(cuts, "destination_mint_without_source_burn_in_cut");
                if (burn.Event.DestinationChain != network.ChainId || burn.Event.Amount != completion.Amount || !Abi.Same(burn.Event.Recipient, completion.Recipient))
                    return Inconclusive(cuts, "completion_and_burn_mismatch");
                var block = await chain.Block(network, completion.BlockNumber, ct);
                if (block is null || !Abi.Same(block.Hash, completion.BlockHash))
                    return Inconclusive(cuts, "completion_noncanonical");
            }
            completed[network.ChainId] = logs;
        }
        BigInteger transit = 0;
        foreach (var t in transfers)
        {
            var destination = config.Network(t.Event.DestinationChain);
            var processed = await chain.Processed(destination, t.Event.Id, Abi.Hex(cuts[destination.Name].Number), ct);
            if (!processed && (t.State == States.Finalized || t.State == States.Intervention && t.ErrorCode == "destination_effect_lost_after_policy_finality") && t.DestinationBlock is not null && t.DestinationBlock <= cuts[destination.Name].Number)
            {
                // A local confirmation threshold is an assumption, not irreversible finality.
                // Never silently relabel a lost, previously finalized effect as normal transit.
                if (t.State != States.Intervention)
                {
                    t.State = States.Intervention;
                    t.ErrorCode = "destination_effect_lost_after_policy_finality";
                    await store.SaveAsync(t, ct);
                }
                var lost = Inconclusive(cuts, "destination_effect_lost_after_policy_finality");
                await store.SaveReconciliationAsync(lost, ct);
                return lost;
            }
            if (processed != completed[destination.ChainId].Any(c => c.Id == t.Event.Id))
                return Inconclusive(cuts, "completion_log_coverage_mismatch");
            if (!processed) transit += t.Event.Amount;
        }
        foreach (var network in config.Networks)
        {
            var block = await chain.Block(network, cuts[network.Name].Number, ct);
            if (block is null || !Abi.Same(block.Hash, cuts[network.Name].Hash)) return Inconclusive(cuts, "reorg_during_reconciliation");
        }
        var expected = NetworkConfig.Integer(config.ReferenceSupply);
        var difference = supplies[0] + supplies[1] + transit - expected;
        var result = new Reconciliation(difference.IsZero ? "balanced" : "mismatch", Text(expected), Text(supplies[0]), Text(supplies[1]), Text(transit), Text(difference), cuts, DateTimeOffset.UtcNow,
            difference.IsZero ? null : "external_issuance_or_missing_business_effect_requires_investigation");
        await store.SaveReconciliationAsync(result, ct);
        return result;
    }

    private static string Text(BigInteger value) => value.ToString(CultureInfo.InvariantCulture);
    private static Reconciliation Inconclusive(IReadOnlyDictionary<string, BlockHeader> cuts, string reason) =>
        new("inconclusive", null, null, null, null, null, cuts, DateTimeOffset.UtcNow, reason);
}
