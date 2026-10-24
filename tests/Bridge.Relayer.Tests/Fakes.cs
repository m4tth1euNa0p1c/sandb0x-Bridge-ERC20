using System.Collections.Concurrent;
using System.Numerics;
using System.Text;
using System.Text.Json;
using Bridge.Relayer;

namespace Bridge.Relayer.Tests;

// These doubles exercise application behavior, never PostgreSQL locking or EVM execution.
internal sealed class Fixture
{
    public static string Address(char c) => "0x" + new string(c, 40);
    public static string Hash(string value) => Abi.Hash(value);
    public static readonly string Recipient = Address('5');
    public BridgeConfig Config { get; }
    public FakeRpc Rpc { get; }
    public FakeStore Store { get; } = new();
    public FakeSigner Signer { get; } = new();
    public Chain Chain { get; }
    public NetworkConfig A => Config.Networks[0];
    public NetworkConfig B => Config.Networks[1];
    public Fixture(int attempts = 12)
    {
        Config = new() { Profile = "local-fast", ReferenceSupply = "1000", PollMilliseconds = 100, MaxAttempts = attempts, Networks = [Network("a",31337,'1','3'), Network("b",31338,'2','4')] };
        Config.Validate();
        Rpc = new(Config);
        Chain = new(Rpc);
        foreach (var n in Config.Networks) Store.Checkpoints[n.ChainId] = new(0, null, 0, 0);
    }
    private static NetworkConfig Network(string name, long id, char bridge, char token) => new()
    {
        Name = name, ChainId = id, GenesisHash = Hash(id + ":0"), ClientPrefix = "anvil", RpcUrl = "http://chain-" + name + ":8545",
        BridgeAddress = Address(bridge), TokenAddress = Address(token), TokenCodeHash = Abi.Hash(Convert.FromHexString("60016000")),
        BridgeCodeHash = Abi.Hash(Convert.FromHexString("60016000")), SignerAddress = Address(name == "a" ? '6' : '7'),
        FinalityMode = "confirmations", Confirmations = 3, MaxTransfer = "1000000000000000000000", MaxGasPriceWei = "100000000000", GasLimit = 350000
    };
    public SourceEvent Event(NetworkConfig? source = null, long nonce = 0, long block = 5, long amount = 10)
    {
        source ??= A;
        var destination = Config.Other(source);
        return new(Abi.TransferId(source, destination, nonce, amount, Recipient), source.ChainId, destination.ChainId, block,
            Rpc.State[source.ChainId].Blocks[block].Hash, Hash(source.ChainId + "tx" + nonce), nonce, Recipient, nonce, amount);
    }
    public Transfer Add(SourceEvent? value = null)
    {
        value ??= Event();
        var transfer = new Transfer { Event = value, DestinationSigner = Config.Network(value.DestinationChain).SignerAddress };
        Store.Transfers[value.Id] = FakeStore.Clone(transfer);
        return transfer;
    }
    public TransferProcessor Processor(IFaults? faults = null) => new(Config, Chain, Store, Signer, faults ?? new NoFaults());
    public Transfer Stored(SourceEvent? source = null) => Store.Transfers[(source ?? Event()).Id];
    public void Due() { foreach (var t in Store.Transfers.Values) t.NextAttempt = DateTimeOffset.MinValue; }
    public void CaughtUp() { foreach (var n in Config.Networks) Store.Checkpoints[n.ChainId] = new(Rpc.State[n.ChainId].Head + 1, DateTimeOffset.UtcNow, Rpc.State[n.ChainId].Head, Rpc.State[n.ChainId].Head - 3); }
}

