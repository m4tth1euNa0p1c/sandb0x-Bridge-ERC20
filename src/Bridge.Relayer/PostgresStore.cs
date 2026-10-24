using System.Globalization;
using System.Numerics;
using System.Reflection;
using System.Text.Json;
using Npgsql;

namespace Bridge.Relayer;

public sealed class PostgresStore(NpgsqlDataSource dataSource) : IBridgeStore
{
    private const string SelectTransfer = """
        SELECT id,source_chain,destination_chain,source_block,source_block_hash,source_tx,log_index,recipient,
        source_nonce,amount::text,destination_signer,state,error_code,attempts,destination_nonce,gas_price::text,
        signed_raw,destination_hash,destination_block,destination_block_hash,observed_at,updated_at,last_attempt,next_attempt
        FROM bridge.transfers
        """;

    private static NpgsqlCommand Command(NpgsqlConnection connection, string sql, params (string Name, object? Value)[] values)
    {
        var command = new NpgsqlCommand(sql, connection) { CommandTimeout = 20 };
        foreach (var (name, value) in values) command.Parameters.AddWithValue(name, value ?? DBNull.Value);
        return command;
    }

    public async Task InitializeAsync(BridgeConfig configuration, CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using (var acquire = Command(connection, "SELECT pg_advisory_lock(74001,0)")) await acquire.ExecuteNonQueryAsync(ct);
        try
        {
            await using var transaction = await connection.BeginTransactionAsync(ct);
            using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Bridge.Relayer.schema.sql") ?? throw new ConfigurationException("schema_resource_missing");
            using var reader = new StreamReader(stream);
            await using (var schema = Command(connection, await reader.ReadToEndAsync(ct))) await schema.ExecuteNonQueryAsync(ct);
            foreach (var network in configuration.Networks)
            {
                await using (var insert = Command(connection,
                    "INSERT INTO bridge.networks(chain_id,identity_hash,next_block) VALUES(@chain,@identity,@start) ON CONFLICT DO NOTHING",
                    ("chain", network.ChainId), ("identity", configuration.Identity(network)), ("start", network.StartBlock))) await insert.ExecuteNonQueryAsync(ct);
                await using var identity = Command(connection, "SELECT identity_hash FROM bridge.networks WHERE chain_id=@chain", ("chain", network.ChainId));
                if (!Equals(await identity.ExecuteScalarAsync(ct), configuration.Identity(network))) throw new ConfigurationException("database_network_identity_changed");
            }
            await transaction.CommitAsync(ct);
        }
        finally
        {
            await using var release = Command(connection, "SELECT pg_advisory_unlock(74001,0)");
            await release.ExecuteNonQueryAsync(CancellationToken.None);
        }
    }

    public async Task<IAsyncDisposable?> TryLockAsync(int category, long chainId, CancellationToken ct)
    {
        var connection = await dataSource.OpenConnectionAsync(ct);
        try
        {
            await using var command = Command(connection, "SELECT pg_try_advisory_lock(@category,@chain)", ("category", category), ("chain", checked((int)chainId)));
            if ((bool)(await command.ExecuteScalarAsync(ct))!) return new Lease(connection, category, checked((int)chainId));
            await connection.DisposeAsync();
            return null;
        }
        catch { await connection.DisposeAsync(); throw; }
    }

    private sealed class Lease(NpgsqlConnection connection, int category, int chain) : IAsyncDisposable
    {
        public async ValueTask DisposeAsync()
        {
            try
            {
                await using var command = Command(connection, "SELECT pg_advisory_unlock(@category,@chain)", ("category", category), ("chain", chain));
                await command.ExecuteNonQueryAsync(CancellationToken.None);
            }
            finally { await connection.DisposeAsync(); }
        }
    }

    public async Task<Checkpoint> CheckpointAsync(NetworkConfig network, CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var command = Command(connection, "SELECT next_block,last_collection,head,finalized FROM bridge.networks WHERE chain_id=@chain", ("chain", network.ChainId));
        await using var reader = await command.ExecuteReaderAsync(ct);
        if (!await reader.ReadAsync(ct)) throw new ConfigurationException("network_checkpoint_missing");
        return new(reader.GetInt64(0), reader.IsDBNull(1) ? null : new DateTimeOffset(reader.GetDateTime(1)), reader.GetInt64(2), reader.GetInt64(3));
    }

