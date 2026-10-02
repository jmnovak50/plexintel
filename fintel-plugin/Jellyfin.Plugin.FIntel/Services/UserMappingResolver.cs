namespace Jellyfin.Plugin.FIntel.Services;

public interface IUserMappingResolver
{
    bool TryResolve(Guid jellyfinUserId, out string fintelUsername);
}

public sealed class UserMappingResolver : IUserMappingResolver
{
    private readonly IPluginConfigurationProvider _configuration;

    public UserMappingResolver(IPluginConfigurationProvider configuration)
    {
        _configuration = configuration;
    }

    public bool TryResolve(Guid jellyfinUserId, out string fintelUsername)
    {
        fintelUsername = string.Empty;
        if (jellyfinUserId == Guid.Empty)
        {
            return false;
        }

        var matches = (_configuration.Current.UserMappings ?? [])
            .Where(mapping => mapping.JellyfinUserId == jellyfinUserId)
            .ToArray();

        if (matches.Length != 1 || string.IsNullOrWhiteSpace(matches[0].FIntelUsername))
        {
            return false;
        }

        fintelUsername = matches[0].FIntelUsername.Trim();
        return true;
    }
}
