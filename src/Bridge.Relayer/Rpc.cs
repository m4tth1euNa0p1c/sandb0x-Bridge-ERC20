using System.Net;
using System.Net.Http.Json;
using System.Numerics;
using System.Text.Json;

namespace Bridge.Relayer;

public sealed class EthereumRpc(HttpClient client) : IRpc
{
    private long _id;
    public async Task<JsonElement> CallAsync(NetworkConfig network, string method, object?[] parameters, CancellationToken ct)
    {
        var id = Interlocked.Increment(ref _id);
        try
        {
            using var response = await client.PostAsJsonAsync(network.RpcUrl, new { jsonrpc = "2.0", id, method, @params = parameters }, ct);
            if (!response.IsSuccessStatusCode) throw new RpcFailure("rpc_http_unavailable");
            using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync(ct));
            var root = document.RootElement;
            if (!root.TryGetProperty("id", out var actualId) || actualId.ValueKind != JsonValueKind.Number || actualId.GetInt64() != id || !root.TryGetProperty("jsonrpc", out var version) || version.GetString() != "2.0") throw new RpcFailure("rpc_envelope_inconsistent", false);
            if (root.TryGetProperty("error", out var error) && error.ValueKind != JsonValueKind.Null)
            {
                var code = error.TryGetProperty("code", out var c) ? c.GetInt32() : 0;
                // Do not retain message/data: a provider may echo raw transactions or credentials.
                throw new RpcFailure(code == -32601 ? "rpc_method_unavailable" : "rpc_rejected", code != -32601);
            }
            if (!root.TryGetProperty("result", out var result)) throw new RpcFailure("rpc_result_missing", false);
            return result.Clone();
        }
        catch (OperationCanceledException) when (!ct.IsCancellationRequested) { throw new RpcFailure("rpc_timeout"); }
        catch (HttpRequestException) { throw new RpcFailure("rpc_unavailable"); }
        catch (JsonException) { throw new RpcFailure("rpc_json_invalid", false); }
    }
}

public sealed class HttpSigner(HttpClient client, string url, string token) : ISigner
{
    public async Task<SignedPayload> SignAsync(SignRequest request, CancellationToken ct)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, url.TrimEnd('/') + "/sign") { Content = JsonContent.Create(request, options: BridgeConfig.Json) };
        message.Headers.Add("X-Bridge-Token", token);
        try
        {
            using var response = await client.SendAsync(message, ct);
            if (response.StatusCode == HttpStatusCode.TooManyRequests) throw new RpcFailure("signer_rate_limited");
            if (!response.IsSuccessStatusCode) throw new RpcFailure("signer_policy_or_availability", (int)response.StatusCode >= 500);
            return await response.Content.ReadFromJsonAsync<SignedPayload>(BridgeConfig.Json, ct) ?? throw new RpcFailure("signer_response_empty", false);
        }
        catch (OperationCanceledException) when (!ct.IsCancellationRequested) { throw new RpcFailure("signer_timeout"); }
        catch (HttpRequestException) { throw new RpcFailure("signer_unavailable"); }
        catch (JsonException) { throw new RpcFailure("signer_response_invalid", false); }
    }
}

