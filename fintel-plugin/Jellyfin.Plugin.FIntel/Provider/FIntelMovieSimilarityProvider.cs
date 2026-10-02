using Jellyfin.Plugin.FIntel.Client;
using Jellyfin.Plugin.FIntel.Matching;
using Jellyfin.Plugin.FIntel.Services;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Configuration;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.FIntel.Provider;

public sealed class FIntelMovieSimilarityProvider : ILocalSimilarItemsProvider<Movie>
{
    private readonly IFIntelClient _client;
    private readonly IUserMappingResolver _userMapping;
    private readonly IRecommendationCache _cache;
    private readonly IMediaMatcher _matcher;
    private readonly IPluginConfigurationProvider _configuration;
    private readonly ILibraryManager _libraryManager;
    private readonly ILogger<FIntelMovieSimilarityProvider> _logger;

    public FIntelMovieSimilarityProvider(
        IFIntelClient client,
        IUserMappingResolver userMapping,
        IRecommendationCache cache,
        IMediaMatcher matcher,
        IPluginConfigurationProvider configuration,
        ILibraryManager libraryManager,
        ILogger<FIntelMovieSimilarityProvider> logger)
    {
        _client = client;
        _userMapping = userMapping;
        _cache = cache;
        _matcher = matcher;
        _configuration = configuration;
        _libraryManager = libraryManager;
        _logger = logger;
    }

    public string Name => "FIntel";

    public MetadataPluginType Type => MetadataPluginType.SimilarityProvider;

    public async Task<IReadOnlyList<BaseItem>> GetSimilarItemsAsync(
        Movie item,
        SimilarItemsQuery query,
        CancellationToken cancellationToken)
    {
        try
        {
            var configuration = _configuration.Current;
            if (!configuration.Enabled || !IsEnabledForLibrary(item) || query.User is null)
            {
                return [];
            }

            if (!_userMapping.TryResolve(query.User.Id, out var fintelUsername))
            {
                return [];
            }

            var requestedLimit = Math.Clamp(query.Limit ?? 20, 1, 100);
            const int fetchLimit = 100;
            var cacheKey = RecommendationCacheKey.Create(configuration.BackendUrl, fintelUsername, "movie");
            var response = await _cache.GetOrCreateAsync(
                cacheKey,
                token => _client.GetRecommendationsAsync(fintelUsername, "movie", fetchLimit, token),
                cancellationToken).ConfigureAwait(false);
            if (response is null)
            {
                return [];
            }

            var result = await _matcher.MatchMoviesAsync(
                response.Recommendations,
                item,
                query.User,
                requestedLimit,
                cancellationToken).ConfigureAwait(false);
            _logger.LogInformation(
                "FIntel movie matching complete: requested={Requested}, matched={Matched}, unmatched={Unmatched}, ambiguous={Ambiguous}, duplicates={Duplicates}, excluded={Excluded}",
                result.Requested,
                result.Matched,
                result.Unmatched,
                result.Ambiguous,
                result.Duplicates,
                result.Excluded);
            return result.Items;
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return [];
        }
        catch (Exception exception)
        {
            _logger.LogWarning(exception, "FIntel similarity failed; returning no FIntel results");
            return [];
        }
    }

    private bool IsEnabledForLibrary(Movie item)
    {
        var typeOptions = _libraryManager.GetLibraryOptions(item).GetTypeOptions(item.GetType().Name);
        return typeOptions?.SimilarItemProviders?.Contains(Name, StringComparer.OrdinalIgnoreCase) == true;
    }
}
