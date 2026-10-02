using System.Diagnostics;
using System.Net;
using System.Net.Http.Json;
using Jellyfin.Plugin.FIntel.Models;
using Jellyfin.Plugin.FIntel.Services;

namespace Jellyfin.Plugin.FIntel.Client;

public interface IFIntelClient
{
    Task<FIntelRecommendationsResponse?> GetRecommendationsAsync(string username, string mediaType, int limit, CancellationToken cancellationToken);

    Task<ConnectivityResult> TestConnectivityAsync(CancellationToken cancellationToken);
}

public sealed class FIntelClient : IFIntelClient
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IPluginConfigurationProvider _configuration;

    public FIntelClient(IHttpClientFactory httpClientFactory, IPluginConfigurationProvider configuration)
    {
        _httpClientFactory = httpClientFactory;
        _configuration = configuration;
    }

    public async Task<FIntelRecommendationsResponse?> GetRecommendationsAsync(string username, string mediaType, int limit, CancellationToken cancellationToken)
    {
        var configuration = GetValidConfiguration();
        var relative = "api/fintel/v1/recommendations?username="
            + Uri.EscapeDataString(username)
            + "&media_type="
            + Uri.EscapeDataString(mediaType)
            + "&limit="
            + Math.Clamp(limit, 1, 100).ToString(System.Globalization.CultureInfo.InvariantCulture);
        using var request = CreateRequest(HttpMethod.Get, new Uri(configuration.BackendUri, relative), configuration.ApiToken);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(configuration.TimeoutSeconds));
        using var response = await _httpClientFactory.CreateClient(nameof(FIntelClient))
            .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, timeout.Token)
            .ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<FIntelRecommendationsResponse>(cancellationToken: timeout.Token).ConfigureAwait(false);
    }

    public async Task<ConnectivityResult> TestConnectivityAsync(CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        try
        {
            var configuration = GetValidConfiguration();
            using var request = CreateRequest(HttpMethod.Get, new Uri(configuration.BackendUri, "api/fintel/v1/health"), configuration.ApiToken);
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            timeout.CancelAfter(TimeSpan.FromSeconds(configuration.TimeoutSeconds));
            using var response = await _httpClientFactory.CreateClient(nameof(FIntelClient))
                .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, timeout.Token)
                .ConfigureAwait(false);
            if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
            {
                return Result(true, false, false, "The backend rejected the configured API token.");
            }

            if (!response.IsSuccessStatusCode)
            {
                return Result(true, true, false, $"The backend returned HTTP {(int)response.StatusCode}.");
            }

            var body = await response.Content.ReadFromJsonAsync<FIntelHealthResponse>(cancellationToken: timeout.Token).ConfigureAwait(false);
            var valid = string.Equals(body?.Status, "ok", StringComparison.OrdinalIgnoreCase);
            return Result(true, true, valid, valid ? "FIntel backend is healthy." : "The backend returned an invalid health response.");
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return Result(false, false, false, "The backend request timed out.");
        }
        catch (HttpRequestException)
        {
            return Result(false, false, false, "The backend could not be reached.");
        }
        catch (System.Text.Json.JsonException)
        {
            return Result(true, true, false, "The backend returned malformed JSON.");
        }
        catch (InvalidOperationException exception)
        {
            return Result(false, false, false, exception.Message);
        }

        ConnectivityResult Result(bool reachable, bool authenticated, bool validResponse, string message)
            => new(reachable, authenticated, validResponse, stopwatch.ElapsedMilliseconds, message);
    }

    private static HttpRequestMessage CreateRequest(HttpMethod method, Uri uri, string apiToken)
    {
        var request = new HttpRequestMessage(method, uri);
        if (!string.IsNullOrWhiteSpace(apiToken))
        {
            request.Headers.Add("X-API-Key", apiToken);
        }

        return request;
    }

    private ValidConfiguration GetValidConfiguration()
    {
        var configuration = _configuration.Current;
        var errors = ConfigurationValidator.Validate(configuration);
        if (errors.Count > 0)
        {
            throw new InvalidOperationException(errors[0]);
        }

        return new ValidConfiguration(
            new Uri(configuration.BackendUrl.Trim().TrimEnd('/') + '/', UriKind.Absolute),
            configuration.ApiToken ?? string.Empty,
            configuration.RequestTimeoutSeconds);
    }

    private sealed record ValidConfiguration(Uri BackendUri, string ApiToken, int TimeoutSeconds);
}
