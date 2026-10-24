using System.Globalization;
using System.Numerics;
using System.Text.Json;

namespace Bridge.Relayer;

public sealed record NetworkConfig
{
    public required string Name { get; init; }
    public required long ChainId { get; init; }
    public required string GenesisHash { get; init; }
    public required string ClientPrefix { get; init; }
    public required string RpcUrl { get; init; }
    public required string TokenAddress { get; init; }
    public required string BridgeAddress { get; init; }
    public required string TokenCodeHash { get; init; }
    public required string BridgeCodeHash { get; init; }
    public required string SignerAddress { get; init; }
    public long StartBlock { get; init; }
    public required string FinalityMode { get; init; }
    public int Confirmations { get; init; } = 3;
    public required string MaxTransfer { get; init; }
    public int GasLimit { get; init; } = 350000;
    public required string MaxGasPriceWei { get; init; }
    // Shared configuration: the relayer never reads KeyFile.
    public string? KeyFile { get; init; }
    public BigInteger AmountLimit => Integer(MaxTransfer);
    public BigInteger GasPriceLimit => Integer(MaxGasPriceWei);
    public static BigInteger Integer(string value) => BigInteger.Parse(value, NumberStyles.None, CultureInfo.InvariantCulture);
}

public sealed record BridgeConfig
{
    public required string Profile { get; init; }
    public required string ReferenceSupply { get; init; }
    public int PollMilliseconds { get; init; } = 1000;
    public int RpcTimeoutSeconds { get; init; } = 5;
    public int MaxAttempts { get; init; } = 12;
    public int Workers { get; init; } = 2;
    public int MaxPerMinute { get; init; } = 10;
    public int PendingTimeoutSeconds { get; init; } = 300;
    public required NetworkConfig[] Networks { get; init; }
    public static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    public static BridgeConfig Load(string path)
    {
        var result = JsonSerializer.Deserialize<BridgeConfig>(File.ReadAllText(path), Json) ?? throw new ConfigurationException("configuration_empty");
        result.Validate();
        return result;
    }

    public void Validate()
    {
        long[] expected = Profile switch
        {
            "local-fast" => [31337, 31338],
            "local-besu" => [31339, 31340],
            _ => throw new ConfigurationException("profile_not_local")
        };
        if (Networks.Length != 2 || !Networks.Select(n => n.ChainId).Order().SequenceEqual(expected))
            throw new ConfigurationException("chain_pair_not_allowed");
        if (Networks.Select(n => n.Name).Distinct().Count() != 2 || Networks.Any(n => n.Name is not ("a" or "b")))
            throw new ConfigurationException("network_names_not_bounded");
        if (PollMilliseconds is < 100 or > 60000 || RpcTimeoutSeconds is < 1 or > 30 || MaxAttempts is < 1 or > 100 || Workers is < 1 or > 8 || MaxPerMinute is < 1 or > 10 || PendingTimeoutSeconds is < 10 or > 3600)
            throw new ConfigurationException("invalid_limits");
        if (NetworkConfig.Integer(ReferenceSupply) <= 0) throw new ConfigurationException("invalid_reference_supply");
        foreach (var n in Networks)
        {
            ValidateLocalUrl(n.RpcUrl, ["chain-a", "chain-b", "rpc-a", "rpc-b", "localhost", "127.0.0.1"]);
            if (n.StartBlock < 0 || n.StartBlock > 10000000 || n.GasLimit is < 21000 or > 500000 || n.GasPriceLimit < 0 || n.GasPriceLimit > BigInteger.Parse("100000000000", CultureInfo.InvariantCulture) || n.AmountLimit <= 0)
                throw new ConfigurationException("invalid_network_limits");
            foreach (var address in new[] { n.TokenAddress, n.BridgeAddress, n.SignerAddress }) Abi.RequireAddress(address);
            foreach (var hash in new[] { n.GenesisHash, n.TokenCodeHash, n.BridgeCodeHash }) Abi.RequireHash(hash);
            var expectedClient = n.ChainId == 31339 ? "besu" : "anvil";
            if (n.ClientPrefix != expectedClient || n.FinalityMode != (expectedClient == "besu" ? "qbft-local" : "confirmations") || n.Confirmations is < 1 or > 128)
                throw new ConfigurationException("finality_not_supported");
        }
    }

    public NetworkConfig Other(NetworkConfig n) => Networks.Single(x => x.ChainId != n.ChainId);
    public NetworkConfig Network(long chainId) => Networks.Single(x => x.ChainId == chainId);
    public string Identity(NetworkConfig n) => Abi.Hash(System.Text.Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new
    { ReferenceSupply, n.ChainId, n.GenesisHash, n.TokenAddress, n.BridgeAddress, n.TokenCodeHash, n.BridgeCodeHash, n.SignerAddress, n.StartBlock, n.FinalityMode, n.Confirmations, n.GasLimit, n.MaxGasPriceWei, n.MaxTransfer }, Json)));

    public static void ValidateLocalUrl(string value, string[] allowedHosts)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri) || uri.Scheme != "http" || !allowedHosts.Contains(uri.Host) || uri.UserInfo.Length != 0 || uri.Query.Length != 0 || uri.Fragment.Length != 0 || uri.AbsolutePath != "/")
            throw new ConfigurationException("nonlocal_or_credentialed_endpoint");
    }
}

public sealed class ConfigurationException(string code) : Exception(code);
public sealed class RpcFailure(string code, bool retryable = true) : Exception(code)
{
    public string Code { get; } = code;
    public bool Retryable { get; } = retryable;
}
