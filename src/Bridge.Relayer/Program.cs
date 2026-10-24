using Bridge.Relayer;
using Npgsql;

try
{
    var configuration = BridgeConfig.Load(Environment.GetEnvironmentVariable("BRIDGE_CONFIG") ?? throw new ConfigurationException("config_path_missing"));
    var signerUrl = Environment.GetEnvironmentVariable("BRIDGE_SIGNER_URL") ?? "http://signer:8080";
    BridgeConfig.ValidateLocalUrl(signerUrl, ["signer", "localhost", "127.0.0.1"]);
    var signerToken = SecretFile("BRIDGE_SIGNER_TOKEN_FILE");
    var dbUser = Environment.GetEnvironmentVariable("BRIDGE_DB_USER") ?? "bridge_app";
    if (dbUser != "bridge_app") throw new ConfigurationException("database_role_not_application");
    var dbHost = Environment.GetEnvironmentVariable("BRIDGE_DB_HOST") ?? "postgres";
    if (dbHost is not ("postgres" or "localhost" or "127.0.0.1")) throw new ConfigurationException("database_endpoint_not_local");
    var connection = new NpgsqlConnectionStringBuilder
    {
        Host = dbHost, Port = int.Parse(Environment.GetEnvironmentVariable("BRIDGE_DB_PORT") ?? "5432", System.Globalization.CultureInfo.InvariantCulture),
        Database = Environment.GetEnvironmentVariable("BRIDGE_DB_NAME") ?? "bridge", Username = dbUser, Password = SecretFile("BRIDGE_DB_PASSWORD_FILE"),
        IncludeErrorDetail = false, Timeout = 5, CommandTimeout = 20, MaxPoolSize = 24, SslMode = SslMode.Disable
    };
    connection["GSS Encryption Mode"] = "Disable";
    var builder = WebApplication.CreateBuilder(args);
    builder.Logging.ClearProviders();
    builder.Logging.AddJsonConsole();
    builder.Logging.AddFilter("Microsoft.AspNetCore", LogLevel.Warning);
    if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("ASPNETCORE_URLS"))) builder.WebHost.UseUrls("http://0.0.0.0:8080");
    builder.Services.AddSingleton(configuration);
    builder.Services.AddSingleton(_ => NpgsqlDataSource.Create(connection.ConnectionString));
    builder.Services.AddSingleton<IBridgeStore, PostgresStore>();
    builder.Services.AddSingleton<IRpc>(_ => new EthereumRpc(LocalHttp(configuration.RpcTimeoutSeconds)));
    builder.Services.AddSingleton<Chain>();
    builder.Services.AddSingleton<ISigner>(_ => new HttpSigner(LocalHttp(configuration.RpcTimeoutSeconds), signerUrl, signerToken));
    builder.Services.AddSingleton<RelayerService>();
    builder.Services.AddHostedService(provider => provider.GetRequiredService<RelayerService>());
    var app = builder.Build();
    app.MapGet("/health", (RelayerService service) => Results.Json(new { status = "available", ready = service.Snapshot.Ready && !service.Stale }));
    app.MapGet("/status", (RelayerService service) => Results.Json(new { service.Snapshot.Running, service.Snapshot.Ready, stale = service.Stale, service.Snapshot.Profile,
        service.Snapshot.CodeVersion, service.Snapshot.UpdatedUtc, service.Snapshot.ErrorCode, service.Snapshot.Networks, service.Snapshot.Transfers, service.Snapshot.Reconciliation }));
    app.MapGet("/metrics", (RelayerService service) => Results.Text(service.Metrics(), "text/plain; version=0.0.4; charset=utf-8"));
    await app.RunAsync();
    return 0;
}
catch (Exception error)
{
    // No exception text or file content: even startup parsing errors may contain secrets.
    Console.Error.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { @event = "startup_failed", errorCode = error is ConfigurationException c ? c.Message : "startup_configuration_or_runtime_failure", errorType = error.GetType().Name }));
    return 1;
}

static string SecretFile(string variable)
{
    var path = Environment.GetEnvironmentVariable(variable) ?? throw new ConfigurationException("secret_file_variable_missing");
    var value = File.ReadAllText(path).Trim();
    if (value.Length < 16 || value.Contains('\n') || value.Contains('\r')) throw new ConfigurationException("secret_file_invalid");
    return value;
}
static HttpClient LocalHttp(int timeout) => new(new HttpClientHandler { AllowAutoRedirect = false, UseProxy = false }) { Timeout = TimeSpan.FromSeconds(timeout) };

public partial class Program;