public sealed class Chain(IRpc rpc)
{
    public Task<JsonElement> Query(NetworkConfig n, string method, CancellationToken ct, params object?[] p) => rpc.CallAsync(n, method, p, ct);
    public async Task<long> Head(NetworkConfig n, CancellationToken ct) => checked((long)Abi.Number((await Query(n, "eth_blockNumber", ct)).GetString()!));
    public static long FinalizedHeight(NetworkConfig n, long head) => n.FinalityMode switch
    {
        "confirmations" => Math.Max(0, head - n.Confirmations),
        "qbft-local" => head,
        _ => throw new ConfigurationException("no_finality_fallback")
    };
    public async Task<BlockHeader?> Block(NetworkConfig n, long height, CancellationToken ct)
    {
        var b = await Query(n, "eth_getBlockByNumber", ct, Abi.Hex(height), false);
        if (b.ValueKind == JsonValueKind.Null) return null;
        var number = checked((long)Abi.Number(b.GetProperty("number").GetString()!));
        if (number != height) throw new RpcFailure("block_number_mismatch", false);
        return new(number, Abi.RequireHash(b.GetProperty("hash").GetString()!), Abi.RequireHash(b.GetProperty("parentHash").GetString()!));
    }
    public async Task<string> Call(NetworkConfig n, string to, string data, string block, CancellationToken ct) =>
        (await Query(n, "eth_call", ct, new { to, data }, block)).GetString() ?? throw new RpcFailure("eth_call_empty", false);
    public async Task<BigInteger> UInt(NetworkConfig n, string to, string data, string block, CancellationToken ct) => Abi.Number(await Call(n, to, data, block, ct));
    public Task<BigInteger> NextSourceNonce(NetworkConfig n, long height, CancellationToken ct) => UInt(n, n.BridgeAddress, Abi.Call("nextNonce()"), Abi.Hex(height), ct);
    public Task<BigInteger> Supply(NetworkConfig n, long height, CancellationToken ct) => UInt(n, n.TokenAddress, Abi.Call("totalSupply()"), Abi.Hex(height), ct);
    private static bool Boolean(BigInteger value) => value == 0 ? false : value == 1 ? true : throw new RpcFailure("rpc_boolean_invalid", false);
    public async Task<bool> Processed(NetworkConfig n, string id, string block, CancellationToken ct) => Boolean(await UInt(n, n.BridgeAddress, Abi.Call("processed(bytes32)", id[2..]), block, ct));
    public async Task<bool> Paused(NetworkConfig n, CancellationToken ct) => Boolean(await UInt(n, n.BridgeAddress, Abi.Call("paused()"), "latest", ct));
    public async Task<BigInteger> Balance(NetworkConfig n, CancellationToken ct) => Abi.Number((await Query(n, "eth_getBalance", ct, n.SignerAddress, "latest")).GetString()!);
    public async Task<BigInteger> GasPrice(NetworkConfig n, CancellationToken ct) => Abi.Number((await Query(n, "eth_gasPrice", ct)).GetString()!);
    public async Task<long> Nonce(NetworkConfig n, string block, CancellationToken ct) => checked((long)Abi.Number((await Query(n, "eth_getTransactionCount", ct, n.SignerAddress, block)).GetString()!));
    public async Task<Receipt?> Receipt(NetworkConfig n, string hash, CancellationToken ct)
    {
        var r = await Query(n, "eth_getTransactionReceipt", ct, hash);
        if (r.ValueKind == JsonValueKind.Null) return null;
        if (!Abi.Same(r.GetProperty("transactionHash").GetString()!, hash)) throw new RpcFailure("receipt_hash_mismatch", false);
        return new(hash, checked((long)Abi.Number(r.GetProperty("blockNumber").GetString()!)), Abi.RequireHash(r.GetProperty("blockHash").GetString()!), Abi.Number(r.GetProperty("status").GetString()!) == 1);
    }
    public async Task<bool> TransactionKnown(NetworkConfig n, string hash, CancellationToken ct)
    {
        var tx = await Query(n, "eth_getTransactionByHash", ct, hash);
        if (tx.ValueKind == JsonValueKind.Null) return false;
        if (!Abi.Same(tx.GetProperty("hash").GetString()!, hash)) throw new RpcFailure("transaction_hash_mismatch", false);
        return true;
    }
    public async Task Send(NetworkConfig n, SignedPayload signed, CancellationToken ct)
    {
        var hash = (await Query(n, "eth_sendRawTransaction", ct, signed.RawTransaction)).GetString()!;
        if (!Abi.Same(hash, signed.TransactionHash)) throw new RpcFailure("submitted_hash_mismatch", false);
    }
    public async Task<IReadOnlyList<SourceEvent>> Events(NetworkConfig source, NetworkConfig destination, long from, long to, CancellationToken ct)
    {
        var raw = await Query(source, "eth_getLogs", ct, new { address = source.BridgeAddress, fromBlock = Abi.Hex(from), toBlock = Abi.Hex(to), topics = new[] { Abi.InitiatedTopic } });
        if (raw.ValueKind != JsonValueKind.Array) throw new RpcFailure("logs_not_array", false);
        var events = raw.EnumerateArray().Select(x => Abi.DecodeEvent(x, source, destination)).ToArray();
        if (events.Any(e => e.BlockNumber < from || e.BlockNumber > to)) throw new RpcFailure("log_outside_range", false);
        var grouped = events.GroupBy(e => (e.BlockHash, e.TransactionHash, e.LogIndex)).ToArray();
        if (grouped.Any(g => g.Distinct().Count() != 1)) throw new RpcFailure("duplicate_log_conflict", false);
        return grouped.Select(g => g.First()).OrderBy(e => e.BlockNumber).ThenBy(e => e.LogIndex).ToArray();
    }
    public async Task<IReadOnlyList<Completion>> Completions(NetworkConfig network, long to, CancellationToken ct)
    {
        var result = new Dictionary<string, Completion>();
        for (var from = network.StartBlock; from <= to; from += 512)
        {
            var end = Math.Min(to, from + 511);
            var raw = await Query(network, "eth_getLogs", ct, new { address = network.BridgeAddress, fromBlock = Abi.Hex(from), toBlock = Abi.Hex(end), topics = new[] { Abi.CompletedTopic } });
            if (raw.ValueKind != JsonValueKind.Array) throw new RpcFailure("completion_logs_not_array", false);
            foreach (var item in raw.EnumerateArray())
            {
                var topics = item.GetProperty("topics").EnumerateArray().Select(x => x.GetString()!).ToArray();
                var words = Abi.Words(item.GetProperty("data").GetString()!);
                var height = checked((long)Abi.Number(item.GetProperty("blockNumber").GetString()!));
                if (!Abi.Same(item.GetProperty("address").GetString()!, network.BridgeAddress) || topics.Length != 3 || !Abi.Same(topics[0], Abi.CompletedTopic) || words.Length != 1 || height < from || height > end || item.TryGetProperty("removed", out var removed) && removed.GetBoolean())
                    throw new RpcFailure("completion_log_invalid", false);
                var completion = new Completion(Abi.RequireHash(topics[1]), Abi.WordAddress(topics[2][2..]), Abi.Number("0x" + words[0]), height, Abi.RequireHash(item.GetProperty("blockHash").GetString()!));
                if (result.TryGetValue(completion.Id, out var existing) && existing != completion) throw new RpcFailure("completion_duplicate_conflict", false);
                result[completion.Id] = completion;
            }
        }
        return result.Values.ToArray();
    }

