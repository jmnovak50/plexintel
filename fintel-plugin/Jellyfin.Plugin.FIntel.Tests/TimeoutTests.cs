using Jellyfin.Plugin.FIntel.Client;
using Jellyfin.Plugin.FIntel.Configuration;

namespace Jellyfin.Plugin.FIntel.Tests;

public sealed class TimeoutTests
{
    [Fact]
    public async Task ConnectivityReportsConfiguredTimeoutWithoutThrowing()
    {
        var handler = new DelegateHttpHandler(async (_, cancellationToken) =>
        {
            await Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);
            throw new InvalidOperationException("unreachable");
        });
        var client = new FIntelClient(
            new StubHttpClientFactory(handler),
            new StaticConfigurationProvider(new PluginConfiguration
            {
                BackendUrl = "https://fintel.example/",
                RequestTimeoutSeconds = 1
            }));

        var result = await client.TestConnectivityAsync(CancellationToken.None);

        Assert.False(result.Reachable);
        Assert.False(result.Authenticated);
        Assert.False(result.ValidResponse);
        Assert.Contains("timed out", result.Message, StringComparison.OrdinalIgnoreCase);
    }
}
