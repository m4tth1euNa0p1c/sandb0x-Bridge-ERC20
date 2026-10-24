using System.Globalization;
using System.Numerics;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Nethereum.Util;

namespace Bridge.Relayer;

public static partial class Abi
{
    [GeneratedRegex("^0x[0-9a-fA-F]{40}$")]
    private static partial Regex AddressRegex();
    [GeneratedRegex("^0x[0-9a-fA-F]{64}$")]
    private static partial Regex HashRegex();
    public static string Hash(byte[] bytes) => "0x" + Convert.ToHexString(Sha3Keccack.Current.CalculateHash(bytes)).ToLowerInvariant();
    public static string Hash(string text) => Hash(Encoding.UTF8.GetBytes(text));
    public static string Hex(long value) => "0x" + value.ToString("x", CultureInfo.InvariantCulture);
    public static string Equal(string value) => value.ToLowerInvariant();
    public static bool Same(string a, string b) => string.Equals(a, b, StringComparison.OrdinalIgnoreCase);
    public static string RequireAddress(string value)
    {
        if (!AddressRegex().IsMatch(value) || value[2..].All(c => c == '0')) throw new ConfigurationException("invalid_address");
        return value.ToLowerInvariant();
    }
    public static string RequireHash(string value)
    {
        if (!HashRegex().IsMatch(value)) throw new ConfigurationException("invalid_hash");
        return value.ToLowerInvariant();
    }
    public static BigInteger Number(string hex)
    {
        if (!hex.StartsWith("0x", StringComparison.Ordinal) || hex.Length <= 2 || hex[2..].Any(c => !Uri.IsHexDigit(c))) throw new RpcFailure("invalid_hex_integer", false);
        return BigInteger.Parse("0" + hex[2..], NumberStyles.AllowHexSpecifier, CultureInfo.InvariantCulture);
    }
    public static string Word(BigInteger value)
    {
        if (value < 0 || value >= BigInteger.One << 256) throw new ConfigurationException("uint256_out_of_range");
        return value.ToString("x", CultureInfo.InvariantCulture).TrimStart('0').PadLeft(64, '0');
    }
    public static string AddressWord(string address) => RequireAddress(address)[2..].PadLeft(64, '0');
    public static string Call(string signature, params string[] words) => Hash(signature)[..10] + string.Concat(words);
    public static string[] Words(string hex)
    {
        if (!hex.StartsWith("0x", StringComparison.Ordinal) || (hex.Length - 2) % 64 != 0 || hex[2..].Any(c => !Uri.IsHexDigit(c))) throw new RpcFailure("invalid_abi_words", false);
        return Enumerable.Range(0, (hex.Length - 2) / 64).Select(i => hex.Substring(2 + i * 64, 64)).ToArray();
    }
    public static string WordAddress(string value)
    {
        if (value.Length != 64 || value[..24].Any(c => c != '0')) throw new RpcFailure("invalid_abi_address", false);
        return RequireAddress("0x" + value[24..]);
    }
    public static readonly string InitiatedTopic = Hash("TransferInitiated(bytes32,uint256,address,address,address,address,address,uint256,uint256)");
    public static readonly string CompletedTopic = Hash("TransferCompleted(bytes32,address,uint256)");
    public static string TransferId(NetworkConfig source, NetworkConfig destination, BigInteger nonce, BigInteger amount, string recipient) =>
        Hash(Convert.FromHexString(Hash("T3L4N_BRIDGE_BURN_MINT")[2..] + Word(1) + Word(source.ChainId) + AddressWord(source.BridgeAddress) + Word(destination.ChainId) + AddressWord(destination.BridgeAddress) + AddressWord(source.TokenAddress) + AddressWord(destination.TokenAddress) + Word(nonce) + Word(amount) + AddressWord(recipient)));
    public static string CompletionData(NetworkConfig source, SourceEvent transfer) => Call("completeTransfer(uint256,address,address,uint256,uint256,address)",
        Word(source.ChainId), AddressWord(source.BridgeAddress), AddressWord(source.TokenAddress), Word(transfer.SourceNonce), Word(transfer.Amount), AddressWord(transfer.Recipient));

    public static SourceEvent DecodeEvent(JsonElement log, NetworkConfig source, NetworkConfig destination)
    {
        if (log.TryGetProperty("removed", out var removed) && removed.GetBoolean()) throw new RpcFailure("removed_log_in_canonical_batch", false);
        if (!Same(log.GetProperty("address").GetString()!, source.BridgeAddress)) throw new RpcFailure("wrong_log_address", false);
        var topics = log.GetProperty("topics").EnumerateArray().Select(x => x.GetString()!).ToArray();
        var words = Words(log.GetProperty("data").GetString()!);
        if (topics.Length != 4 || words.Length != 6 || !Same(topics[0], InitiatedTopic) || Number(topics[2]) != destination.ChainId)
            throw new RpcFailure("wrong_event_domain", false);
        var recipient = WordAddress(words[0]);
        if (!Same(WordAddress(words[1]), source.TokenAddress) || !Same(WordAddress(words[2]), destination.TokenAddress) || !Same(WordAddress(words[3]), destination.BridgeAddress))
            throw new RpcFailure("wrong_event_pair", false);
        var nonce = Number("0x" + words[4]);
        var amount = Number("0x" + words[5]);
        if (amount <= 0 || amount > source.AmountLimit || amount > destination.AmountLimit || nonce > 1000000)
            throw new RpcFailure("event_limits_exceeded", false);
        var id = RequireHash(topics[1]);
        if (!Same(id, TransferId(source, destination, nonce, amount, recipient))) throw new RpcFailure("transfer_id_mismatch", false);
        return new(id, source.ChainId, destination.ChainId, checked((long)Number(log.GetProperty("blockNumber").GetString()!)),
            RequireHash(log.GetProperty("blockHash").GetString()!), RequireHash(log.GetProperty("transactionHash").GetString()!),
            checked((long)Number(log.GetProperty("logIndex").GetString()!)), recipient, nonce, amount);
    }
}
