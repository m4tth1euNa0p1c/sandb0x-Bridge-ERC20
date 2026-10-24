using System.Text;
using System.Text.Json;
using Bridge.Signer;
using Xunit;

namespace Bridge.Signer.Tests;

public sealed class ConfigurationAndKeyTests
{
    [Theory]
    [InlineData("integration-testnet")]
    [InlineData("mainnet")]
    [InlineData("unknown")]
    public void Unimplemented_or_unknown_profiles_are_refused(string profile)
    {
        using var fixture = new SignerTestEnvironment();
        fixture.ConfigurationJson["profile"] = profile;
        Assert.Throws<SignerConfigurationException>(() => fixture.Configuration);
    }

    [Theory]
    [InlineData("chainId", "1")]
    [InlineData("gasLimit", "500001")]
    [InlineData("gasLimit", "0")]
    [InlineData("maxGasPriceWei", "100000000001")]
    [InlineData("maxTransfer", "0")]
    [InlineData("maxTransfer", "-1")]
    [InlineData("keyFile", "relative-key")]
    [InlineData("bridgeAddress", "0x0000000000000000000000000000000000000000")]
    public void Invalid_network_policy_is_refused(string field, string value)
    {
        using var fixture = new SignerTestEnvironment();
        var network = fixture.ConfigurationJson["networks"]![0]!;
        network[field] = field is "chainId" or "gasLimit" ? JsonSerializer.SerializeToNode(int.Parse(value)) : value;
        Assert.Throws<SignerConfigurationException>(() => fixture.Configuration);
    }

    [Fact]
    public void Duplicate_json_properties_and_duplicate_key_paths_are_refused()
    {
        using var fixture = new SignerTestEnvironment();
        var json = fixture.ConfigurationJson.ToJsonString();
        json = json.Replace("\"profile\":\"local-fast\"", "\"profile\":\"local-fast\",\"profile\":\"local-besu\"", StringComparison.Ordinal);
        Assert.Throws<SignerConfigurationException>(() => SignerConfiguration.Parse(Encoding.UTF8.GetBytes(json)));
        fixture.ConfigurationJson["networks"]![1]!["keyFile"] = fixture.KeyA;
        Assert.Throws<SignerConfigurationException>(() => fixture.Configuration);
    }

    [Fact]
    public void Wrong_signer_key_identity_refuses_startup()
    {
        using var fixture = new SignerTestEnvironment();
        var tokenPath = Path.Combine(Path.GetDirectoryName(fixture.KeyA)!, "auth-token");
        File.WriteAllText(tokenPath, fixture.Token);
        fixture.ConfigurationJson["networks"]![0]!["signerAddress"] = fixture.AddressB;
        Assert.Throws<SignerConfigurationException>(() => SigningService.Load(fixture.Configuration, tokenPath));
    }

    [Fact]
    public void Generate_key_never_overwrites_and_returns_only_its_public_address()
    {
        using var fixture = new SignerTestEnvironment();
        using var key = new FileKeySigner(fixture.KeyA);
        Assert.Equal(fixture.AddressA, key.Address);
        Assert.NotEqual(fixture.AddressA, fixture.AddressB);
        Assert.Throws<IOException>(() => FileKeySigner.GenerateNewKey(fixture.KeyA));
        using var reread = new FileKeySigner(fixture.KeyA);
        Assert.Equal(fixture.AddressA, reread.Address);
        if (!OperatingSystem.IsWindows())
            Assert.Equal(UnixFileMode.UserRead | UnixFileMode.GroupRead | UnixFileMode.OtherRead,
                File.GetUnixFileMode(fixture.KeyA));
    }

    [Fact]
    public void Authentication_matches_only_the_exact_token()
    {
        using var fixture = new SignerTestEnvironment();
        using var authentication = new TokenAuthenticator(fixture.Token);
        Assert.True(authentication.Matches(fixture.Token));
        Assert.False(authentication.Matches(fixture.Token[..^1]));
        Assert.False(authentication.Matches(fixture.Token + "x"));
        Assert.False(authentication.Matches(null));
        Assert.False(authentication.Matches(""));
        Assert.Throws<SignerConfigurationException>(() => new TokenAuthenticator("short"));
    }
}
