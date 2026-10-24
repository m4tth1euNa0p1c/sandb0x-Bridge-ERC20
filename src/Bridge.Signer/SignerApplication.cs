using System.Text.Json;

namespace Bridge.Signer;

public static class SignerApplication
{
    public const int MaxRequestBodyBytes = 4096;
    private static readonly HashSet<string> RequestProperties = ["chainId", "nonce", "gasPriceWei", "gasLimit", "to", "data"];

    public static WebApplication Build(SigningService service, string[]? args = null,
        Action<WebApplicationBuilder>? configure = null)
    {
        var builder = WebApplication.CreateBuilder(new WebApplicationOptions
        {
            Args = args ?? [], EnvironmentName = Environments.Production
        });
        // Aucun middleware de journalisation HTTP ou de payload. Les erreurs applicatives sont bornées.
        builder.Logging.ClearProviders();
        builder.WebHost.UseUrls(Environment.GetEnvironmentVariable("ASPNETCORE_URLS") ?? "http://127.0.0.1:8080");
        builder.WebHost.ConfigureKestrel(options =>
        {
            options.AddServerHeader = false;
            options.Limits.MaxRequestBodySize = MaxRequestBodyBytes;
            options.Limits.MaxRequestHeadersTotalSize = 8192;
            options.Limits.MaxConcurrentConnections = 32;
        });
        configure?.Invoke(builder);
        var app = builder.Build();
        app.MapGet("/health", () => Results.Json(new { status = "available" }));
        app.MapPost("/sign", async (HttpContext context) =>
        {
            context.Response.Headers.CacheControl = "no-store";
            if (!context.Request.Headers.TryGetValue("X-Bridge-Token", out var values) || values.Count != 1 ||
                !service.Authentication.Matches(values[0]))
                return Results.Json(new { error = "unauthorized" }, statusCode: StatusCodes.Status401Unauthorized);
            SignRequest request;
            try
            {
                request = await ParseRequest(context.Request, context.RequestAborted);
            }
            catch (Exception exc) when (exc is JsonException or InvalidOperationException or FormatException or
                                       OverflowException or KeyNotFoundException or BadHttpRequestException)
            {
                return Results.Json(new { error = "invalid_request" }, statusCode: StatusCodes.Status400BadRequest);
            }
            catch (OperationCanceledException) when (context.RequestAborted.IsCancellationRequested)
            {
                return Results.StatusCode(499);
            }
            catch
            {
                return Results.Json(new { error = "signing_failed" }, statusCode: StatusCodes.Status500InternalServerError);
            }
            try
            {
                return Results.Json(service.Sign(request));
            }
            catch (PolicyRejectedException)
            {
                return Results.Json(new { error = "policy_rejected" }, statusCode: StatusCodes.Status403Forbidden);
            }
            catch (RateLimitedException)
            {
                context.Response.Headers.RetryAfter = "60";
                return Results.Json(new { error = "rate_limited" }, statusCode: StatusCodes.Status429TooManyRequests);
            }
            catch (OperationCanceledException) when (context.RequestAborted.IsCancellationRequested)
            {
                return Results.StatusCode(499);
            }
            catch
            {
                return Results.Json(new { error = "signing_failed" }, statusCode: StatusCodes.Status500InternalServerError);
            }
        });
        return app;
    }

    private static async Task<SignRequest> ParseRequest(HttpRequest request, CancellationToken cancellationToken)
    {
        if (!string.Equals(request.ContentType?.Split(';', 2)[0].Trim(), "application/json", StringComparison.OrdinalIgnoreCase) ||
            request.ContentLength > MaxRequestBodyBytes)
            throw new JsonException();
        var bytes = new byte[MaxRequestBodyBytes + 1];
        var length = 0;
        while (length < bytes.Length)
        {
            var read = await request.Body.ReadAsync(bytes.AsMemory(length), cancellationToken);
            if (read == 0) break;
            length += read;
        }
        if (length > MaxRequestBodyBytes) throw new JsonException();
        using var doc = JsonDocument.Parse(bytes.AsMemory(0, length), new JsonDocumentOptions { MaxDepth = 2 });
        var root = doc.RootElement;
        if (root.ValueKind != JsonValueKind.Object) throw new JsonException();
        StrictJson.RejectDuplicateProperties(root);
        if (root.EnumerateObject().Count() != RequestProperties.Count ||
            root.EnumerateObject().Any(p => !RequestProperties.Contains(p.Name)))
            throw new JsonException();
        return new SignRequest(root.GetProperty("chainId").GetInt64(),
            root.GetProperty("nonce").GetString() ?? throw new JsonException(),
            root.GetProperty("gasPriceWei").GetString() ?? throw new JsonException(),
            root.GetProperty("gasLimit").GetInt32(),
            root.GetProperty("to").GetString() ?? throw new JsonException(),
            root.GetProperty("data").GetString() ?? throw new JsonException());
    }
}
