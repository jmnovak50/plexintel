using Jellyfin.Plugin.FIntel.Configuration;

namespace Jellyfin.Plugin.FIntel.Services;

public interface IPluginConfigurationProvider
{
    PluginConfiguration Current { get; }
}

public sealed class PluginConfigurationProvider : IPluginConfigurationProvider
{
    public PluginConfiguration Current => Plugin.Instance?.Configuration ?? new PluginConfiguration();
}
