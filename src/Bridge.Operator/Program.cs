using System.Numerics;
using System.Text.Json;
using Nethereum.Signer;

// Outil ponctuel d'administration des deux simulations locales. Jamais un service.
// Aucun argument ne contient de clé ou de payload signé. Sortie dans un fichier local.
if (args.Length != 3) { Console.Error.WriteLine("Usage: operator request.json key-file result.json"); return 2; }
try
{
    var input = JsonDocument.Parse(File.ReadAllText(args[0])).RootElement;
    var chainId = input.GetProperty("chainId").GetInt32();
    if (chainId is not (31337 or 31338 or 31339 or 31340)) throw new InvalidOperationException();
    var nonce = BigInteger.Parse(input.GetProperty("nonce").GetString()!);
    var gas = input.GetProperty("gasLimit").GetInt64();
    var price = BigInteger.Parse(input.GetProperty("gasPriceWei").GetString()!);
    var value = BigInteger.Parse(input.GetProperty("value").GetString()!);
    if (nonce < 0 || nonce > 1000000 || gas < 21000 || gas > 8000000 || price < 0 || price > BigInteger.Parse("100000000000") || value < 0 || value > BigInteger.Parse("100000000000000000000")) throw new InvalidOperationException();
    var key = File.ReadAllText(args[1]).Trim();
    var signer = new LegacyTransactionSigner();
    var signed = signer.SignTransaction(key, chainId, input.GetProperty("to").GetString() ?? "", value, nonce, price, gas, input.GetProperty("data").GetString() ?? "0x");
    File.WriteAllText(args[2], "0x" + signed.TrimStartHex());
    Console.WriteLine("Transaction locale signée dans le fichier de sortie ; aucune diffusion.");
    return 0;
}
catch { Console.Error.WriteLine("Opération refusée ou impossible ; aucune donnée sensible journalisée."); return 1; }

static class HexExtensions
{
    public static string TrimStartHex(this string value) => value.StartsWith("0x", StringComparison.OrdinalIgnoreCase) ? value[2..] : value;
}
