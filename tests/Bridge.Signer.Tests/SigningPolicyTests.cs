using System.Numerics;
using System.Text.Json;
using Bridge.Signer;
using Nethereum.Model;
using Nethereum.Signer;
using Nethereum.Util;
using Xunit;

namespace Bridge.Signer.Tests;

public sealed class SigningPolicyTests
{
    [Theory]
    [InlineData("local-fast", 31337)]
    [InlineData("local-fast", 31338)]
    [InlineData("local-besu", 31339)]
    [InlineData("local-besu", 31340)]
    public void Valid_request_signs_the_expected_eip155_transaction(string profile, long chainId)
    {
        using var fixture = new SignerTestEnvironment(profile);
        using var service = fixture.Service();
        var request = fixture.Request(chainId);
        var signed = service.Sign(request);
        var tx = Assert.IsType<LegacyTransactionChainId>(TransactionFactory.CreateTransaction(signed.RawTransaction));
        Assert.True(tx.VerifyTransaction());
        Assert.Equal(signed.SignerAddress, tx.GetSenderAddress(), ignoreCase: true);
        Assert.Equal(chainId, tx.GetChainIdAsBigInteger());
        Assert.Equal(new BigInteger(7), new BigInteger(tx.Nonce, isUnsigned: true, isBigEndian: true));
        Assert.Equal(BigInteger.Zero, new BigInteger(tx.Value, isUnsigned: true, isBigEndian: true));
        Assert.Equal(new BigInteger(350000), new BigInteger(tx.GasLimit, isUnsigned: true, isBigEndian: true));
        Assert.Equal(request.To[2..], Convert.ToHexString(tx.ReceiveAddress), ignoreCase: true);
        Assert.Equal(request.Data[2..], Convert.ToHexString(tx.Data), ignoreCase: true);
        var expectedHash = "0x" + Convert.ToHexString(Sha3Keccack.Current.CalculateHash(Convert.FromHexString(signed.RawTransaction[2..]))).ToLowerInvariant();
        Assert.Equal(expectedHash, signed.TransactionHash);
        var again = service.Sign(request);
        Assert.True(signed.RawTransaction == again.RawTransaction, "La même demande doit produire les mêmes octets signés.");
    }

    public static IEnumerable<object[]> InvalidRequests()
    {
        yield return ["mainnet", (Func<SignRequest, SignRequest>)(r => r with { ChainId = 1 })];
        yield return ["unknown chain", (Func<SignRequest, SignRequest>)(r => r with { ChainId = 12345 })];
        yield return ["other destination", (Func<SignRequest, SignRequest>)(r => r with { To = SignerTestEnvironment.TokenA })];
        yield return ["bad address", (Func<SignRequest, SignRequest>)(r => r with { To = "0x123" })];
        yield return ["negative nonce", (Func<SignRequest, SignRequest>)(r => r with { Nonce = "-1" })];
        yield return ["decimal nonce", (Func<SignRequest, SignRequest>)(r => r with { Nonce = "1.5" })];
        yield return ["noncanonical nonce", (Func<SignRequest, SignRequest>)(r => r with { Nonce = "01" })];
        yield return ["oversized nonce", (Func<SignRequest, SignRequest>)(r => r with { Nonce = "1000001" })];
        yield return ["negative gas price", (Func<SignRequest, SignRequest>)(r => r with { GasPriceWei = "-1" })];
        yield return ["high gas price", (Func<SignRequest, SignRequest>)(r => r with { GasPriceWei = "100000000001" })];
        yield return ["high gas", (Func<SignRequest, SignRequest>)(r => r with { GasLimit = 350001 })];
        yield return ["intrinsic gas missing", (Func<SignRequest, SignRequest>)(r => r with { GasLimit = 21000 })];
        yield return ["wrong selector", (Func<SignRequest, SignRequest>)(r => r with { Data = "0xffffffff" + r.Data[10..] })];
        yield return ["trailing data", (Func<SignRequest, SignRequest>)(r => r with { Data = r.Data + "00" })];
        yield return ["short data", (Func<SignRequest, SignRequest>)(r => r with { Data = r.Data[..^2] })];
        yield return ["nonhex data", (Func<SignRequest, SignRequest>)(r => r with { Data = r.Data[..^2] + "ZZ" })];
    }