internal sealed class FakeChainState(long chainId)
{
    public long Head { get; set; } = 20;
    public Dictionary<long, BlockHeader> Blocks { get; } = Enumerable.Range(0, 30).ToDictionary(i => (long)i, i => new BlockHeader(i, Fixture.Hash(chainId + ":" + i), Fixture.Hash(chainId + ":" + (i - 1))));
    public List<SourceEvent> Events { get; } = [];
    public Dictionary<string, Receipt> Receipts { get; } = [];
    public Dictionary<string, Completion> Completed { get; } = [];
    public Dictionary<string, long> Processed { get; } = [];
    public HashSet<string> KnownTransactions { get; } = [];
    public List<string> Broadcasts { get; } = [];
    public long LatestNonce { get; set; }
    public long PendingNonce { get; set; }
    public BigInteger GasPrice { get; set; } = 1;
    public BigInteger Balance { get; set; } = BigInteger.Pow(10, 20);
    public BigInteger Supply { get; set; } = 500;
    public bool Paused { get; set; }
    public bool Automine { get; set; } = true;
    public bool LoseSendResponse { get; set; }
    public bool HideSourceLogs { get; set; }
    public bool DuplicateSourceLogs { get; set; }
    public bool HideCompletionLogs { get; set; }
    public int MintEffects { get; set; }
}

