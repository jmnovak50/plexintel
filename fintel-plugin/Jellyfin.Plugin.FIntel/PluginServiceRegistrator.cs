using Jellyfin.Plugin.FIntel.Client;
using Jellyfin.Plugin.FIntel.Matching;
using Jellyfin.Plugin.FIntel.Provider;
using Jellyfin.Plugin.FIntel.Services;
using MediaBrowser.Controller;
using MediaBrowser.Controller.Plugins;
using Microsoft.Extensions.DependencyInjection;

namespace Jellyfin.Plugin.FIntel;

public sealed class PluginServiceRegistrator : IPluginServiceRegistrator
{
    public void RegisterServices(IServiceCollection serviceCollection, IServerApplicationHost applicationHost)
    {
        serviceCollection.AddHttpClient();
        serviceCollection.AddSingleton(TimeProvider.System);
        serviceCollection.AddSingleton<IPluginConfigurationProvider, PluginConfigurationProvider>();
        serviceCollection.AddSingleton<IFIntelClient, FIntelClient>();
        serviceCollection.AddSingleton<IUserMappingResolver, UserMappingResolver>();
        serviceCollection.AddSingleton<IRecommendationCache, RecommendationCache>();
        serviceCollection.AddSingleton<IMediaMatcher, MediaMatcher>();
        serviceCollection.AddSingleton<FIntelMovieSimilarityProvider>();
    }
}
