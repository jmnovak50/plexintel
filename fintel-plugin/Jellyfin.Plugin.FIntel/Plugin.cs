using System.Globalization;
using Jellyfin.Plugin.FIntel.Configuration;
using Jellyfin.Plugin.FIntel.Services;
using MediaBrowser.Common.Configuration;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Model.Plugins;
using MediaBrowser.Model.Serialization;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.FIntel;

public sealed class Plugin : BasePlugin<PluginConfiguration>, IHasWebPages
{
    private readonly ILogger<Plugin> _logger;

    public Plugin(IApplicationPaths applicationPaths, IXmlSerializer xmlSerializer, ILogger<Plugin> logger)
        : base(applicationPaths, xmlSerializer)
    {
        _logger = logger;
        Instance = this;
        _logger.LogInformation("FIntel plugin loaded");
    }

    public static Plugin? Instance { get; private set; }

    public override string Name => "FIntel";

    public override string Description => "User-specific movie similarity from the FIntel recommendation engine.";

    public override Guid Id => Guid.Parse("d84462bb-88da-4af1-952c-c10887752a28");

    public IEnumerable<PluginPageInfo> GetPages()
    {
        yield return new PluginPageInfo
        {
            Name = Name,
            EmbeddedResourcePath = string.Format(
                CultureInfo.InvariantCulture,
                "{0}.Configuration.configPage.html",
                GetType().Namespace)
        };
    }

    public override void UpdateConfiguration(BasePluginConfiguration configuration)
    {
        if (configuration is not PluginConfiguration typedConfiguration)
        {
            throw new ArgumentException("Invalid FIntel configuration type.", nameof(configuration));
        }

        var errors = ConfigurationValidator.Validate(typedConfiguration);
        if (errors.Count > 0)
        {
            throw new ArgumentException(string.Join(" ", errors), nameof(configuration));
        }

        typedConfiguration.BackendUrl = typedConfiguration.BackendUrl.Trim();
        typedConfiguration.UserMappings ??= [];
        foreach (var mapping in typedConfiguration.UserMappings)
        {
            mapping.FIntelUsername = mapping.FIntelUsername.Trim();
        }

        base.UpdateConfiguration(typedConfiguration);
    }

    public override void OnUninstalling()
    {
        _logger.LogInformation("FIntel plugin is being uninstalled");
        base.OnUninstalling();
    }
}