internal sealed class FakeRpc(BridgeConfig config) : IRpc
{
    public Dictionary<long, FakeChainState> State { get; } = config.Networks.ToDictionary(n => n.ChainId, n => new FakeChainState(n.ChainId));
    public Func<NetworkConfig, string, object?[], JsonElement?>? Override { get; set; }
    public static JsonElement Json(object? value) => JsonSerializer.SerializeToElement(value, BridgeConfig.Json);
    public Task<JsonElement> CallAsync(NetworkConfig network, string method, object?[] parameters, CancellationToken ct)
    {
        var custom = Override?.Invoke(network, method, parameters);
        if (custom is not null) return Task.FromResult(custom.Value);
        var state = State[network.ChainId];
        JsonElement result;
        switch (method)
        {
            case "eth_chainId": result = Json(Abi.Hex(network.ChainId)); break;
            case "web3_clientVersion": result = Json("anvil/v1.3.1"); break;
            case "eth_blockNumber": result = Json(Abi.Hex(state.Head)); break;
            case "eth_getBlockByNumber":
                var height = (long)Abi.Number((string)parameters[0]!);
                result = state.Blocks.TryGetValue(height, out var block) && height <= state.Head ? Json(new { number = Abi.Hex(height), hash = block.Hash, parentHash = block.ParentHash }) : Json(null); break;
            case "eth_getCode": result = Json("0x60016000"); break;
            case "eth_getBalance": result = Json("0x" + state.Balance.ToString("x")); break;
            case "eth_gasPrice": result = Json("0x" + state.GasPrice.ToString("x")); break;
            case "eth_getTransactionCount": result = Json(Abi.Hex((string)parameters[1]! == "pending" ? state.PendingNonce : state.LatestNonce)); break;
            case "eth_getTransactionReceipt":
                result = state.Receipts.TryGetValue((string)parameters[0]!, out var receipt) ? Json(new { transactionHash = receipt.TransactionHash, blockNumber = Abi.Hex(receipt.BlockNumber), blockHash = receipt.BlockHash, status = receipt.Success ? "0x1" : "0x0" }) : Json(null); break;
            case "eth_getTransactionByHash": result = state.KnownTransactions.Contains((string)parameters[0]!) ? Json(new { hash = parameters[0] }) : Json(null); break;
            case "eth_call": result = Call(network, Json(parameters[0]).GetProperty("data").GetString()!, (string)parameters[1]!); break;
            case "eth_getLogs":
                var filter = Json(parameters[0]);
                var from = (long)Abi.Number(filter.GetProperty("fromBlock").GetString()!);
                var to = (long)Abi.Number(filter.GetProperty("toBlock").GetString()!);
                if (filter.GetProperty("topics")[0].GetString() == Abi.InitiatedTopic)
                {
                    var events = state.HideSourceLogs ? [] : state.Events.Where(e => e.BlockNumber >= from && e.BlockNumber <= to).ToArray();
                    if (state.DuplicateSourceLogs) events = events.Concat(events).ToArray();
                    result = Json(events.Select(e => SourceLog(config.Network(e.SourceChain), config.Network(e.DestinationChain), e))); 
                }
                else result = Json((state.HideCompletionLogs ? [] : state.Completed.Values.Where(c => c.BlockNumber >= from && c.BlockNumber <= to).ToArray()).Select(c => new { address = network.BridgeAddress, topics = new[] { Abi.CompletedTopic, c.Id, "0x" + Abi.AddressWord(c.Recipient) }, data = "0x" + Abi.Word(c.Amount), blockNumber = Abi.Hex(c.BlockNumber), blockHash = c.BlockHash, removed = false }));
                break;
            case "eth_sendRawTransaction":
                var raw = (string)parameters[0]!;
                state.Broadcasts.Add(raw);
                var hash = Abi.Hash(Convert.FromHexString(raw[2..]));
                if (state.Automine) Mine(network, raw, hash);
                if (state.LoseSendResponse) { state.LoseSendResponse = false; throw new RpcFailure("rpc_timeout"); }
                result = Json(hash); break;
            default: throw new InvalidOperationException("Unsupported test RPC method " + method);
        }
        return Task.FromResult(result);
    }
    private JsonElement Call(NetworkConfig network, string data, string at)
    {
        var s = State[network.ChainId];
        var height = at == "latest" ? s.Head : (long)Abi.Number(at);
        string Word(BigInteger value) => "0x" + Abi.Word(value);
        if (data == Abi.Call("nextNonce()")) return Json(Word(s.Events.Count(e => e.BlockNumber <= height)));
        if (data == Abi.Call("totalSupply()")) return Json(Word(s.Supply));
        if (data == Abi.Call("paused()")) return Json(Word(s.Paused ? 1 : 0));
        if (data.StartsWith(Abi.Call("processed(bytes32)"), StringComparison.Ordinal)) return Json(Word(s.Processed.TryGetValue("0x" + data[10..], out var h) && h <= height ? 1 : 0));
        if (data == Abi.Call("decimals()")) return Json(Word(18));
        if (data == Abi.Call("PROTOCOL_VERSION()")) return Json(Word(1));
        if (data == Abi.Call("localChainId()")) return Json(Word(network.ChainId));
        if (data == Abi.Call("maxTransfer()")) return Json(Word(network.AmountLimit));
        if (data == Abi.Call("token()")) return Json("0x" + Abi.AddressWord(network.TokenAddress));
        if (data.StartsWith(Abi.Call("pairs(uint256)"), StringComparison.Ordinal)) return Json("0x" + Abi.AddressWord(config.Other(network).BridgeAddress) + Abi.AddressWord(config.Other(network).TokenAddress));
        if (data.StartsWith(Abi.Call("hasRole(bytes32,address)"), StringComparison.Ordinal)) return Json(Word(1));
        throw new InvalidOperationException("Unsupported eth_call in fixture");
    }
    private void Mine(NetworkConfig destination, string raw, string hash)
    {
        var s = State[destination.ChainId];
        var request = JsonSerializer.Deserialize<SignRequest>(Encoding.UTF8.GetString(Convert.FromHexString(raw[2..])), BridgeConfig.Json)!;
        var words = Abi.Words("0x" + request.Data[10..]);
        var source = config.Network((long)Abi.Number("0x" + words[0]));
        var nonce = Abi.Number("0x" + words[3]);
        var amount = Abi.Number("0x" + words[4]);
        var recipient = Abi.WordAddress(words[5]);
        var id = Abi.TransferId(source, destination, nonce, amount, recipient);
        var height = s.Head - destination.Confirmations;
        var success = !s.Processed.ContainsKey(id);
        s.Receipts[hash] = new(hash, height, s.Blocks[height].Hash, success);
        if (success)
        {
            s.Processed[id] = height;
            s.Completed[id] = new(id, recipient, amount, height, s.Blocks[height].Hash);
            s.MintEffects++;
        }
        s.LatestNonce = Math.Max(s.LatestNonce, long.Parse(request.Nonce, System.Globalization.CultureInfo.InvariantCulture) + 1);
        s.PendingNonce = s.LatestNonce;
    }
    public static object SourceLog(NetworkConfig source, NetworkConfig destination, SourceEvent e) => new
    {
        address = source.BridgeAddress, topics = new[] { Abi.InitiatedTopic, e.Id, "0x" + Abi.Word(destination.ChainId), "0x" + Abi.AddressWord(Fixture.Address('8')) },
        data = "0x" + Abi.AddressWord(e.Recipient) + Abi.AddressWord(source.TokenAddress) + Abi.AddressWord(destination.TokenAddress) + Abi.AddressWord(destination.BridgeAddress) + Abi.Word(e.SourceNonce) + Abi.Word(e.Amount),
        blockNumber = Abi.Hex(e.BlockNumber), blockHash = e.BlockHash, transactionHash = e.TransactionHash, logIndex = Abi.Hex(e.LogIndex), removed = false
    };
}