    public async Task<IReadOnlyList<BlockHeader>> StoredBlocksAsync(NetworkConfig network, CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var command = Command(connection, "SELECT block_number,block_hash,parent_hash FROM bridge.blocks WHERE chain_id=@chain ORDER BY block_number DESC LIMIT 129", ("chain", network.ChainId));
        await using var reader = await command.ExecuteReaderAsync(ct);
        var result = new List<BlockHeader>();
        while (await reader.ReadAsync(ct)) result.Add(new(reader.GetInt64(0), reader.GetString(1), reader.GetString(2)));
        return result;
    }

    public async Task RewindAsync(NetworkConfig network, long ancestor, CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var transaction = await connection.BeginTransactionAsync(ct);
        await using (var observations = Command(connection, "UPDATE bridge.observations SET canonical=false WHERE source_chain=@chain AND block_number>@ancestor", ("chain", network.ChainId), ("ancestor", ancestor))) await observations.ExecuteNonQueryAsync(ct);
        await using (var transfers = Command(connection, """
            UPDATE bridge.transfers SET state=CASE WHEN destination_nonce IS NULL AND signed_raw IS NULL THEN 'rejected' ELSE 'intervention_required' END,
            error_code='source_reorg',updated_at=now() WHERE source_chain=@chain AND source_block>@ancestor
            """, ("chain", network.ChainId), ("ancestor", ancestor))) await transfers.ExecuteNonQueryAsync(ct);
        await using (var blocks = Command(connection, "DELETE FROM bridge.blocks WHERE chain_id=@chain AND block_number>@ancestor", ("chain", network.ChainId), ("ancestor", ancestor))) await blocks.ExecuteNonQueryAsync(ct);
        await using (var checkpoint = Command(connection, "UPDATE bridge.networks SET next_block=@next WHERE chain_id=@chain", ("next", ancestor + 1), ("chain", network.ChainId))) await checkpoint.ExecuteNonQueryAsync(ct);
        await transaction.CommitAsync(ct);
    }

    public async Task SaveBatchAsync(NetworkConfig network, IReadOnlyList<BlockHeader> blocks, IReadOnlyList<SourceEvent> events, string destinationSigner, long head, long finalized, CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var transaction = await connection.BeginTransactionAsync(ct);
        foreach (var block in blocks)
        {
            await using var insert = Command(connection, "INSERT INTO bridge.blocks(chain_id,block_number,block_hash,parent_hash) VALUES(@chain,@height,@hash,@parent) ON CONFLICT(chain_id,block_number) DO UPDATE SET block_hash=excluded.block_hash,parent_hash=excluded.parent_hash", ("chain", network.ChainId), ("height", block.Number), ("hash", block.Hash), ("parent", block.ParentHash));
            await insert.ExecuteNonQueryAsync(ct);
        }
        foreach (var e in events)
        {
            await using (var insert = Command(connection, """
                INSERT INTO bridge.observations(source_chain,source_bridge,block_number,block_hash,transaction_hash,log_index,transfer_id)
                VALUES(@source,@bridge,@height,@blockhash,@tx,@log,@id)
                ON CONFLICT(source_chain,source_bridge,block_hash,transaction_hash,log_index) DO UPDATE SET canonical=true
                """, ("source", e.SourceChain), ("bridge", Abi.Equal(network.BridgeAddress)), ("height", e.BlockNumber), ("blockhash", e.BlockHash), ("tx", e.TransactionHash), ("log", e.LogIndex), ("id", e.Id))) await insert.ExecuteNonQueryAsync(ct);
            await using var transfer = Command(connection, """
                INSERT INTO bridge.transfers(id,source_chain,destination_chain,source_block,source_block_hash,source_tx,log_index,recipient,source_nonce,amount,destination_signer,state)
                VALUES(@id,@source,@destination,@height,@blockhash,@tx,@log,@recipient,@nonce,CAST(@amount AS numeric),@signer,'observed')
                ON CONFLICT(id) DO UPDATE SET source_block=excluded.source_block,source_block_hash=excluded.source_block_hash,
                source_tx=excluded.source_tx,log_index=excluded.log_index,state='observed',error_code=NULL,next_attempt=now(),updated_at=now()
                WHERE bridge.transfers.state='rejected' AND bridge.transfers.destination_nonce IS NULL AND bridge.transfers.error_code='source_reorg'
                """, ("id", e.Id), ("source", e.SourceChain), ("destination", e.DestinationChain), ("height", e.BlockNumber), ("blockhash", e.BlockHash), ("tx", e.TransactionHash), ("log", e.LogIndex), ("recipient", e.Recipient), ("nonce", checked((long)e.SourceNonce)), ("amount", e.Amount.ToString(CultureInfo.InvariantCulture)), ("signer", Abi.Equal(destinationSigner)));
            await transfer.ExecuteNonQueryAsync(ct);
        }
        await using (var checkpoint = Command(connection, "UPDATE bridge.networks SET next_block=COALESCE(@next,next_block),last_collection=now(),head=@head,finalized=@finalized WHERE chain_id=@chain",
            ("next", blocks.Count == 0 ? null : blocks[^1].Number + 1), ("head", head), ("finalized", finalized), ("chain", network.ChainId))) await checkpoint.ExecuteNonQueryAsync(ct);
        await transaction.CommitAsync(ct);
    }

