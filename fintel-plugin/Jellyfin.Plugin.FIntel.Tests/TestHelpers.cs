using System.Net;
using Jellyfin.Plugin.FIntel.Configuration;
using Jellyfin.Plugin.FIntel.Services;

namespace Jellyfin.Plugin.FIntel.Tests;

internal sealed class StaticConfigurationProvider : IPluginConfigurationProvider
{
    public StaticConfigurationProvider(PluginConfiguration configuration)
    {
        Current = configuration;
    }

    public PluginConfiguration Current { get; }
}

internal sealed class MutableTimeProvider : TimeProvider
{
    public DateTimeOffset Now { get; set; } = DateTimeOffset.Parse("2026-01-01T00:00:00Z");

    public override DateTimeOffset GetUtcNow() => Now;
}

internal sealed class StubHttpClientFactory : IHttpClientFactory
{
    private readonly HttpClient _client;

    public StubHttpClientFactory(HttpMessageHandler handler)
    {
        _client = new HttpClient(handler);
    }

    public HttpClient CreateClient(string name) => _client;
}

internal sealed class DelegateHttpHandler : HttpMessageHandler
{
    private readonly Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> _handler;

    public DelegateHttpHandler(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> handler)
    {
        _handler = handler;
    }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        => _handler(request, cancellationToken);

    public static HttpResponseMessage Json(string json, HttpStatusCode statusCode = HttpStatusCode.OK)
        => new(statusCode) { Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json") };
}