internal sealed class FakeSigner : ISigner
{
    public List<SignRequest> Requests { get; } = [];
    public int DelayMilliseconds { get; set; }
    public async Task<SignedPayload> SignAsync(SignRequest request, CancellationToken ct)
    {
        Requests.Add(request);
        if (DelayMilliseconds > 0) await Task.Delay(DelayMilliseconds, ct);
        var raw = JsonSerializer.SerializeToUtf8Bytes(request, BridgeConfig.Json);
        return new("0x" + Convert.ToHexString(raw).ToLowerInvariant(), Abi.Hash(raw), Fixture.Address(request.ChainId == 31337 ? '6' : '7'));
    }
}
internal sealed class NoFaults : IFaults { public void Hit(string point, string transferId) { } }
internal sealed class TestCrash : Exception;
internal sealed class CrashAt(string expected) : IFaults { public void Hit(string point, string transferId) { if (point == expected) throw new TestCrash(); } }

internal sealed class FakeStore : IBridgeStore
{
    private readonly ConcurrentDictionary<(int, long), SemaphoreSlim> _locks = new();
    public Dictionary<long, Checkpoint> Checkpoints { get; } = [];
    public Dictionary<long, List<BlockHeader>> Blocks { get; } = [];
    public Dictionary<string, Transfer> Transfers { get; } = [];
    public Dictionary<long, long> Nonces { get; } = [];
    public List<Reconciliation> Reports { get; } = [];
    public int ReservationCount { get; private set; }
    public int RecentAttempts { get; set; }
    public Task InitializeAsync(BridgeConfig configuration, CancellationToken ct) => Task.CompletedTask;
    public async Task<IAsyncDisposable?> TryLockAsync(int category, long chainId, CancellationToken ct)
    {
        var gate = _locks.GetOrAdd((category, chainId), _ => new(1, 1));
        return await gate.WaitAsync(0, ct) ? new Lease(gate) : null;
    }
    private sealed class Lease(SemaphoreSlim gate) : IAsyncDisposable { public ValueTask DisposeAsync() { gate.Release(); return ValueTask.CompletedTask; } }
    public Task<Checkpoint> CheckpointAsync(NetworkConfig n, CancellationToken ct) => Task.FromResult(Checkpoints[n.ChainId]);
    public Task<IReadOnlyList<BlockHeader>> StoredBlocksAsync(NetworkConfig n, CancellationToken ct) => Task.FromResult<IReadOnlyList<BlockHeader>>(Blocks.GetValueOrDefault(n.ChainId, []).OrderByDescending(x => x.Number).Take(129).ToArray());
    public Task RewindAsync(NetworkConfig n, long ancestor, CancellationToken ct)
    {
        foreach (var t in Transfers.Values.Where(t => t.Event.SourceChain == n.ChainId && t.Event.BlockNumber > ancestor)) { t.State = t.DestinationNonce is null ? States.Rejected : States.Intervention; t.ErrorCode = "source_reorg"; }
        Blocks[n.ChainId] = Blocks.GetValueOrDefault(n.ChainId, []).Where(b => b.Number <= ancestor).ToList();
        Checkpoints[n.ChainId] = Checkpoints[n.ChainId] with { NextBlock = ancestor + 1 };
        return Task.CompletedTask;
    }
    public Task SaveBatchAsync(NetworkConfig n, IReadOnlyList<BlockHeader> blocks, IReadOnlyList<SourceEvent> events, string signer, long head, long finalized, CancellationToken ct)
    {
        if (!Blocks.ContainsKey(n.ChainId)) Blocks[n.ChainId] = [];
        foreach (var block in blocks) { Blocks[n.ChainId].RemoveAll(b => b.Number == block.Number); Blocks[n.ChainId].Add(block); }
        foreach (var e in events) if (!Transfers.ContainsKey(e.Id)) Transfers[e.Id] = new() { Event = e, DestinationSigner = signer };
        Checkpoints[n.ChainId] = new(blocks.Count == 0 ? Checkpoints[n.ChainId].NextBlock : blocks[^1].Number + 1, DateTimeOffset.UtcNow, head, finalized);
        return Task.CompletedTask;
    }
    public Task<Transfer?> NextAsync(NetworkConfig destination, CancellationToken ct)
    {
        if (Transfers.Values.Any(t => t.Event.DestinationChain == destination.ChainId && t.State == States.Intervention && t.DestinationNonce is not null)) return Task.FromResult<Transfer?>(null);
        var result = Transfers.Values.Where(t => t.Event.DestinationChain == destination.ChainId && t.State is not (States.Finalized or States.Rejected or States.Intervention)).OrderBy(t => t.DestinationNonce ?? long.MaxValue).ThenBy(t => t.ObservedAt).FirstOrDefault();
        return Task.FromResult(result is null ? null : Clone(result));
    }
    public Task SaveAsync(Transfer transfer, CancellationToken ct) { Transfers[transfer.Event.Id] = Clone(transfer); return Task.CompletedTask; }
    public Task ReserveNonceAsync(Transfer t, long pending, BigInteger gasPrice, CancellationToken ct)
    {
        var nonce = Nonces.GetValueOrDefault(t.Event.DestinationChain, pending);
        if (nonce < pending) throw new RpcFailure("account_nonce_requires_intervention", false);
        t.DestinationNonce = nonce; t.GasPrice = gasPrice;
        Nonces[t.Event.DestinationChain] = nonce + 1; ReservationCount++;
        return SaveAsync(t, ct);
    }
    public Task<int> RecentAttemptsAsync(long destination, CancellationToken ct) => Task.FromResult(RecentAttempts);
    public Task<IReadOnlyList<Transfer>> CanonicalAtAsync(IReadOnlyDictionary<long, long> heights, CancellationToken ct) => Task.FromResult<IReadOnlyList<Transfer>>(Transfers.Values.Where(t => t.Event.BlockNumber <= heights[t.Event.SourceChain] && !(t.State == States.Rejected && t.ErrorCode == "source_reorg")).Select(Clone).ToArray());
    public Task<TransferSummary> SummaryAsync(CancellationToken ct) => Task.FromResult(new TransferSummary(States.All.ToDictionary(s => s, s => (long)Transfers.Values.Count(t => t.State == s)), 0, Transfers.Values.Sum(t => t.Attempts)));
    public Task SaveReconciliationAsync(Reconciliation value, CancellationToken ct) { Reports.Add(value); return Task.CompletedTask; }
    public static Transfer Clone(Transfer t) => new() { Event = t.Event, DestinationSigner = t.DestinationSigner, State = t.State, ErrorCode = t.ErrorCode, Attempts = t.Attempts, DestinationNonce = t.DestinationNonce, GasPrice = t.GasPrice, SignedRaw = t.SignedRaw, DestinationHash = t.DestinationHash, DestinationBlock = t.DestinationBlock, DestinationBlockHash = t.DestinationBlockHash, ObservedAt = t.ObservedAt, UpdatedAt = t.UpdatedAt, LastAttempt = t.LastAttempt, NextAttempt = t.NextAttempt };
}
