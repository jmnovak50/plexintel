using Jellyfin.Plugin.FIntel.Models;
using Jellyfin.Plugin.FIntel.Services;

namespace Jellyfin.Plugin.FIntel.Tests;

public sealed class RecommendationCacheTests
{
    [Fact]
    public async Task CachesSuccessfulResponseForFiveMinutesAndIsolatesUsers()
    {
        var time = new MutableTimeProvider();
        var cache = new RecommendationCache(time);
        var calls = 0;
        Task<FIntelRecommendationsResponse?> Factory(CancellationToken _)
        {
            calls++;
            return Task.FromResult<FIntelRecommendationsResponse?>(new FIntelRecommendationsResponse());
        }

        var alice = RecommendationCacheKey.Create("https://host/", "alice", "movie");
        var bob = RecommendationCacheKey.Create("https://host", "bob", "movie");
        await cache.GetOrCreateAsync(alice, Factory, CancellationToken.None);
        await cache.GetOrCreateAsync(alice, Factory, CancellationToken.None);
        await cache.GetOrCreateAsync(bob, Factory, CancellationToken.None);
        Assert.Equal(2, calls);

        time.Now = time.Now.AddMinutes(5);
        await cache.GetOrCreateAsync(alice, Factory, CancellationToken.None);
        Assert.Equal(3, calls);
    }

    [Fact]
    public async Task DoesNotCacheFailuresAndCollapsesConcurrentRequests()
    {
        var cache = new RecommendationCache(new MutableTimeProvider());
        var key = RecommendationCacheKey.Create("https://host", "alice", "movie");
        var calls = 0;
        await cache.GetOrCreateAsync(key, _ =>
        {
            calls++;
            return Task.FromResult<FIntelRecommendationsResponse?>(null);
        }, CancellationToken.None);
        await cache.GetOrCreateAsync(key, _ =>
        {
            calls++;
            return Task.FromResult<FIntelRecommendationsResponse?>(null);
        }, CancellationToken.None);
        Assert.Equal(2, calls);

        var gate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        Task<FIntelRecommendationsResponse?> SlowFactory(CancellationToken _)
        {
            Interlocked.Increment(ref calls);
            return CompleteAsync();
        }

        async Task<FIntelRecommendationsResponse?> CompleteAsync()
        {
            await gate.Task;
            return new FIntelRecommendationsResponse();
        }

        var first = cache.GetOrCreateAsync(key, SlowFactory, CancellationToken.None);
        var second = cache.GetOrCreateAsync(key, SlowFactory, CancellationToken.None);
        gate.SetResult();
        await Task.WhenAll(first, second);
        Assert.Equal(3, calls);
    }
}
