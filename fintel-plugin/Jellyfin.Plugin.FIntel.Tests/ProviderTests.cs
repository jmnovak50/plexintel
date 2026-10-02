using Jellyfin.Database.Implementations.Entities;
using Jellyfin.Plugin.FIntel.Client;
using Jellyfin.Plugin.FIntel.Configuration;
using Jellyfin.Plugin.FIntel.Matching;
using Jellyfin.Plugin.FIntel.Models;
using Jellyfin.Plugin.FIntel.Provider;
using Jellyfin.Plugin.FIntel.Services;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Configuration;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;

namespace Jellyfin.Plugin.FIntel.Tests;

public sealed class ProviderTests
{
    [Theory]
    [InlineData(false, true, true)]
    [InlineData(true, false, true)]
    [InlineData(true, true, false)]
    public async Task ReturnsNoResultsWhenDisabledOrUnmapped(bool enabled, bool libraryEnabled, bool mapped)
    {
        var fixture = new ProviderFixture(enabled, libraryEnabled, mapped);
        var results = await fixture.Provider.GetSimilarItemsAsync(
            fixture.Source,
            new SimilarItemsQuery { User = fixture.User, Limit = 10 },
            CancellationToken.None);

        Assert.Empty(results);
        fixture.Client.Verify(
            client => client.GetRecommendationsAsync(It.IsAny<string>(), It.IsAny<string>(), It.IsAny<int>(), It.IsAny<CancellationToken>()),
            Times.Never);
    }

    [Fact]
    public async Task IsolatesBackendAndMatchingFailures()
    {
        var fixture = new ProviderFixture(true, true, true);
        fixture.Client.Setup(client => client.GetRecommendationsAsync("member", "movie", 100, It.IsAny<CancellationToken>()))
            .ThrowsAsync(new HttpRequestException("offline"));

        var backendFailure = await fixture.Provider.GetSimilarItemsAsync(
            fixture.Source,
            new SimilarItemsQuery { User = fixture.User, Limit = 10 },
            CancellationToken.None);
        Assert.Empty(backendFailure);

        fixture = new ProviderFixture(true, true, true);
        fixture.Matcher.Setup(matcher => matcher.MatchMoviesAsync(
                It.IsAny<IReadOnlyList<FIntelRecommendation>>(),
                fixture.Source,
                fixture.User,
                10,
                It.IsAny<CancellationToken>()))
            .ThrowsAsync(new InvalidOperationException("matching failed"));
        var matchingFailure = await fixture.Provider.GetSimilarItemsAsync(
            fixture.Source,
            new SimilarItemsQuery { User = fixture.User, Limit = 10 },
            CancellationToken.None);
        Assert.Empty(matchingFailure);
    }

    [Fact]
    public async Task ReturnsMatcherOrderAndRequestsBoundedCompensationLimit()
    {
        var fixture = new ProviderFixture(true, true, true);
        var first = new Movie { Id = Guid.NewGuid(), Name = "First" };
        var second = new Movie { Id = Guid.NewGuid(), Name = "Second" };
        fixture.Matcher.Setup(matcher => matcher.MatchMoviesAsync(
                It.IsAny<IReadOnlyList<FIntelRecommendation>>(),
                fixture.Source,
                fixture.User,
                2,
                It.IsAny<CancellationToken>()))
            .ReturnsAsync(new MediaMatchResult([first, second], 2, 2, 0, 0, 0, 0));

        var results = await fixture.Provider.GetSimilarItemsAsync(
            fixture.Source,
            new SimilarItemsQuery { User = fixture.User, Limit = 2 },
            CancellationToken.None);

        Assert.Equal(new[] { first.Id, second.Id }, results.Select(item => item.Id));
        fixture.Client.Verify(client => client.GetRecommendationsAsync("member", "movie", 100, It.IsAny<CancellationToken>()), Times.Once);
    }

    private sealed class ProviderFixture
    {
        public ProviderFixture(bool enabled, bool libraryEnabled, bool mapped)
        {
            User = new User("viewer", "auth", "reset");
            Source = new Movie { Id = Guid.NewGuid(), Name = "Source" };
            Client = new Mock<IFIntelClient>();
            Client.Setup(client => client.GetRecommendationsAsync(It.IsAny<string>(), It.IsAny<string>(), It.IsAny<int>(), It.IsAny<CancellationToken>()))
                .ReturnsAsync(new FIntelRecommendationsResponse { Recommendations = [new FIntelRecommendation { Title = "Candidate" }] });
            Matcher = new Mock<IMediaMatcher>();
            Matcher.Setup(matcher => matcher.MatchMoviesAsync(
                    It.IsAny<IReadOnlyList<FIntelRecommendation>>(),
                    It.IsAny<Movie>(),
                    It.IsAny<User>(),
                    It.IsAny<int>(),
                    It.IsAny<CancellationToken>()))
                .ReturnsAsync(new MediaMatchResult([], 1, 0, 1, 0, 0, 0));
            var mapping = new Mock<IUserMappingResolver>();
            mapping.Setup(resolver => resolver.TryResolve(User.Id, out It.Ref<string>.IsAny))
                .Returns((Guid _, out string username) =>
                {
                    username = "member";
                    return mapped;
                });
            var configuration = new PluginConfiguration
            {
                Enabled = enabled,
                BackendUrl = "https://fintel.example/",
                RequestTimeoutSeconds = 10
            };
            var library = new Mock<ILibraryManager>();
            library.Setup(manager => manager.GetLibraryOptions(Source)).Returns(new LibraryOptions
            {
                TypeOptions =
                [
                    new TypeOptions
                    {
                        Type = nameof(Movie),
                        SimilarItemProviders = libraryEnabled ? ["FIntel"] : []
                    }
                ]
            });

            Provider = new FIntelMovieSimilarityProvider(
                Client.Object,
                mapping.Object,
                new RecommendationCache(TimeProvider.System),
                Matcher.Object,
                new StaticConfigurationProvider(configuration),
                library.Object,
                NullLogger<FIntelMovieSimilarityProvider>.Instance);
        }

        public User User { get; }

        public Movie Source { get; }

        public Mock<IFIntelClient> Client { get; }

        public Mock<IMediaMatcher> Matcher { get; }

        public FIntelMovieSimilarityProvider Provider { get; }
    }
}
