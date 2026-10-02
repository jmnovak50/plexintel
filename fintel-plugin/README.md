# FIntel for Jellyfin

FIntel is a movie-only Jellyfin 12.1 plugin that adds personalized results to
Jellyfin's native **More Like This** flow. The plugin is an adapter: prediction,
training, embeddings, and explanation logic remain in the existing FIntel
(formerly PlexIntel) FastAPI service.

## Requirements

- Jellyfin server ABI `12.1.0.0`
- .NET 10 SDK to build
- A reachable FIntel backend from the Jellyfin server
- The backend setting `public_api.api_key`

The plugin references `Jellyfin.Controller` and `Jellyfin.Model` 12.1.0 and is
not intended for Jellyfin 10.x, 12.0, or a later ABI without rebuilding and
retesting.

## Build

```bash
dotnet restore Jellyfin.Plugin.FIntel.slnx
dotnet test Jellyfin.Plugin.FIntel.slnx -c Release
dotnet build Jellyfin.Plugin.FIntel/Jellyfin.Plugin.FIntel.csproj -c Release
```

### Normal installation

In Jellyfin, open **Dashboard → Plugins → Repositories**, add this repository
URL, and save:

```text
https://raw.githubusercontent.com/jmnovak50/plexintel/main/fintel-plugin/manifest.json
```

Then open **Catalog → FIntel → Install** and restart Jellyfin if prompted.
Release packages are immutable GitHub Release assets; the stable repository
manifest keeps older versions under the same FIntel entry.

### Development/manual installation

Copy the compiled DLL into its own directory beneath Jellyfin's plugins
directory:

```text
Jellyfin plugins directory/
    FIntel/
        Jellyfin.Plugin.FIntel.dll
```

The compiled DLL is at
`Jellyfin.Plugin.FIntel/bin/Release/net10.0/Jellyfin.Plugin.FIntel.dll`. Restart
Jellyfin after copying or replacing it. A packaged release uses the ABI and
artifact metadata in `build.yaml`.

## Configure

1. Open the FIntel plugin configuration page in the Jellyfin dashboard.
2. Enter an absolute HTTP or HTTPS backend URL. Do not put the API key in the
   URL.
3. Enter the same token configured as `public_api.api_key` in FIntel. The token
   is stored in Jellyfin's standard plugin configuration XML and is shown as a
   password field; a Jellyfin server administrator can still read the XML.
4. Select a timeout from 1 through 120 seconds (default: 10).
5. Add each Jellyfin user GUID and its corresponding, case-sensitive FIntel
   username. Blank names, invalid GUIDs, and duplicate user IDs are rejected.
6. Save, then use **Test connectivity**. A successful result proves reachability,
   authentication, valid JSON, and backend database access.
7. Enable FIntel in each movie library's similarity-provider settings. Place
   FIntel first in provider order when its ranking should dominate blending.
8. Turn on the global **Enable FIntel** switch.

Jellyfin's item-level `GET /Items/{itemId}/Similar` endpoint invokes the
provider. Existing clients that use that endpoint receive the results without
client changes. Each requesting Jellyfin user must have a mapping; unmapped
users receive no FIntel results.

## Matching and failure behavior

Recommendations are resolved only to movies visible to the requesting user.
Matching tries TMDB, IMDb, TVDB, and then an exact normalized title plus year,
in that order. Ambiguous fallbacks, the source movie, duplicates, inaccessible
items, and unmatched entries are skipped without disturbing backend order.

Successful backend responses are cached for five minutes per normalized
backend URL, FIntel username, and media type. Failures and resolved Jellyfin
items are not cached. Backend, timeout, authentication, JSON, and matching
failures return no FIntel results, allowing Jellyfin's built-in providers and
all ordinary browsing/playback behavior to continue.

## Phase 1 boundary

Jellyfin 12.1 has no independent personalized-feed plugin contract for
`GET /Recommendations`; that endpoint selects the first batch-local provider
and bypasses configured remote providers. FIntel deliberately does not take
over that fragile path. Phase 1 therefore affects item similarity only.

Series, client modifications, JavaScript injection, explanation UI, ingestion
or training changes, database migrations, and Jellyfin core patches are out of
scope.

See [architecture](docs/architecture.md) and [development](docs/development.md).
