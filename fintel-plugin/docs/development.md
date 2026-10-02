# Development

## Toolchain

Install the .NET 10 SDK and a Python environment containing this repository's
existing dependencies. The plugin is pinned to the Jellyfin 12.1.0 packages and
targets `net10.0`.

```bash
dotnet --info
dotnet restore fintel-plugin/Jellyfin.Plugin.FIntel.slnx
dotnet build fintel-plugin/Jellyfin.Plugin.FIntel.slnx -c Release
dotnet test fintel-plugin/Jellyfin.Plugin.FIntel.slnx -c Release
plexenv/bin/python -m pytest -q \
  tests/test_fintel_routes.py tests/test_public_recommendation_routes.py
```

The initial ABI probe should compile a class implementing
`ILocalSimilarItemsProvider<Movie>` and a parameterless class implementing
`IPluginServiceRegistrator` against the same package versions before changing
provider code.

## Package

Build Release, then package `Jellyfin.Plugin.FIntel.dll` with `build.yaml` for
target ABI `12.1.0.0`. Do not include Jellyfin's Controller or Model assemblies;
the server supplies them. A release version must keep the project assembly
version and `build.yaml` version aligned.

## Manual Jellyfin 12.1 smoke test

1. Install the plugin DLL in its own plugin directory and start Jellyfin 12.1.
2. Confirm the log reports plugin initialization and no load/type errors.
3. Save an absolute backend URL, API token, 1-120 second timeout, and two user
   mappings. Confirm the connectivity test reports reachable, authenticated,
   and valid response.
4. Enable FIntel for one movie library and place it first in similarity-provider
   order.
5. As each mapped user, call `GET /Items/{movieId}/Similar` (or open More Like
   This) and verify that their independently ranked results differ as expected.
6. Confirm TMDB/IMDb matches and an unambiguous title/year fallback resolve only
   to movies visible to that user. Confirm an ambiguous title/year is absent.
7. Stop the FastAPI backend. Repeat browsing, playback, and similarity calls;
   Jellyfin must remain usable and built-in similarity must still return.
8. Confirm `GET /Recommendations` is unchanged.
9. Uninstall or disable the plugin and restart Jellyfin; no worker or unmanaged
   state should remain.

This repository cannot substitute automated unit tests for the live Jellyfin
load and two-user smoke test. Record the exact Jellyfin build, plugin checksum,
and observations when performing it.

## Future work

Series matching is a future phase. A standalone recommendation feed depends on
an upstream Jellyfin provider contract or explicit client changes. Neither is
implemented in this vertical slice.
