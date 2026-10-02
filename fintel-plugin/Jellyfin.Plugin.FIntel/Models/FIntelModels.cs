using System.Text.Json.Serialization;

namespace Jellyfin.Plugin.FIntel.Models;

public sealed class FIntelHealthResponse
{
    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;
}

public sealed class FIntelRecommendationsResponse
{
    [JsonPropertyName("username")]
    public string Username { get; set; } = string.Empty;

    [JsonPropertyName("media_type")]
    public string MediaType { get; set; } = string.Empty;

    [JsonPropertyName("recommendations")]
    public List<FIntelRecommendation> Recommendations { get; set; } = [];
}

public sealed class FIntelRecommendation
{
    [JsonPropertyName("rating_key")]
    public long RatingKey { get; set; }

    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;

    [JsonPropertyName("year")]
    public int? Year { get; set; }

    [JsonPropertyName("media_type")]
    public string MediaType { get; set; } = string.Empty;

    [JsonPropertyName("probability")]
    public double Probability { get; set; }

    [JsonPropertyName("tmdb_id")]
    public string? TmdbId { get; set; }

    [JsonPropertyName("imdb_id")]
    public string? ImdbId { get; set; }

    [JsonPropertyName("tvdb_id")]
    public string? TvdbId { get; set; }
}

public sealed record ConnectivityResult(
    bool Reachable,
    bool Authenticated,
    bool ValidResponse,
    long ElapsedMilliseconds,
    string Message);
