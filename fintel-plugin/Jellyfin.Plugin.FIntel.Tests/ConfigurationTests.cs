using Jellyfin.Plugin.FIntel.Configuration;
using Jellyfin.Plugin.FIntel.Services;

namespace Jellyfin.Plugin.FIntel.Tests;

public sealed class ConfigurationTests
{
    [Fact]
    public void DefaultsAreSafe()
    {
        var configuration = new PluginConfiguration();
        Assert.False(configuration.Enabled);
        Assert.Equal(10, configuration.RequestTimeoutSeconds);
        Assert.Empty(configuration.UserMappings);
    }

    [Fact]
    public void ValidationRejectsInvalidUrlTimeoutDuplicateUsersAndBlankNames()
    {
        var id = Guid.NewGuid();
        var configuration = new PluginConfiguration
        {
            BackendUrl = "file:///tmp/backend",
            RequestTimeoutSeconds = 121,
            UserMappings =
            [
                new UserMapping { JellyfinUserId = id, FIntelUsername = "valid" },
                new UserMapping { JellyfinUserId = id, FIntelUsername = " " }
            ]
        };

        var errors = ConfigurationValidator.Validate(configuration);
        Assert.Equal(4, errors.Count);
    }

    [Fact]
    public void ResolverTrimsMappedUsernameAndFailsClosedForDuplicateOrMissingMapping()
    {
        var id = Guid.NewGuid();
        var configuration = new PluginConfiguration
        {
            BackendUrl = "https://fintel.example/",
            UserMappings = [new UserMapping { JellyfinUserId = id, FIntelUsername = "  member  " }]
        };
        var resolver = new UserMappingResolver(new StaticConfigurationProvider(configuration));

        Assert.True(resolver.TryResolve(id, out var username));
        Assert.Equal("member", username);
        Assert.False(resolver.TryResolve(Guid.NewGuid(), out _));

        configuration.UserMappings =
        [
            new UserMapping { JellyfinUserId = id, FIntelUsername = "one" },
            new UserMapping { JellyfinUserId = id, FIntelUsername = "two" }
        ];
        Assert.False(resolver.TryResolve(id, out _));
    }
}
