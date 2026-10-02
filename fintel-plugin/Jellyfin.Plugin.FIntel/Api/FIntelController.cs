using Jellyfin.Plugin.FIntel.Client;
using Jellyfin.Plugin.FIntel.Models;
using MediaBrowser.Common.Api;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.FIntel.Api;

[ApiController]
[Route("FIntel")]
[Authorize(Policy = Policies.RequiresElevation)]
public sealed class FIntelController : ControllerBase
{
    private readonly IFIntelClient _client;
    private readonly ILogger<FIntelController> _logger;

    public FIntelController(IFIntelClient client, ILogger<FIntelController> logger)
    {
        _client = client;
        _logger = logger;
    }

    [HttpPost("HealthCheck")]
    [ProducesResponseType(typeof(ConnectivityResult), StatusCodes.Status200OK)]
    public async Task<ActionResult<ConnectivityResult>> HealthCheck(CancellationToken cancellationToken)
    {
        var result = await _client.TestConnectivityAsync(cancellationToken).ConfigureAwait(false);
        _logger.LogInformation(
            "FIntel connectivity test complete: reachable={Reachable}, authenticated={Authenticated}, validResponse={ValidResponse}, elapsedMs={ElapsedMilliseconds}",
            result.Reachable,
            result.Authenticated,
            result.ValidResponse,
            result.ElapsedMilliseconds);
        return Ok(result);
    }
}
