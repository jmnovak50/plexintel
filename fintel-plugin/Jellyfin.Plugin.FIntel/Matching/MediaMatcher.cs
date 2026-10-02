using System.Globalization;
using System.Text;
using Jellyfin.Data.Enums;
using Jellyfin.Database.Implementations.Entities;
using Jellyfin.Plugin.FIntel.Models;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Entities;

namespace Jellyfin.Plugin.FIntel.Matching;

public sealed record MediaMatchResult(
    IReadOnlyList<BaseItem> Items,
    int Requested,
    int Matched,
    int Unmatched,
    int Ambiguous,
    int Duplicates,
    int Excluded);

public interface IMediaMatcher
{
    Task<MediaMatchResult> MatchMoviesAsync(
        IReadOnlyList<FIntelRecommendation> recommendations,
        Movie source,
        User user,
        int limit,
        CancellationToken cancellationToken);
}

public sealed class MediaMatcher : IMediaMatcher
{
    private readonly ILibraryManager _libraryManager;

    public MediaMatcher(ILibraryManager libraryManager)
    {
        _libraryManager = libraryManager;
    }

    public Task<MediaMatchResult> MatchMoviesAsync(
        IReadOnlyList<FIntelRecommendation> recommendations,
        Movie source,
        User user,
        int limit,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var movies = _libraryManager.GetItemList(new InternalItemsQuery(user)
        {
            IncludeItemTypes = [BaseItemKind.Movie],
            Recursive = true
        }).OfType<Movie>().ToArray();

        var tmdb = BuildUniqueIdIndex(movies, MetadataProvider.Tmdb);
        var imdb = BuildUniqueIdIndex(movies, MetadataProvider.Imdb);
        var tvdb = BuildUniqueIdIndex(movies, MetadataProvider.Tvdb);
        var titleYearGroups = movies
            .Where(movie => movie.ProductionYear.HasValue)
            .GroupBy(movie => TitleYearKey(movie.Name, movie.ProductionYear), StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.ToArray(), StringComparer.Ordinal);

        var items = new List<BaseItem>();
        var seen = new HashSet<Guid> { source.Id };
        var unmatched = 0;
        var ambiguous = 0;
        var duplicates = 0;
        var excluded = 0;

        foreach (var recommendation in recommendations)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (items.Count >= limit)
            {
                break;
            }

            var match = FindById(tmdb, recommendation.TmdbId)
                ?? FindById(imdb, recommendation.ImdbId)
                ?? FindById(tvdb, recommendation.TvdbId);
            if (match is null && recommendation.Year.HasValue)
            {
                var key = TitleYearKey(recommendation.Title, recommendation.Year);
                if (titleYearGroups.TryGetValue(key, out var candidates))
                {
                    if (candidates.Length == 1)
                    {
                        match = candidates[0];
                    }
                    else
                    {
                        ambiguous++;
                        continue;
                    }
                }
            }

            if (match is null)
            {
                unmatched++;
                continue;
            }

            if (match.Id == source.Id)
            {
                excluded++;
                continue;
            }

            if (!seen.Add(match.Id))
            {
                duplicates++;
                continue;
            }

            items.Add(match);
        }

        return Task.FromResult(new MediaMatchResult(
            items,
            recommendations.Count,
            items.Count,
            unmatched,
            ambiguous,
            duplicates,
            excluded));
    }

    public static string NormalizeTitle(string? title)
    {
        if (string.IsNullOrWhiteSpace(title))
        {
            return string.Empty;
        }

        var normalized = title.Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(normalized.Length);
        var pendingSpace = false;
        foreach (var character in normalized)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            if (char.IsLetterOrDigit(character))
            {
                if (pendingSpace && builder.Length > 0)
                {
                    builder.Append(' ');
                }

                builder.Append(char.ToLowerInvariant(character));
                pendingSpace = false;
            }
            else
            {
                pendingSpace = true;
            }
        }

        return builder.ToString();
    }

    private static Dictionary<string, Movie> BuildUniqueIdIndex(IEnumerable<Movie> movies, MetadataProvider provider)
        => movies
            .Select(movie => (Movie: movie, Id: movie.GetProviderId(provider)))
            .Where(pair => !string.IsNullOrWhiteSpace(pair.Id))
            .GroupBy(pair => pair.Id!, StringComparer.OrdinalIgnoreCase)
            .Where(group => group.Count() == 1)
            .ToDictionary(group => group.Key, group => group.Single().Movie, StringComparer.OrdinalIgnoreCase);

    private static Movie? FindById(IReadOnlyDictionary<string, Movie> index, string? id)
        => !string.IsNullOrWhiteSpace(id) && index.TryGetValue(id.Trim(), out var movie) ? movie : null;

    private static string TitleYearKey(string? title, int? year)
        => string.Concat(NormalizeTitle(title), "\u001f", year?.ToString(CultureInfo.InvariantCulture) ?? string.Empty);
}
