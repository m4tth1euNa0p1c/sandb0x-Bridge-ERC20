using System.Net;
using System.Text.Json;
using Bridge.Relayer;

namespace Bridge.Relayer.Tests;

public sealed class TransportTests
{
    private sealed class Handler(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> handle) : HttpMessageHandler
    { protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken token) => handle(request, token); }

    [Fact]
    public async Task UnavailableRpcIsSanitizedWithoutProviderCredentials()
    {
        using var http = new HttpClient(new Handler((_, _) => throw new HttpRequestException("password=secret-sentinel")));
        var error = await Assert.ThrowsAsync<RpcFailure>(() => new EthereumRpc(http).CallAsync(new Fixture().A, "eth_blockNumber", [], default));
        Assert.Equal("rpc_unavailable", error.Message); Assert.DoesNotContain("sentinel", error.ToString());
    }

    [Fact]
    public async Task SlowRpcTimesOutWithoutFallback()
    {
        using var http = new HttpClient(new Handler(async (_, token) => { await Task.Delay(2000, token); return new(HttpStatusCode.OK); })) { Timeout = TimeSpan.FromMilliseconds(30) };
        var error = await Assert.ThrowsAsync<RpcFailure>(() => new EthereumRpc(http).CallAsync(new Fixture().A, "eth_blockNumber", [], default));
        Assert.Equal("rpc_timeout", error.Code); Assert.True(error.Retryable);
    }

    [Fact]
    public async Task ResponseForAnotherRequestIsRejected()
    {
        using var http = new HttpClient(new Handler((_, _) => Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent("{\"jsonrpc\":\"2.0\",\"id\":9999,\"result\":\"0x1\"}") })));
        var error = await Assert.ThrowsAsync<RpcFailure>(() => new EthereumRpc(http).CallAsync(new Fixture().A, "eth_blockNumber", [], default));
        Assert.Equal("rpc_envelope_inconsistent", error.Code); Assert.False(error.Retryable);
    }

    [Fact]
    public async Task RpcErrorDetailsNeverEscapeException()
    {
        using var http = new HttpClient(new Handler(async (request, token) =>
        {
            using var body = JsonDocument.Parse(await request.Content!.ReadAsStringAsync(token));
            return new(HttpStatusCode.OK) { Content = new StringContent(JsonSerializer.Serialize(new { jsonrpc = "2.0", id = body.RootElement.GetProperty("id").GetInt64(), error = new { code = -32000, message = "signed_raw=secret-sentinel", data = "password=secret-sentinel" } })) };
        }));
        var error = await Assert.ThrowsAsync<RpcFailure>(() => new EthereumRpc(http).CallAsync(new Fixture().A, "eth_sendRawTransaction", ["test-payload"], default));
        Assert.Equal("rpc_rejected", error.Message); Assert.DoesNotContain("sentinel", error.ToString());
    }

    [Fact]
    public async Task SignerRateResponseIsExplicitAndDoesNotExposeResponseBody()
    {
        using var http = new HttpClient(new Handler((_, _) => Task.FromResult(new HttpResponseMessage(HttpStatusCode.TooManyRequests) { Content = new StringContent("secret-sentinel") })));
        var request = new SignRequest(31337, "0", "1", 350000, Fixture.Address('1'), "0x");
        var error = await Assert.ThrowsAsync<RpcFailure>(() => new HttpSigner(http, "http://signer:8080", "test-not-a-real-secret").SignAsync(request, default));
        Assert.Equal("signer_rate_limited", error.Code); Assert.DoesNotContain("sentinel", error.ToString());
    }
}
