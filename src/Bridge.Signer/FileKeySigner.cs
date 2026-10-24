using System.Numerics;
using System.Security.Cryptography;
using Nethereum.Signer;

namespace Bridge.Signer;

/// <summary>Point de substitution d'un fournisseur de signature ; aucune dépendance RPC.</summary>
public interface ITransactionSignerBackend : IDisposable
{
    string Address { get; }
    string Sign(ValidatedTransaction transaction);
}

/// <summary>Clé locale de test, distincte d'un HSM ; ses copies internes ne sont pas garanties effaçables.</summary>
public sealed class FileKeySigner : ITransactionSignerBackend
{
    private readonly byte[] _privateKey;
    private readonly object _sync = new();
    private bool _disposed;
    public string Address { get; }

    public FileKeySigner(string path)
    {
        byte[] content = [];
        byte[] key = [];
        try
        {
            if (new FileInfo(path).Length > 70) throw new SignerConfigurationException();
            content = File.ReadAllBytes(path);
            var span = content.AsSpan();
            while (!span.IsEmpty && span[^1] is (byte)'\r' or (byte)'\n') span = span[..^1];
            if (span.StartsWith("0x"u8)) span = span[2..];
            if (span.Length != 64) throw new SignerConfigurationException();
            key = new byte[32];
            for (var i = 0; i < key.Length; i++) key[i] = (byte)((Nibble(span[2 * i]) << 4) | Nibble(span[2 * i + 1]));
            if (!ValidScalar(key)) throw new SignerConfigurationException();
            Address = new EthECKey(key, true).GetPublicAddress().ToLowerInvariant();
            _privateKey = key;
        }
        catch
        {
            CryptographicOperations.ZeroMemory(key);
            throw new SignerConfigurationException();
        }
        finally { CryptographicOperations.ZeroMemory(content); }
    }

    public string Sign(ValidatedTransaction transaction)
    {
        lock (_sync)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            // Aucun montant ETH fourni par l'appelant : valeur zéro imposée ici.
            var encoded = new LegacyTransactionSigner().SignTransaction(_privateKey, transaction.ChainId,
                transaction.To, BigInteger.Zero, transaction.Nonce, transaction.GasPriceWei,
                transaction.GasLimit, transaction.Data);
            return encoded.StartsWith("0x", StringComparison.Ordinal) ? encoded : "0x" + encoded;
        }
    }

    public void Dispose()
    {
        lock (_sync)
        {
            if (_disposed) return;
            CryptographicOperations.ZeroMemory(_privateKey);
            _disposed = true;
        }
    }

    public static string GenerateNewKey(string path)
    {
        var absolute = Path.GetFullPath(path);
        var directory = Path.GetDirectoryName(absolute) ?? throw new SignerConfigurationException();
        if (!Directory.Exists(directory))
        {
            if (OperatingSystem.IsWindows()) Directory.CreateDirectory(directory);
            else Directory.CreateDirectory(directory, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
        }
        byte[] key = RandomNumberGenerator.GetBytes(32);
        while (!ValidScalar(key)) RandomNumberGenerator.Fill(key);
        byte[] ascii = new byte[66];
        try
        {
            var address = new EthECKey(key, true).GetPublicAddress().ToLowerInvariant();
            ascii[0] = (byte)'0'; ascii[1] = (byte)'x';
            ReadOnlySpan<byte> digits = "0123456789abcdef"u8;
            for (var i = 0; i < key.Length; i++)
            {
                ascii[2 + i * 2] = digits[key[i] >> 4];
                ascii[3 + i * 2] = digits[key[i] & 15];
            }
            var options = new FileStreamOptions { Mode = FileMode.CreateNew, Access = FileAccess.Write, Share = FileShare.None };
            if (!OperatingSystem.IsWindows()) options.UnixCreateMode = UnixFileMode.UserRead | UnixFileMode.UserWrite;
            using (var stream = new FileStream(absolute, options))
            {
                stream.Write(ascii);
                stream.Flush(flushToDisk: true);
            }
            // Lecture possible dans le secret Compose par l'UID du signataire ; parent dédié 0700.
            if (!OperatingSystem.IsWindows())
                File.SetUnixFileMode(absolute, UnixFileMode.UserRead | UnixFileMode.GroupRead | UnixFileMode.OtherRead);
            return address;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(key);
            CryptographicOperations.ZeroMemory(ascii);
        }
    }

    private static int Nibble(byte c) => c switch
    {
        >= (byte)'0' and <= (byte)'9' => c - '0',
        >= (byte)'a' and <= (byte)'f' => c - 'a' + 10,
        >= (byte)'A' and <= (byte)'F' => c - 'A' + 10,
        _ => throw new SignerConfigurationException()
    };

    private static bool ValidScalar(byte[] bytes)
    {
        // Ordre public de secp256k1, en décimal pour le distinguer d'un fichier de clé.
        var order = BigInteger.Parse("115792089237316195423570985008687907852837564279074904382605163141518161494337",
            System.Globalization.CultureInfo.InvariantCulture);
        var value = new BigInteger(bytes, isUnsigned: true, isBigEndian: true);
        return value > 0 && value < order;
    }
}