    public async Task ValidateIdentity(BridgeConfig config, NetworkConfig n, CancellationToken ct)
    {
        var actualChain = Abi.Number((await Query(n, "eth_chainId", ct)).GetString()!);
        var client = (await Query(n, "web3_clientVersion", ct)).GetString()!;
        var genesis = await Block(n, 0, ct);
        if (actualChain != n.ChainId || !client.Contains(n.ClientPrefix, StringComparison.OrdinalIgnoreCase) || genesis is null || !Abi.Same(genesis.Hash, n.GenesisHash)) throw new ConfigurationException("network_identity_mismatch");
        foreach (var (address, expected) in new[] { (n.TokenAddress, n.TokenCodeHash), (n.BridgeAddress, n.BridgeCodeHash) })
        {
            var code = (await Query(n, "eth_getCode", ct, address, "latest")).GetString()!;
            if (code == "0x" || !Abi.Same(Abi.Hash(Convert.FromHexString(code[2..])), expected)) throw new ConfigurationException("runtime_code_mismatch");
        }
        var other = config.Other(n);
        var pair = Abi.Words(await Call(n, n.BridgeAddress, Abi.Call("pairs(uint256)", Abi.Word(other.ChainId)), "latest", ct));
        if (pair.Length != 2 || !Abi.Same(Abi.WordAddress(pair[0]), other.BridgeAddress) || !Abi.Same(Abi.WordAddress(pair[1]), other.TokenAddress)) throw new ConfigurationException("configured_pair_mismatch");
        var token = Abi.Words(await Call(n, n.BridgeAddress, Abi.Call("token()"), "latest", ct));
        if (token.Length != 1 || !Abi.Same(Abi.WordAddress(token[0]), n.TokenAddress) || await UInt(n, n.TokenAddress, Abi.Call("decimals()"), "latest", ct) != 18) throw new ConfigurationException("token_or_decimals_mismatch");
        if (await UInt(n, n.BridgeAddress, Abi.Call("PROTOCOL_VERSION()"), "latest", ct) != 1 || await UInt(n, n.BridgeAddress, Abi.Call("localChainId()"), "latest", ct) != n.ChainId || n.AmountLimit > await UInt(n, n.BridgeAddress, Abi.Call("maxTransfer()"), "latest", ct)) throw new ConfigurationException("protocol_or_limit_mismatch");
        if (await UInt(n, n.BridgeAddress, Abi.Call("hasRole(bytes32,address)", Abi.Hash("EXECUTOR_ROLE")[2..], Abi.AddressWord(n.SignerAddress)), "latest", ct) != 1 || await UInt(n, n.TokenAddress, Abi.Call("hasRole(bytes32,address)", Abi.Hash("BRIDGE_ROLE")[2..], Abi.AddressWord(n.BridgeAddress)), "latest", ct) != 1) throw new ConfigurationException("required_role_missing");
    }
}
