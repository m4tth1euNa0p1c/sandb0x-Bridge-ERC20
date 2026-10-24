using System.Globalization;

namespace Bridge.Relayer;

public sealed class TransferProcessor(BridgeConfig config, Chain chain, IBridgeStore store, ISigner signer, IFaults faults, ILogger<TransferProcessor>? logger = null)
{
    public async Task ProcessAsync(NetworkConfig destination, CancellationToken ct)
    {
        await using var lease = await store.TryLockAsync(74003, destination.ChainId, ct);
        if (lease is null) return;
        var transfer = await store.NextAsync(destination, ct);
        if (transfer is null || transfer.NextAttempt > DateTimeOffset.UtcNow) return;
        var source = config.Network(transfer.Event.SourceChain);
        var attemptRecorded = false;
        try
        {
            if (!await SourceCanonical(source, transfer, ct))
            {
                await Set(transfer, transfer.DestinationNonce is null ? States.Rejected : States.Intervention, "source_reorg", ct);
                return;
            }
            var sourceHead = await chain.Head(source, ct);
            if (Chain.FinalizedHeight(source, sourceHead) < transfer.Event.BlockNumber)
            {
                await Set(transfer, States.WaitingFinality, "source_not_finalized", ct);
                return;
            }
            if (transfer.State is States.Observed or States.WaitingFinality)
                await Set(transfer, States.SourceFinalized, null, ct);

            // A receipt, processed mapping and canonical destination block are checked before
            // gas/pause/retries: a mined effect must not be obscured by a later empty balance.
            if (transfer.DestinationHash is not null)
            {
                var receipt = await chain.Receipt(destination, transfer.DestinationHash, ct);
                if (receipt is not null)
                {
                    var canonical = await chain.Block(destination, receipt.BlockNumber, ct);
                    if (canonical is null || !Abi.Same(canonical.Hash, receipt.BlockHash))
                        throw new RpcFailure("destination_receipt_noncanonical");
                    if (!receipt.Success)
                    {
                        await Set(transfer, States.Intervention, "destination_reverted_no_compensation", ct);
                        return;
                    }
                    if (!await chain.Processed(destination, transfer.Event.Id, Abi.Hex(receipt.BlockNumber), ct))
                        throw new RpcFailure("receipt_without_business_effect", false);
                    transfer.DestinationBlock = receipt.BlockNumber;
                    transfer.DestinationBlockHash = receipt.BlockHash;
                    var head = await chain.Head(destination, ct);
                    await Set(transfer, Chain.FinalizedHeight(destination, head) >= receipt.BlockNumber ? States.Finalized : States.Submitted, null, ct);
                    return;
                }
            }
            if (await chain.Processed(destination, transfer.Event.Id, "latest", ct))
            {
                // Another authorized actor may have minted. Never invent a receipt or consume
                // an unused reserved nonce to compensate; require an explicit investigation.
                await Set(transfer, States.Intervention, "processed_without_owned_receipt", ct);
                return;
            }
            var latestNonce = await chain.Nonce(destination, "latest", ct);
            var pendingNonce = await chain.Nonce(destination, "pending", ct);
            if (pendingNonce < latestNonce) throw new RpcFailure("rpc_nonce_inconsistent");
            if (transfer.DestinationNonce is not null && latestNonce > transfer.DestinationNonce)
            {
                await Set(transfer, States.Intervention, "nonce_consumed_receipt_unknown", ct);
                return;
            }
            if (transfer.DestinationHash is not null && await chain.TransactionKnown(destination, transfer.DestinationHash, ct))
            {
                if (transfer.LastAttempt is not null && DateTimeOffset.UtcNow - transfer.LastAttempt > TimeSpan.FromSeconds(config.PendingTimeoutSeconds))
                    await Set(transfer, States.Intervention, "pending_transaction_timeout_no_replacement", ct);
                else await Set(transfer, States.Submitted, null, ct);
                return;
            }
            if (transfer.DestinationNonce is not null && pendingNonce > transfer.DestinationNonce)
                throw new RpcFailure("pending_nonce_ambiguous");
            if (transfer.Attempts >= config.MaxAttempts)
            {
                await Set(transfer, States.Intervention, "attempt_limit", ct);
                return;
            }
            if (await chain.Paused(destination, ct)) { await Set(transfer, States.WaitingPause, "destination_paused", ct); return; }
            var gasPrice = transfer.GasPrice ?? await chain.GasPrice(destination, ct);
            if (gasPrice < 0 || gasPrice > destination.GasPriceLimit)
            { await Set(transfer, States.WaitingGas, "gas_price_above_limit", ct); return; }
            if (await chain.Balance(destination, ct) < gasPrice * destination.GasLimit)
            { await Set(transfer, States.WaitingGas, "insufficient_test_gas", ct); return; }
            if (await store.RecentAttemptsAsync(destination.ChainId, ct) >= config.MaxPerMinute)
            {
                transfer.NextAttempt = DateTimeOffset.UtcNow.AddSeconds(6);
                await Set(transfer, States.WaitingRate, "rate_limit", ct, preserveSchedule: true);
                return;
            }
            if (transfer.DestinationNonce is null)
            {
                if (pendingNonce != latestNonce) throw new RpcFailure("unmanaged_pending_account_transaction", false);
                await store.ReserveNonceAsync(transfer, pendingNonce, gasPrice, ct);
            }
            if (transfer.SignedRaw is null)
            {
                var request = new SignRequest(destination.ChainId, transfer.DestinationNonce!.Value.ToString(CultureInfo.InvariantCulture),
                    transfer.GasPrice!.Value.ToString(CultureInfo.InvariantCulture), destination.GasLimit, destination.BridgeAddress, Abi.CompletionData(source, transfer.Event));
                var signed = await signer.SignAsync(request, ct);
                if (!Abi.Same(signed.SignerAddress, destination.SignerAddress) || !signed.RawTransaction.StartsWith("0x", StringComparison.Ordinal) || !Abi.Same(Abi.Hash(Convert.FromHexString(signed.RawTransaction[2..])), signed.TransactionHash))
                    throw new RpcFailure("signed_payload_integrity_mismatch", false);
                transfer.SignedRaw = signed.RawTransaction;
                transfer.DestinationHash = Abi.RequireHash(signed.TransactionHash);
                await Set(transfer, States.Prepared, null, ct);
                faults.Hit("after_signed_persisted", transfer.Event.Id);
            }
            // Last source-hash recheck immediately before diffusion. A reorg beyond the
            // configured finality assumption remains a trust/consensus limitation.
            if (!await SourceCanonical(source, transfer, ct))
            { await Set(transfer, States.Intervention, "source_reorg", ct); return; }
            transfer.Attempts++;
            transfer.LastAttempt = DateTimeOffset.UtcNow;
            await Set(transfer, States.Prepared, null, ct);
            attemptRecorded = true;
            await chain.Send(destination, new(transfer.SignedRaw, transfer.DestinationHash!, destination.SignerAddress), ct);
            faults.Hit("after_broadcast", transfer.Event.Id);
            await Set(transfer, States.Submitted, null, ct);
        }
        catch (RpcFailure error)
        {
            if (!attemptRecorded) { transfer.Attempts++; transfer.LastAttempt = DateTimeOffset.UtcNow; }
            transfer.NextAttempt = DateTimeOffset.UtcNow.AddSeconds(Math.Min(30, Math.Pow(2, Math.Min(transfer.Attempts, 5))));
            // Even the last permitted send can have reached the node before a timeout.
            // Keep one reconciliation pass eligible before applying the attempt ceiling.
            var reconcileBroadcast = attemptRecorded && transfer.DestinationHash is not null;
            await Set(transfer, reconcileBroadcast || error.Retryable && transfer.Attempts < config.MaxAttempts ? States.Retryable : States.Intervention, error.Code, ct, preserveSchedule: true);
        }
        catch (ConfigurationException error)
        {
            await Set(transfer, States.Intervention, error.Message, ct);
        }
        catch (FormatException)
        {
            await Set(transfer, States.Intervention, "invalid_rpc_or_signature_encoding", ct);
        }
    }

    private async Task<bool> SourceCanonical(NetworkConfig source, Transfer t, CancellationToken ct)
    {
        var block = await chain.Block(source, t.Event.BlockNumber, ct);
        return block is not null && Abi.Same(block.Hash, t.Event.BlockHash);
    }

    private async Task Set(Transfer t, string state, string? error, CancellationToken ct, bool preserveSchedule = false)
    {
        var changed = t.State != state || t.ErrorCode != error;
        t.State = state;
        t.ErrorCode = error;
        if (!preserveSchedule) t.NextAttempt = DateTimeOffset.UtcNow.AddMilliseconds(config.PollMilliseconds);
        await store.SaveAsync(t, ct);
        if (changed) logger?.LogInformation("transfer_state {TransferId} {State} {ErrorCode}", t.Event.Id, state, error);
    }
}
