namespace Bridge.Signer;

public static class Program
{
    public static async Task<int> Main(string[] args)
    {
        try
        {
            if (args.Length == 2 && args[0] == "--generate-key")
            {
                Console.WriteLine(FileKeySigner.GenerateNewKey(args[1]));
                return 0;
            }
            if (args.Length != 0) throw new SignerConfigurationException();
            var configPath = Environment.GetEnvironmentVariable("BRIDGE_CONFIG") ?? throw new SignerConfigurationException();
            var tokenPath = Environment.GetEnvironmentVariable("BRIDGE_SIGNER_TOKEN_FILE") ?? throw new SignerConfigurationException();
            var configuration = SignerConfiguration.Load(configPath);
            using var service = SigningService.Load(configuration, tokenPath);
            await using var app = SignerApplication.Build(service);
            await app.RunAsync();
            return 0;
        }
        catch
        {
            // Une exception de bibliothèque peut contenir un chemin ou une donnée d'entrée.
            Console.Error.WriteLine("{\"event\":\"signer_startup_failed\"}");
            return 2;
        }
    }
}
