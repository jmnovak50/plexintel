using Jellyfin.Plugin.FIntel.Configuration;

namespace Jellyfin.Plugin.FIntel.Services;

public static class ConfigurationValidator
{
    public static IReadOnlyList<string> Validate(PluginConfiguration configuration)
    {
        var errors = new List<string>();
        if (!Uri.TryCreate(configuration.BackendUrl, UriKind.Absolute, out var backendUri)
            || (backendUri.Scheme != Uri.UriSchemeHttp && backendUri.Scheme != Uri.UriSchemeHttps))
        {
            errors.Add("Backend URL must be an absolute HTTP or HTTPS URL.");
        }

        if (configuration.RequestTimeoutSeconds is < 1 or > 120)
        {
            errors.Add("Timeout must be between 1 and 120 seconds.");
        }

        var seen = new HashSet<Guid>();
        foreach (var mapping in configuration.UserMappings ?? [])
        {
            if (mapping.JellyfinUserId == Guid.Empty)
            {
                errors.Add("Every user mapping must contain a valid Jellyfin user ID.");
            }
            else if (!seen.Add(mapping.JellyfinUserId))
            {
                errors.Add($"Duplicate Jellyfin user mapping: {mapping.JellyfinUserId:D}.");
            }

            if (string.IsNullOrWhiteSpace(mapping.FIntelUsername))
            {
                errors.Add("Every user mapping must contain a FIntel username.");
            }
        }

        return errors;
    }
}