    public async Task<Transfer?> NextAsync(NetworkConfig destination, CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var command = Command(connection, SelectTransfer + """
             WHERE destination_chain=@chain AND state NOT IN ('destination_finalized','rejected','intervention_required')
             AND NOT EXISTS(SELECT 1 FROM bridge.transfers stopped WHERE stopped.destination_chain=@chain AND stopped.destination_nonce IS NOT NULL AND stopped.state='intervention_required')
             ORDER BY destination_nonce NULLS LAST,observed_at,id LIMIT 1
            """, ("chain", destination.ChainId));
        await using var reader = await command.ExecuteReaderAsync(ct);
        return await reader.ReadAsync(ct) ? ReadTransfer(reader) : null;
    }

    private static Transfer ReadTransfer(NpgsqlDataReader r) => new()
    {
        Event = new(r.GetString(0), r.GetInt64(1), r.GetInt64(2), r.GetInt64(3), r.GetString(4), r.GetString(5), r.GetInt64(6), r.GetString(7), new BigInteger(r.GetInt64(8)), NetworkConfig.Integer(r.GetString(9))),
        DestinationSigner = r.GetString(10), State = r.GetString(11), ErrorCode = r.IsDBNull(12) ? null : r.GetString(12), Attempts = r.GetInt32(13),
        DestinationNonce = r.IsDBNull(14) ? null : r.GetInt64(14), GasPrice = r.IsDBNull(15) ? null : NetworkConfig.Integer(r.GetString(15)),
        SignedRaw = r.IsDBNull(16) ? null : r.GetString(16), DestinationHash = r.IsDBNull(17) ? null : r.GetString(17),
        DestinationBlock = r.IsDBNull(18) ? null : r.GetInt64(18), DestinationBlockHash = r.IsDBNull(19) ? null : r.GetString(19),
        ObservedAt = new DateTimeOffset(r.GetDateTime(20)), UpdatedAt = new DateTimeOffset(r.GetDateTime(21)),
        LastAttempt = r.IsDBNull(22) ? null : new DateTimeOffset(r.GetDateTime(22)), NextAttempt = new DateTimeOffset(r.GetDateTime(23))
    };

    public async Task SaveAsync(Transfer t, CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var transaction = await connection.BeginTransactionAsync(ct);
        t.UpdatedAt = DateTimeOffset.UtcNow;
        await using (var update = Command(connection, """
            UPDATE bridge.transfers SET state=@state,error_code=@error,attempts=@attempts,destination_nonce=@nonce,
            gas_price=CAST(@gasprice AS numeric),signed_raw=@raw,destination_hash=@hash,destination_block=@block,
            destination_block_hash=@blockhash,updated_at=@updated,last_attempt=@last,next_attempt=@next
            WHERE id=@id AND NOT (state='intervention_required' AND error_code='source_reorg')
            """, ("state", t.State), ("error", t.ErrorCode), ("attempts", t.Attempts), ("nonce", t.DestinationNonce),
            ("gasprice", t.GasPrice?.ToString(CultureInfo.InvariantCulture)), ("raw", t.SignedRaw), ("hash", t.DestinationHash), ("block", t.DestinationBlock), ("blockhash", t.DestinationBlockHash),
            ("updated", t.UpdatedAt), ("last", t.LastAttempt), ("next", t.NextAttempt), ("id", t.Event.Id)))
            if (await update.ExecuteNonQueryAsync(ct) != 1) throw new RpcFailure("transfer_state_conflict", false);
        if (t.Attempts > 0 && t.LastAttempt is not null)
        {
            await using var attempt = Command(connection, "INSERT INTO bridge.attempts(transfer_id,attempt,destination_chain,attempted_at) VALUES(@id,@attempt,@chain,@at) ON CONFLICT DO NOTHING", ("id", t.Event.Id), ("attempt", t.Attempts), ("chain", t.Event.DestinationChain), ("at", t.LastAttempt));
            await attempt.ExecuteNonQueryAsync(ct);
        }
        await transaction.CommitAsync(ct);
    }

