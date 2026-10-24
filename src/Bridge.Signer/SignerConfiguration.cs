using System.Numerics;
using System.Text.Json;

namespace Bridge.Signer;

public sealed record NetworkPolicy(long ChainId, string BridgeAddress, string TokenAddress,
    string SignerAddress, string KeyFile, BigInteger MaxTransfer, int GasLimit, BigInteger MaxGasPriceWei);

public sealed class SignerConfiguration
{
    public string Profile { get; }
    public IReadOnlyDictionary<long, NetworkPolicy> Networks { get; }

    private SignerConfiguration(string profile, Dictionary<long, NetworkPolicy> networks)
    {
        Profile = profile;
        Networks = networks.AsReadOnly();
    }

    public static SignerConfiguration Load(string path)
    {
        if (new FileInfo(path).Length > 65_536)
            throw new SignerConfigurationException();
        return Parse(File.ReadAllBytes(path));
    }

    public static SignerConfiguration Parse(ReadOnlyMemory<byte> json)
    {
        try
        {
            using var doc = JsonDocument.Parse(json, new JsonDocumentOptions { MaxDepth = 16 });
            StrictJson.RejectDuplicateProperties(doc.RootElement);
            var root = doc.RootElement;
            string profile = root.GetProperty("profile").GetString() ?? "";
            long[] expected = profile switch
            {
                "local-fast" => [31337, 31338],
                "local-besu" => [31339, 31340],
                _ => throw new SignerConfigurationException()
            };
            var entries = root.GetProperty("networks");
            if (entries.ValueKind != JsonValueKind.Array || entries.GetArrayLength() != 2)
                throw new SignerConfigurationException();
            var networks = new Dictionary<long, NetworkPolicy>();
            var paths = new HashSet<string>(OperatingSystem.IsWindows() ? StringComparer.OrdinalIgnoreCase : StringComparer.Ordinal);
            foreach (var entry in entries.EnumerateArray())
            {
                var chainId = entry.GetProperty("chainId").GetInt64();
                var bridge = HexFields.Address(entry.GetProperty("bridgeAddress").GetString());
                var token = HexFields.Address(entry.GetProperty("tokenAddress").GetString());
                var signer = HexFields.Address(entry.GetProperty("signerAddress").GetString());
                var keyFile = entry.GetProperty("keyFile").GetString() ?? "";
                var maxTransfer = DecimalFields.Parse(entry.GetProperty("maxTransfer").GetString(), DecimalFields.MaxUint256);
                var gasLimit = entry.GetProperty("gasLimit").GetInt32();
                var maxGasPrice = DecimalFields.Parse(entry.GetProperty("maxGasPriceWei").GetString(), SigningPolicy.AbsoluteMaxGasPriceWei);
                if (!expected.Contains(chainId) || !Path.IsPathFullyQualified(keyFile) ||
                    !paths.Add(Path.GetFullPath(keyFile)) || maxTransfer <= 0 ||
                    gasLimit < 21_000 || gasLimit > SigningPolicy.AbsoluteMaxGasLimit || bridge == token)
                    throw new SignerConfigurationException();
                if (!networks.TryAdd(chainId, new NetworkPolicy(chainId, bridge, token, signer,
                        Path.GetFullPath(keyFile), maxTransfer, gasLimit, maxGasPrice)))
                    throw new SignerConfigurationException();
            }
            if (!expected.All(networks.ContainsKey)) throw new SignerConfigurationException();
            return new SignerConfiguration(profile, networks);
        }
        catch (Exception exc) when (exc is JsonException or KeyNotFoundException or InvalidOperationException
                                   or FormatException or OverflowException or PolicyRejectedException or ArgumentException)
        {
            // Ne propager aucun extrait de fichier, adresse ou chemin de clé dans une erreur.
            throw new SignerConfigurationException();
        }
    }
}

public sealed class SignerConfigurationException : Exception
{
    public SignerConfigurationException() : base("signer_configuration_invalid") { }
}

internal static class StrictJson
{
    public static void RejectDuplicateProperties(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var property in element.EnumerateObject())
            {
                if (!names.Add(property.Name)) throw new JsonException();
                RejectDuplicateProperties(property.Value);
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in element.EnumerateArray()) RejectDuplicateProperties(item);
        }
    }
}
