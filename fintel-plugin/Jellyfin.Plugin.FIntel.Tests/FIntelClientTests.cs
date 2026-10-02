using System.Net;
using Jellyfin.Plugin.FIntel.Client;
using Jellyfin.Plugin.FIntel.Configuration;

namespace Jellyfin.Plugin.FIntel.Tests;

public sealed class FIntelClientTests
{
    [Fact]
    public async Task DeserializesContractAndSendsTokenOnlyAsHeader()
    {
        Uri? requestedUri = null;
        string? token = null;
        var handler = new DelegateHttpHandler((request, _) =>
        {
            requestedUri = request.RequestUri;
            token = request.Headers.GetValues("X-API-Key").Single();
            return Task.FromResult(DelegateHttpHandler.Json("""
                {"username":"alice","media_type":"movie","recommendations":[{"rating_key":7,"title":"Amélie","year":2001,"media_type":"movie","probability":0.91,"tmdb_id":"194","imdb_id":null,"tvdb_id":null}]}
                """));
        });
        var client = CreateClient(handler);

        var response = await client.GetRecommendationsAsync("alice smith", "movie", 20, CancellationToken.None);

        Assert.NotNull(response);
        Assert.Equal("194", response.Recommendations.Single().TmdbId);
        Assert.Equal("secret", token);
        Assert.DoesNotContain("secret", requestedUri!.AbsoluteUri, StringComparison.Ordinal);
        Assert.Contains("username=alice%20smith", requestedUri.AbsoluteUri, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ConnectivityDistinguishesAuthenticationMalformedAndUnavailableResponses()
    {
        var unauthorized = CreateClient(new DelegateHttpHandler((_, _) => Task.FromResult(new HttpResponseMessage(HttpStatusCode.Unauthorized))));
        var malformed = CreateClient(new DelegateHttpHandler((_, _) => Task.FromResult(DelegateHttpHandler.Json("not-json"))));
        var unavailable = CreateClient(new DelegateHttpHandler((_, _) => throw new HttpRequestException("offline")));

        var authResult = await unauthorized.TestConnectivityAsync(CancellationToken.None);
        var malformedResult = await malformed.TestConnectivityAsync(CancellationToken.None);
        var unavailableResult = await unavailable.TestConnectivityAsync(CancellationToken.None);

        Assert.True(authResult.Reachable);
        Assert.False(authResult.Authenticated);
        Assert.False(malformedResult.ValidResponse);
        Assert.True(malformedResult.Authenticated);
        Assert.False(unavailableResult.Reachable);
    }

    private static FIntelClient CreateClient(HttpMessageHandler handler)
        => new(
            new StubHttpClientFactory(handler),
            new StaticConfigurationProvider(new PluginConfiguration
            {
                BackendUrl = "https://fintel.example/base/",
                ApiToken = "secret",
                RequestTimeoutSeconds = 10
            }));
}