    public async Task ReserveNonceAsync(Transfer t, long pendingNonce, BigInteger gasPrice, CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var transaction = await connection.BeginTransactionAsync(ct);
        await using (var initialize = Command(connection, "INSERT INTO bridge.nonces(chain_id,signer,next_nonce) VALUES(@chain,@signer,@pending) ON CONFLICT DO NOTHING", ("chain", t.Event.DestinationChain), ("signer", Abi.Equal(t.DestinationSigner)), ("pending", pendingNonce))) await initialize.ExecuteNonQueryAsync(ct);
        await using var select = Command(connection, "SELECT next_nonce FROM bridge.nonces WHERE chain_id=@chain AND signer=@signer FOR UPDATE", ("chain", t.Event.DestinationChain), ("signer", Abi.Equal(t.DestinationSigner)));
        var nonce = (long)(await select.ExecuteScalarAsync(ct))!;
        if (nonce < pendingNonce || nonce > 1000000) throw new RpcFailure("account_nonce_requires_intervention", false);
        await using (var reserve = Command(connection, "UPDATE bridge.transfers SET destination_nonce=@nonce,gas_price=CAST(@gasprice AS numeric),updated_at=now() WHERE id=@id AND destination_nonce IS NULL AND state<>'intervention_required'", ("nonce", nonce), ("gasprice", gasPrice.ToString(CultureInfo.InvariantCulture)), ("id", t.Event.Id)))
            if (await reserve.ExecuteNonQueryAsync(ct) != 1) throw new RpcFailure("nonce_reservation_conflict", false);
        await using (var increment = Command(connection, "UPDATE bridge.nonces SET next_nonce=@next WHERE chain_id=@chain AND signer=@signer", ("next", nonce + 1), ("chain", t.Event.DestinationChain), ("signer", Abi.Equal(t.DestinationSigner)))) await increment.ExecuteNonQueryAsync(ct);
        await transaction.CommitAsync(ct);
        t.DestinationNonce = nonce;
        t.GasPrice = gasPrice;
    }

    public async Task<int> RecentAttemptsAsync(long destinationChain, CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var command = Command(connection, "SELECT count(*)::integer FROM bridge.attempts WHERE destination_chain=@chain AND attempted_at>now()-interval '1 minute'", ("chain", destinationChain));
        return (int)(await command.ExecuteScalarAsync(ct))!;
    }

    public async Task<IReadOnlyList<Transfer>> CanonicalAtAsync(IReadOnlyDictionary<long, long> heights, CancellationToken ct)
    {
        var result = new List<Transfer>();
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        foreach (var (chain, height) in heights)
        {
            await using var command = Command(connection, SelectTransfer + """
                 WHERE source_chain=@chain AND source_block<=@height AND EXISTS(SELECT 1 FROM bridge.observations o
                 WHERE o.transfer_id=bridge.transfers.id AND o.block_hash=bridge.transfers.source_block_hash AND o.canonical)
                """, ("chain", chain), ("height", height));
            await using var reader = await command.ExecuteReaderAsync(ct);
            while (await reader.ReadAsync(ct)) result.Add(ReadTransfer(reader));
        }
        return result;
    }

    public async Task<TransferSummary> SummaryAsync(CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        var counts = States.All.ToDictionary(x => x, _ => 0L);
        await using (var command = Command(connection, "SELECT state,count(*) FROM bridge.transfers GROUP BY state"))
        await using (var reader = await command.ExecuteReaderAsync(ct))
            while (await reader.ReadAsync(ct)) counts[reader.GetString(0)] = reader.GetInt64(1);
        await using var pending = Command(connection, "SELECT COALESCE(EXTRACT(EPOCH FROM now()-min(observed_at))::float8,0),COALESCE(sum(attempts)::bigint,0) FROM bridge.transfers WHERE state NOT IN ('destination_finalized','rejected')");
        await using var p = await pending.ExecuteReaderAsync(ct);
        await p.ReadAsync(ct);
        return new(counts, p.GetDouble(0), p.GetInt64(1));
    }

    public async Task SaveReconciliationAsync(Reconciliation value, CancellationToken ct)
    {
        await using var connection = await dataSource.OpenConnectionAsync(ct);
        await using var insert = Command(connection, "INSERT INTO bridge.reconciliations(observed_at,state,report) VALUES(@at,@state,CAST(@report AS jsonb))", ("at", value.UpdatedUtc), ("state", value.State), ("report", JsonSerializer.Serialize(value, BridgeConfig.Json)));
        await insert.ExecuteNonQueryAsync(ct);
    }
}
