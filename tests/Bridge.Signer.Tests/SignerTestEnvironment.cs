using System.Numerics;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using Bridge.Signer;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.TestHost;
using Nethereum.Util;

namespace Bridge.Signer.Tests;

internal sealed class SignerTestEnvironment : IDisposable
{
    public const string BridgeA = "0x1111111111111111111111111111111111111111";
    public const string BridgeB = "0x2222222222222222222222222222222222222222";
    public const string TokenA = "0x3333333333333333333333333333333333333333";
    public const string TokenB = "0x4444444444444444444444444444444444444444";
    public const string Recipient = "0x5555555555555555555555555555555555555555";
    private readonly string _temporaryRoot;
    public string KeyA { get; }
    public string KeyB { get; }
    public string AddressA { get; }
    public string AddressB { get; }
    public string Token { get; } = Convert.ToHexString(RandomNumberGenerator.GetBytes(32)).ToLowerInvariant();
    public ManualTimeProvider Clock { get; } = new();
    public JsonObject ConfigurationJson { get; }
    public SignerConfiguration Configuration => SignerConfiguration.Parse(JsonSerializer.SerializeToUtf8Bytes(ConfigurationJson));

    public SignerTestEnvironment(string profile = "local-fast")
    {
        _temporaryRoot = Path.Combine(Path.GetTempPath(), "t3l4n-signer-test-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_temporaryRoot);
        KeyA = Path.Combine(_temporaryRoot, "key_a");
        KeyB = Path.Combine(_temporaryRoot, "key_b");
        AddressA = FileKeySigner.GenerateNewKey(KeyA);
        AddressB = FileKeySigner.GenerateNewKey(KeyB);
        var baseId = profile == "local-besu" ? 31339 : 31337;
        ConfigurationJson = new JsonObject
        {
            ["profile"] = profile,
            ["referenceSupply"] = "1000000000000000000000000",
            ["networks"] = new JsonArray(Network(baseId, BridgeA, TokenA, AddressA, KeyA),
                                        Network(baseId + 1, BridgeB, TokenB, AddressB, KeyB))
        };
    }

    private static JsonObject Network(long id, string bridge, string token, string signer, string keyFile) => new()
    {
        ["chainId"] = id, ["bridgeAddress"] = bridge, ["tokenAddress"] = token,
        ["signerAddress"] = signer, ["keyFile"] = keyFile,
        ["maxTransfer"] = "1000000000000000000000", ["gasLimit"] = 350000, ["maxGasPriceWei"] = "100000000000"
    };

    public SigningService Service() => new(Configuration, new TokenAuthenticator(Token),
        Configuration.Networks.Values.ToDictionary(n => n.ChainId, n => (ITransactionSignerBackend)new FileKeySigner(n.KeyFile)), Clock);

    public async Task<(WebApplication App, HttpClient Client, SigningService Service)> Http()
    {
        var service = Service();
        var app = SignerApplication.Build(service, configure: builder => builder.WebHost.UseTestServer());
        await app.StartAsync();
        return (app, app.GetTestClient(), service);
    }

    public SignRequest Request(long? chainId = null)
    {
        var destination = chainId ?? Configuration.Networks.Keys.Min();
        var remote = Configuration.Networks.Values.Single(n => n.ChainId != destination);
        return new SignRequest(destination, "7", "1000000000", 350000,
            Configuration.Networks[destination].BridgeAddress,
            Calldata(remote.ChainId, remote.BridgeAddress, remote.TokenAddress, 0, 123, Recipient));
    }

    // Encodage indépendant du décodeur de politique : signature Keccak + six mots ABI.
    public static string Calldata(BigInteger sourceChain, string sourceBridge, string sourceToken,
        BigInteger sourceNonce, BigInteger amount, string recipient)
    {
        var selector = Sha3Keccack.Current.CalculateHash("completeTransfer(uint256,address,address,uint256,uint256,address)")[..8];
        static string Number(BigInteger x) => Convert.ToHexString(x.ToByteArray(isUnsigned: true, isBigEndian: true)).PadLeft(64, '0').ToLowerInvariant();
        static string Address(string x) => x[2..].PadLeft(64, '0');
        return "0x" + selector + Number(sourceChain) + Address(sourceBridge) + Address(sourceToken) +
            Number(sourceNonce) + Number(amount) + Address(recipient);
    }

    public void Dispose()
    {
        var full = Path.GetFullPath(_temporaryRoot);
        var allowed = Path.GetFullPath(Path.GetTempPath());
        if (!full.StartsWith(allowed, StringComparison.OrdinalIgnoreCase) ||
            !Path.GetFileName(full).StartsWith("t3l4n-signer-test-", StringComparison.Ordinal))
            throw new InvalidOperationException("Test cleanup outside temporary scope");
        Directory.Delete(full, recursive: true);
    }
}

internal sealed class ManualTimeProvider : TimeProvider
{
    private long _timestamp;
    public override long TimestampFrequency => TimeSpan.TicksPerSecond;
    public override long GetTimestamp() => Interlocked.Read(ref _timestamp);
    public void Advance(TimeSpan duration) => Interlocked.Add(ref _timestamp, duration.Ticks);
}
