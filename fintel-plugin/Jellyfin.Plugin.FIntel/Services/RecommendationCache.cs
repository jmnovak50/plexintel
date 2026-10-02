using System.Collections.Concurrent;
using Jellyfin.Plugin.FIntel.Models;

namespace Jellyfin.Plugin.FIntel.Services;

public readonly record struct RecommendationCacheKey(string BackendUrl, string Username, string MediaType)
{
    public static RecommendationCacheKey Create(string backendUrl, string username, string mediaType)
    {
        var normalizedUrl = backendUrl.Trim().TrimEnd('/').ToUpperInvariant();
        return new RecommendationCacheKey(normalizedUrl, username.Trim(), mediaType.Trim().ToLowerInvariant());
    }
}

public interface IRecommendationCache
{
    Task<FIntelRecommendationsResponse?> GetOrCreateAsync(
        RecommendationCacheKey key,
        Func<CancellationToken, Task<FIntelRecommendationsResponse?>> factory,
        CancellationToken cancellationToken);
}

public sealed class RecommendationCache : IRecommendationCache
{
    private static readonly TimeSpan Lifetime = TimeSpan.FromMinutes(5);
    private readonly ConcurrentDictionary<RecommendationCacheKey, CacheEntry> _entries = new();
    private readonly ConcurrentDictionary<RecommendationCacheKey, Lazy<Task<FIntelRecommendationsResponse?>>> _inflight = new();
    private readonly TimeProvider _timeProvider;

    public RecommendationCache(TimeProvider timeProvider)
    {
        _timeProvider = timeProvider;
    }

    public async Task<FIntelRecommendationsResponse?> GetOrCreateAsync(
        RecommendationCacheKey key,
        Func<CancellationToken, Task<FIntelRecommendationsResponse?>> factory,
        CancellationToken cancellationToken)
    {
        var now = _timeProvider.GetUtcNow();
        if (_entries.TryGetValue(key, out var entry) && entry.ExpiresAt > now)
        {
            return entry.Value;
        }

        _entries.TryRemove(key, out _);
        var lazyTask = _inflight.GetOrAdd(
            key,
            _ => new Lazy<Task<FIntelRecommendationsResponse?>>(
                () => FetchAndCacheAsync(key, factory),
                LazyThreadSafetyMode.ExecutionAndPublication));
        return await lazyTask.Value.WaitAsync(cancellationToken).ConfigureAwait(false);
    }

    private async Task<FIntelRecommendationsResponse?> FetchAndCacheAsync(
        RecommendationCacheKey key,
        Func<CancellationToken, Task<FIntelRecommendationsResponse?>> factory)
    {
        try
        {
            var response = await factory(CancellationToken.None).ConfigureAwait(false);
            if (response is not null)
            {
                _entries[key] = new CacheEntry(response, _timeProvider.GetUtcNow().Add(Lifetime));
            }

            return response;
        }
        finally
        {
            _inflight.TryRemove(key, out _);
        }
    }

    private sealed record CacheEntry(FIntelRecommendationsResponse Value, DateTimeOffset ExpiresAt);
}
