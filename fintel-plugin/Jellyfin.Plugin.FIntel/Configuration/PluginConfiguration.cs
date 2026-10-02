using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.FIntel.Configuration;

public sealed class PluginConfiguration : BasePluginConfiguration
{
    public bool Enabled { get; set; }

    public string BackendUrl { get; set; } = string.Empty;

    public string ApiToken { get; set; } = string.Empty;

    public int RequestTimeoutSeconds { get; set; } = 10;

    public UserMapping[] UserMappings { get; set; } = [];
}

public sealed class UserMapping
{
    public Guid JellyfinUserId { get; set; }

    public string FIntelUsername { get; set; } = string.Empty;
}
