using Jellyfin.Database.Implementations.Entities;
using Jellyfin.Plugin.FIntel.Matching;
using Jellyfin.Plugin.FIntel.Models;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Entities;
using Moq;

namespace Jellyfin.Plugin.FIntel.Tests;

public sealed class MediaMatcherTests
{
    [Fact]
    public async Task MatchesInBackendOrderByTmdbImdbTvdbThenNormalizedTitleYear()
    {
        var source = Movie("Source", 2000);
        var tmdb = Movie("TMDb", 2001, MetadataProvider.Tmdb, "10");
        var imdb = Movie("IMDb", 2002, MetadataProvider.Imdb, "tt20");
        var tvdb = Movie("TVDb", 2003, MetadataProvider.Tvdb, "30");
        var title = Movie("Amélie!", 2001);
        var matcher = CreateMatcher(source, tmdb, imdb, tvdb, title);
        var recommendations = new[]
        {
            Recommendation("ignored", 2001, tmdb: "10"),
            Recommendation("ignored", 2002, imdb: "tt20"),
            Recommendation("ignored", 2003, tvdb: "30"),
            Recommendation("AMELIE", 2001)
        };

        var result = await matcher.MatchMoviesAsync(recommendations, source, User(), 10, CancellationToken.None);

        Assert.Equal(new[] { tmdb.Id, imdb.Id, tvdb.Id, title.Id }, result.Items.Select(item => item.Id));
        Assert.Equal(4, result.Matched);
    }

    [Fact]
    public async Task SkipsAmbiguousFallbackSourceAndDuplicateWhilePreservingOrder()
    {
        var source = Movie("Source", 2000, MetadataProvider.Tmdb, "1");
        var duplicate = Movie("Duplicate", 2001, MetadataProvider.Tmdb, "2");
        var ambiguousOne = Movie("Same Title", 2010);
        var ambiguousTwo = Movie("Same-Title", 2010);
        var final = Movie("Final", 2011, MetadataProvider.Imdb, "tt3");
        var matcher = CreateMatcher(source, duplicate, ambiguousOne, ambiguousTwo, final);
        var recommendations = new[]
        {
            Recommendation("source", 2000, tmdb: "1"),
            Recommendation("duplicate", 2001, tmdb: "2"),
            Recommendation("duplicate again", 2001, tmdb: "2"),
            Recommendation("same title", 2010),
            Recommendation("final", 2011, imdb: "tt3")
        };

        var result = await matcher.MatchMoviesAsync(recommendations, source, User(), 10, CancellationToken.None);

        Assert.Equal(new[] { duplicate.Id, final.Id }, result.Items.Select(item => item.Id));
        Assert.Equal(1, result.Ambiguous);
        Assert.Equal(1, result.Duplicates);
        Assert.Equal(1, result.Excluded);
    }

    [Theory]
    [InlineData("  Spider-Man: Into the Spider-Verse ", "spider man into the spider verse")]
    [InlineData("Amélie", "amelie")]
    [InlineData("WALL·E", "wall e")]
    public void NormalizesTitles(string input, string expected)
        => Assert.Equal(expected, MediaMatcher.NormalizeTitle(input));

    private static MediaMatcher CreateMatcher(params Movie[] movies)
    {
        var library = new Mock<ILibraryManager>();
        library.Setup(manager => manager.GetItemList(It.IsAny<InternalItemsQuery>()))
            .Returns(movies.Cast<BaseItem>().ToArray());
        return new MediaMatcher(library.Object);
    }

    private static Movie Movie(string name, int year, MetadataProvider? provider = null, string? providerId = null)
    {
        var movie = new Movie { Id = Guid.NewGuid(), Name = name, ProductionYear = year };
        if (provider.HasValue)
        {
            movie.SetProviderId(provider.Value, providerId!);
        }

        return movie;
    }

    private static User User() => new("viewer", "auth", "reset");

    private static FIntelRecommendation Recommendation(
        string title,
        int year,
        string? tmdb = null,
        string? imdb = null,
        string? tvdb = null)
        => new() { Title = title, Year = year, MediaType = "movie", TmdbId = tmdb, ImdbId = imdb, TvdbId = tvdb };
}
