using System.Globalization;
using System.Numerics;
using Nethereum.Util;

namespace Bridge.Signer;

public sealed record SignRequest(long ChainId, string Nonce, string GasPriceWei, int GasLimit, string To, string Data);
public sealed record ValidatedTransaction(long ChainId, BigInteger Nonce, BigInteger GasPriceWei,
    int GasLimit, string To, string Data);
public sealed record SignResponse(string RawTransaction, string TransactionHash, string SignerAddress);

public sealed class PolicyRejectedException : Exception
{
    public PolicyRejectedException() : base("policy_rejected") { }
}

public sealed class RateLimitedException : Exception
{
    public RateLimitedException() : base("rate_limited") { }
}

public sealed class SigningPolicy(SignerConfiguration configuration)
{
    public const int AbsoluteMaxGasLimit = 500_000;
    public const int MaxNonce = 1_000_000;
    public static readonly BigInteger AbsoluteMaxGasPriceWei = new(100_000_000_000L);
    public const string CompleteTransferSignature = "completeTransfer(uint256,address,address,uint256,uint256,address)";
    private static readonly byte[] CompleteTransferSelector = Convert.FromHexString(
        Sha3Keccack.Current.CalculateHash(CompleteTransferSignature)[..8]);

    public ValidatedTransaction Validate(SignRequest request)
    {
        if (!configuration.Networks.TryGetValue(request.ChainId, out var destination))
            throw new PolicyRejectedException();
        if (HexFields.Address(request.To) != destination.BridgeAddress)
            throw new PolicyRejectedException();
        var nonce = DecimalFields.Parse(request.Nonce, MaxNonce);
        var gasPrice = DecimalFields.Parse(request.GasPriceWei, destination.MaxGasPriceWei);
        if (request.GasLimit < 21_000 || request.GasLimit > destination.GasLimit)
            throw new PolicyRejectedException();

        // Signature à six paramètres statiques : 4 octets + exactement 6 mots de 32 octets.
        var bytes = HexFields.Bytes(request.Data, 4 + 6 * 32);
        if (!bytes.AsSpan(0, 4).SequenceEqual(CompleteTransferSelector)) throw new PolicyRejectedException();
        var remote = configuration.Networks.Values.Single(n => n.ChainId != destination.ChainId);
        if (Word(bytes, 0) != remote.ChainId || AddressWord(bytes, 1) != remote.BridgeAddress ||
            AddressWord(bytes, 2) != remote.TokenAddress || Word(bytes, 3) > MaxNonce)
            throw new PolicyRejectedException();
        var amount = Word(bytes, 4);
        if (amount <= 0 || amount > destination.MaxTransfer || amount > remote.MaxTransfer)
            throw new PolicyRejectedException();
        _ = AddressWord(bytes, 5); // Refus de zéro et du padding non canonique.
        var intrinsicGas = 21_000 + bytes.Sum(b => b == 0 ? 4 : 16);
        if (request.GasLimit < intrinsicGas) throw new PolicyRejectedException();
        return new ValidatedTransaction(request.ChainId, nonce, gasPrice, request.GasLimit,
            destination.BridgeAddress, "0x" + Convert.ToHexString(bytes).ToLowerInvariant());
    }

    private static BigInteger Word(byte[] data, int index) =>
        new(data.AsSpan(4 + index * 32, 32), isUnsigned: true, isBigEndian: true);

    private static string AddressWord(byte[] data, int index)
    {
        var word = data.AsSpan(4 + index * 32, 32);
        foreach (var b in word[..12])
            if (b != 0) throw new PolicyRejectedException();
        return HexFields.Address("0x" + Convert.ToHexString(word[12..]).ToLowerInvariant());
    }
}

internal static class DecimalFields
{
    internal static readonly BigInteger MaxUint256 = (BigInteger.One << 256) - 1;

    internal static BigInteger Parse(string? value, BigInteger maximum)
    {
        if (string.IsNullOrEmpty(value) || value.Length > 78 ||
            value.Any(c => c is < '0' or > '9') || (value.Length > 1 && value[0] == '0') ||
            !BigInteger.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out var parsed) ||
            parsed > maximum)
            throw new PolicyRejectedException();
        return parsed;
    }
}

internal static class HexFields
{
    internal static byte[] Bytes(string? value, int size)
    {
        if (value is null || value.Length != 2 + 2 * size || !value.StartsWith("0x", StringComparison.Ordinal))
            throw new PolicyRejectedException();
        try { return Convert.FromHexString(value.AsSpan(2)); }
        catch (FormatException) { throw new PolicyRejectedException(); }
    }

    internal static string Address(string? value)
    {
        var bytes = Bytes(value, 20);
        if (bytes.All(b => b == 0)) throw new PolicyRejectedException();
        return "0x" + Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