    [Theory]
    [MemberData(nameof(InvalidRequests))]
    public void Policy_rejects_out_of_scope_requests(string scenario, Func<SignRequest, SignRequest> change)
    {
        using var fixture = new SignerTestEnvironment();
        using var service = fixture.Service();
        var exception = Assert.Throws<PolicyRejectedException>(() => service.Sign(change(fixture.Request())));
        Assert.Equal("policy_rejected", exception.Message);
        Assert.False(string.IsNullOrWhiteSpace(scenario));
    }

    [Theory]
    [InlineData("chain")]
    [InlineData("bridge")]
    [InlineData("token")]
    [InlineData("nonce")]
    [InlineData("zero-amount")]
    [InlineData("high-amount")]
    [InlineData("zero-recipient")]
    [InlineData("address-padding")]
    public void Calldata_domain_and_amount_are_checked(string mutation)
    {
        using var fixture = new SignerTestEnvironment();
        using var service = fixture.Service();
        var data = SignerTestEnvironment.Calldata(mutation == "chain" ? 31337 : 31338,
            mutation == "bridge" ? SignerTestEnvironment.BridgeA : SignerTestEnvironment.BridgeB,
            mutation == "token" ? SignerTestEnvironment.TokenA : SignerTestEnvironment.TokenB,
            mutation == "nonce" ? 1000001 : 0,
            mutation == "zero-amount" ? 0 : mutation == "high-amount" ? BigInteger.Parse("1000000000000000000001") : 123,
            mutation == "zero-recipient" ? "0x" + new string('0', 40) : SignerTestEnvironment.Recipient);
        if (mutation == "address-padding") data = data[..74] + "01" + data[76..];
        Assert.Throws<PolicyRejectedException>(() => service.Sign(fixture.Request() with { Data = data }));
    }

    [Fact]
    public void Zero_gas_price_and_exact_limits_are_supported_for_local_besu()
    {
        using var fixture = new SignerTestEnvironment("local-besu");
        using var service = fixture.Service();
        var request = fixture.Request() with
        {
            Nonce = "1000000", GasPriceWei = "0",
            Data = SignerTestEnvironment.Calldata(31340, SignerTestEnvironment.BridgeB, SignerTestEnvironment.TokenB,
                1000000, BigInteger.Parse("1000000000000000000000"), SignerTestEnvironment.Recipient)
        };
        var response = service.Sign(request);
        Assert.True(TransactionVerificationAndRecovery.VerifyTransaction(response.RawTransaction));
    }

    [Fact]
    public async Task Parallel_requests_cannot_exceed_ten_signatures_per_chain_per_minute()
    {
        using var fixture = new SignerTestEnvironment();
        using var service = fixture.Service();
        var accepted = 0;
        await Task.WhenAll(Enumerable.Range(0, 24).Select(_ => Task.Run(() =>
        {
            try { service.Sign(fixture.Request()); Interlocked.Increment(ref accepted); }
            catch (RateLimitedException) { }
        })));
        Assert.Equal(10, accepted);
        Assert.Throws<RateLimitedException>(() => service.Sign(fixture.Request()));
        // L'autre chaîne a sa propre fenêtre.
        service.Sign(fixture.Request(31338));
        fixture.Clock.Advance(TimeSpan.FromSeconds(59));
        Assert.Throws<RateLimitedException>(() => service.Sign(fixture.Request()));
        fixture.Clock.Advance(TimeSpan.FromSeconds(1));
        service.Sign(fixture.Request());
    }

    [Fact]
    public void Invalid_request_does_not_consume_the_signature_budget()
    {
        using var fixture = new SignerTestEnvironment();
        using var service = fixture.Service();
        for (var i = 0; i < 12; i++)
            Assert.Throws<PolicyRejectedException>(() => service.Sign(fixture.Request() with { ChainId = 1 }));
        for (var i = 0; i < 10; i++) service.Sign(fixture.Request());
    }
}
