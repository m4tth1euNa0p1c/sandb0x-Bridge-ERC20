using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Bridge.Signer;
using Microsoft.AspNetCore.TestHost;
using Nethereum.Signer;
using Xunit;

namespace Bridge.Signer.Tests;

public sealed class SignerHttpTests
{
    private static readonly JsonSerializerOptions WebJson = new(JsonSerializerDefaults.Web);

    private static HttpRequestMessage Post(string body, string? token)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/sign")
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json")
        };
        if (token is not null) request.Headers.Add("X-Bridge-Token", token);
        return request;
    }

    [Fact]
    public async Task Authorized_http_request_returns_a_recoverable_signature_and_health_is_minimal()
    {
        using var fixture = new SignerTestEnvironment();
        var server = await fixture.Http();
        await using var app = server.App;
        using var client = server.Client;
        using var service = server.Service;
        using var health = await client.GetAsync("/health");
        Assert.Equal(HttpStatusCode.OK, health.StatusCode);
        Assert.True(await health.Content.ReadAsStringAsync() == "{\"status\":\"available\"}");
        using var request = Post(JsonSerializer.Serialize(fixture.Request(), WebJson), fixture.Token);
        using var response = await client.SendAsync(request);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.True(response.Headers.CacheControl?.NoStore);
        var signed = await response.Content.ReadFromJsonAsync<SignResponse>(WebJson);
        Assert.NotNull(signed);
        Assert.Equal(fixture.AddressA, TransactionVerificationAndRecovery.GetSenderAddress(signed.RawTransaction), ignoreCase: true);
        Assert.True(signed.SignerAddress == fixture.AddressA);
        Assert.Equal(66, signed.TransactionHash.Length);
    }

    [Theory]
    [InlineData("missing")]
    [InlineData("wrong")]
    [InlineData("duplicate")]
    public async Task Invalid_authentication_is_rejected_before_body_parsing(string scenario)
    {
        using var fixture = new SignerTestEnvironment();
        var server = await fixture.Http();
        await using var app = server.App;
        using var client = server.Client;
        using var service = server.Service;
        using var request = Post("not-json-auth-must-run-first", scenario == "missing" ? null : scenario == "wrong" ? "invalid" : fixture.Token);
        if (scenario == "duplicate") request.Headers.Add("X-Bridge-Token", fixture.Token);
        using var response = await client.SendAsync(request);
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.True(body == "{\"error\":\"unauthorized\"}", "Réponse d'authentification non minimale.");
        Assert.True(!body.Contains(fixture.Token, StringComparison.Ordinal));
    }

    [Theory]
    [InlineData("malformed")]
    [InlineData("duplicate")]
    [InlineData("extra-value-zero")]
    [InlineData("extra-value-positive")]
    [InlineData("extra-private-key")]
    [InlineData("wrong-number-type")]
    [InlineData("null-data")]
    [InlineData("missing-field")]
    [InlineData("oversized")]
    [InlineData("array")]
    public async Task Request_schema_refuses_ambiguous_or_extra_data_without_echo(string scenario)
    {
        using var fixture = new SignerTestEnvironment();
        var server = await fixture.Http();
        await using var app = server.App;
        using var client = server.Client;
        using var service = server.Service;
        var body = JsonSerializer.Serialize(fixture.Request(), WebJson);
        body = scenario switch
        {
            "malformed" => "{unclosed",
            "duplicate" => body[..^1] + ",\"chainId\":31337}",
            "extra-value-zero" => body[..^1] + ",\"value\":\"0\"}",
            "extra-value-positive" => body[..^1] + ",\"value\":\"1\"}",
            "extra-private-key" => body[..^1] + ",\"privateKey\":\"NON_SECRET_ERROR_CANARY\"}",
            "wrong-number-type" => body.Replace("\"chainId\":31337", "\"chainId\":\"31337\"", StringComparison.Ordinal),
            "null-data" => body.Replace("\"data\":\"" + fixture.Request().Data + "\"", "\"data\":null", StringComparison.Ordinal),
            "missing-field" => body.Replace("\"nonce\":\"7\",", "", StringComparison.Ordinal),
            "oversized" => body + new string(' ', 4096),
            "array" => "[" + body + "]",
            _ => throw new InvalidOperationException()
        };
        using var request = Post(body, fixture.Token);
        using var response = await client.SendAsync(request);
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.True(await response.Content.ReadAsStringAsync() == "{\"error\":\"invalid_request\"}",
            "Une erreur doit rester générique, sans écho des données de la demande.");
    }

    [Fact]
    public async Task Policy_denial_and_frequency_have_distinct_http_statuses()
    {
        using var fixture = new SignerTestEnvironment();
        var server = await fixture.Http();
        await using var app = server.App;
        using var client = server.Client;
        using var service = server.Service;
        using (var denied = Post(JsonSerializer.Serialize(fixture.Request() with { ChainId = 1 }, WebJson), fixture.Token))
        using (var response = await client.SendAsync(denied))
        {
            Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
            Assert.True(await response.Content.ReadAsStringAsync() == "{\"error\":\"policy_rejected\"}");
        }
        for (var i = 0; i < 10; i++)
        {
            using var request = Post(JsonSerializer.Serialize(fixture.Request(), WebJson), fixture.Token);
            using var response = await client.SendAsync(request);
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        }
        using var limited = Post(JsonSerializer.Serialize(fixture.Request(), WebJson), fixture.Token);
        using var result = await client.SendAsync(limited);
        Assert.Equal(HttpStatusCode.TooManyRequests, result.StatusCode);
        Assert.Equal(TimeSpan.FromSeconds(60), result.Headers.RetryAfter?.Delta);
        Assert.True(await result.Content.ReadAsStringAsync() == "{\"error\":\"rate_limited\"}");
    }

    [Theory]
    [InlineData("exception")]
    [InlineData("json")]
    [InlineData("invalid-operation")]
    public async Task Unexpected_backend_failure_is_sanitized(string failure)
    {
        using var fixture = new SignerTestEnvironment();
        using var service = new SigningService(fixture.Configuration, new TokenAuthenticator(fixture.Token),
            new Dictionary<long, ITransactionSignerBackend>
            {
                [31337] = new FailingBackend(fixture.AddressA, failure), [31338] = new FailingBackend(fixture.AddressB, failure)
            });
        await using var app = SignerApplication.Build(service, configure: builder => builder.WebHost.UseTestServer());
        await app.StartAsync();
        using var client = app.GetTestClient();
        using var request = Post(JsonSerializer.Serialize(fixture.Request(), WebJson), fixture.Token);
        using var response = await client.SendAsync(request);
        Assert.Equal(HttpStatusCode.InternalServerError, response.StatusCode);
        Assert.True(await response.Content.ReadAsStringAsync() == "{\"error\":\"signing_failed\"}");
    }

    private sealed class FailingBackend(string address, string failure) : ITransactionSignerBackend
    {
        public string Address => address;
        public string Sign(ValidatedTransaction transaction) => throw (failure switch
        {
            "json" => new JsonException("NON_SECRET_INTERNAL_ERROR_CANARY"),
            "invalid-operation" => new InvalidOperationException("NON_SECRET_INTERNAL_ERROR_CANARY"),
            _ => new Exception("NON_SECRET_INTERNAL_ERROR_CANARY")
        });
        public void Dispose() { }
    }
}
