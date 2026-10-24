using System.Security.Cryptography;
using System.Text;
using Nethereum.Util;

namespace Bridge.Signer;

public sealed class TokenAuthenticator : IDisposable
{
    private readonly byte[] _expectedHash;
    private bool _disposed;

    public TokenAuthenticator(string token)
    {
        if (token.Length is < 32 or > 256 || token.Any(c => c is < '!' or > '~'))
            throw new SignerConfigurationException();
        var bytes = Encoding.UTF8.GetBytes(token);
        try { _expectedHash = SHA256.HashData(bytes); }
        finally { CryptographicOperations.ZeroMemory(bytes); }
    }

    public static TokenAuthenticator Load(string path)
    {
        if (new FileInfo(path).Length > 258) throw new SignerConfigurationException();
        return new TokenAuthenticator(File.ReadAllText(path).TrimEnd('\r', '\n'));
    }

    public bool Matches(string? candidate)
    {
        if (_disposed || candidate is null || candidate.Length > 512) return false;
        var bytes = Encoding.UTF8.GetBytes(candidate);
        try
        {
            Span<byte> actualHash = stackalloc byte[32];
            SHA256.HashData(bytes, actualHash);
            // Les empreintes ont toujours même longueur, y compris si les jetons diffèrent de taille.
            return CryptographicOperations.FixedTimeEquals(_expectedHash, actualHash);
        }
        finally { CryptographicOperations.ZeroMemory(bytes); }
    }

    public void Dispose()
    {
        CryptographicOperations.ZeroMemory(_expectedHash);
        _disposed = true;
    }
}

public sealed class SigningRateLimiter(TimeProvider timeProvider)
{
    public const int SignaturesPerMinute = 10;
    private readonly object _sync = new();
    private readonly Dictionary<long, Queue<long>> _timestamps = [];

    public void Reserve(long chainId)
    {
        lock (_sync)
        {
            var now = timeProvider.GetTimestamp();
            if (!_timestamps.TryGetValue(chainId, out var window))
                _timestamps[chainId] = window = new Queue<long>();
            while (window.TryPeek(out var oldest) && timeProvider.GetElapsedTime(oldest, now) >= TimeSpan.FromMinutes(1))
                window.Dequeue();
            if (window.Count >= SignaturesPerMinute) throw new RateLimitedException();
            window.Enqueue(now);
        }
    }
}

public sealed class SigningService : IDisposable
{
    private readonly SigningPolicy _policy;
    private readonly IReadOnlyDictionary<long, ITransactionSignerBackend> _keys;
    private readonly SigningRateLimiter _limiter;
    public TokenAuthenticator Authentication { get; }

    public SigningService(SignerConfiguration configuration, TokenAuthenticator authentication,
        IReadOnlyDictionary<long, ITransactionSignerBackend> keys, TimeProvider? timeProvider = null)
    {
        if (keys.Count != configuration.Networks.Count || configuration.Networks.Any(p =>
                !keys.TryGetValue(p.Key, out var key) || !string.Equals(key.Address, p.Value.SignerAddress, StringComparison.OrdinalIgnoreCase)))
            throw new SignerConfigurationException();
        _policy = new SigningPolicy(configuration);
        _keys = keys;
        Authentication = authentication;
        _limiter = new SigningRateLimiter(timeProvider ?? TimeProvider.System);
    }

    public static SigningService Load(SignerConfiguration configuration, string tokenFile)
    {
        var keys = new Dictionary<long, ITransactionSignerBackend>();
        TokenAuthenticator? auth = null;
        try
        {
            auth = TokenAuthenticator.Load(tokenFile);
            foreach (var network in configuration.Networks.Values)
                keys.Add(network.ChainId, new FileKeySigner(network.KeyFile));
            return new SigningService(configuration, auth, keys);
        }
        catch
        {
            foreach (var key in keys.Values) key.Dispose();
            auth?.Dispose();
            throw new SignerConfigurationException();
        }
    }

    public SignResponse Sign(SignRequest request)
    {
        var tx = _policy.Validate(request);
        _limiter.Reserve(tx.ChainId);
        var key = _keys[tx.ChainId];
        var raw = key.Sign(tx);
        var bytes = Convert.FromHexString(raw.AsSpan(2));
        var hash = "0x" + Convert.ToHexString(Sha3Keccack.Current.CalculateHash(bytes)).ToLowerInvariant();
        return new SignResponse(raw, hash, key.Address);
    }

    public void Dispose()
    {
        foreach (var key in _keys.Values) key.Dispose();
        Authentication.Dispose();
    }
}
