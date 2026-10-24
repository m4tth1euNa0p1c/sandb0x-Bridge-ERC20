using System.Numerics;
using System.Text.Json;
using Bridge.Relayer;

namespace Bridge.Relayer.Tests;

public sealed class ProtocolTests
{
    [Fact]
    public void TransferIdMatchesIndependentFoundryVector()
    {
        var f = new Fixture();
        using var vector = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "transfer-id-v1.json")));
        var p = vector.RootElement.GetProperty("parameters");
        var source = f.A with { ChainId = long.Parse(p.GetProperty("sourceChainId").GetString()!), BridgeAddress = p.GetProperty("sourceBridge").GetString()!, TokenAddress = p.GetProperty("sourceToken").GetString()! };
        var destination = f.B with { ChainId = long.Parse(p.GetProperty("destinationChainId").GetString()!), BridgeAddress = p.GetProperty("destinationBridge").GetString()!, TokenAddress = p.GetProperty("destinationToken").GetString()! };
        Assert.Equal(vector.RootElement.GetProperty("transferId").GetString(), Abi.TransferId(source, destination, NetworkConfig.Integer(p.GetProperty("nonce").GetString()!), NetworkConfig.Integer(p.GetProperty("amount").GetString()!), p.GetProperty("recipient").GetString()!));
    }

    [Fact]
    public void HugeIntegerUnitsAreExactAndNegativeValuesRejected()
    {
        var units = BigInteger.Pow(10, 30) + 1;
        Assert.Equal(units, Abi.Number("0x" + Abi.Word(units)));
        Assert.Throws<ConfigurationException>(() => Abi.Word(-1));
        Assert.Throws<ConfigurationException>(() => Abi.Word(BigInteger.One << 256));
    }

    [Fact]
    public void ReplayingEventInAnotherContextFailsBeforePersistence()
    {
        var f = new Fixture();
        var log = FakeRpc.Json(FakeRpc.SourceLog(f.A, f.B, f.Event()));
        Assert.Equal(f.Event(), Abi.DecodeEvent(log, f.A, f.B));
        var altered = f.B with { BridgeAddress = Fixture.Address('9') };
        Assert.Throws<RpcFailure>(() => Abi.DecodeEvent(log, f.A, altered));
        Assert.NotEqual(f.Event().Id, Abi.TransferId(f.A with { ChainId = 31339 }, f.B, 0, 10, Fixture.Recipient));
    }

    [Theory]
    [InlineData("integration-testnet")]
    [InlineData("mainnet")]
    [InlineData("unknown")]
    public void NonlocalProfilesFailClosed(string profile) => Assert.Throws<ConfigurationException>(() => (new Fixture().Config with { Profile = profile }).Validate());

    [Theory]
    [InlineData("https://example.org")]
    [InlineData("http://user:token@localhost:8545")]
    [InlineData("http://localhost:8545/?apikey=test")]
    [InlineData("http://169.254.169.254")]
    public void ExternalOrCredentialedRpcIsRefused(string url)
    {
        var f = new Fixture();
        Assert.Throws<ConfigurationException>(() => (f.Config with { Networks = [f.A with { RpcUrl = url }, f.B] }).Validate());
    }

    [Fact]
    public void UnknownFinalityAndZeroDepthCannotFallback()
    {
        var f = new Fixture();
        Assert.Throws<ConfigurationException>(() => (f.Config with { Networks = [f.A with { FinalityMode = "finalized" }, f.B] }).Validate());
        Assert.Throws<ConfigurationException>(() => (f.Config with { Networks = [f.A with { Confirmations = 0 }, f.B] }).Validate());
        Assert.Equal(7, Chain.FinalizedHeight(f.A, 10));
        Assert.Throws<ConfigurationException>(() => Chain.FinalizedHeight(f.A with { FinalityMode = "unsupported" }, 10));
    }

    [Fact]
    public async Task CompleteIdentityValidatedAndWrongDecimalsRejected()
    {
        var f = new Fixture();
        await f.Chain.ValidateIdentity(f.Config, f.A, default);
        f.Rpc.Override = (_, method, p) => method == "eth_call" && FakeRpc.Json(p[0]).GetProperty("data").GetString() == Abi.Call("decimals()") ? FakeRpc.Json("0x" + Abi.Word(6)) : null;
        var error = await Assert.ThrowsAsync<ConfigurationException>(() => f.Chain.ValidateIdentity(f.Config, f.A, default));
        Assert.Equal("token_or_decimals_mismatch", error.Message);
    }

    [Theory]
    [InlineData("eth_chainId", "0x1")]
    [InlineData("web3_clientVersion", "unknown/client")]
    [InlineData("eth_getCode", "0x6002")]
    public async Task ChangedNetworkOrBytecodeBlocksIdentity(string method, string value)
    {
        var f = new Fixture(); f.Rpc.Override = (_, m, _) => m == method ? FakeRpc.Json(value) : null;
        await Assert.ThrowsAsync<ConfigurationException>(() => f.Chain.ValidateIdentity(f.Config, f.A, default));
    }
}
