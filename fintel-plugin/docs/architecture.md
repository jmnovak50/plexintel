# FIntel architecture

## System boundary

```text
Jellyfin client
    -> Jellyfin 12.1 server
        -> FIntel plugin (configuration, user mapping, HTTP, matching, cache)
            -> FIntel FastAPI service
                -> PostgreSQL and the existing recommendation model
                -> Tautulli metadata for external IDs
```

The C# plugin contains no recommendation model. It translates an authenticated,
user-scoped backend ranking into local Jellyfin movie objects. The FastAPI
addition is a read-only adapter over the existing recommendation query and does
not alter existing routes or introduce a database migration.

## Jellyfin 12.1 investigation findings

1. **Exact contracts.** `ILocalSimilarItemsProvider<TItemType>` returns resolved
   `BaseItem` instances. `IRemoteSimilarItemsProvider<TItemType>` returns
   references for Jellyfin to resolve. Both extend `ISimilarItemsProvider`.
   FIntel uses `ILocalSimilarItemsProvider<Movie>` because title/year fallback
   requires controlled local resolution.
2. **Relevant source.** The contracts are under
   `MediaBrowser.Controller/Library`. Orchestration is in
   `Emby.Server.Implementations/Library/SimilarItems/SimilarItemsManager.cs`;
   item similarity is exposed by `Jellyfin.Api/Controllers/LibraryController.cs`.
   `TmdbMovieSimilarProvider`, the built-in local providers, and
   `ListenBrainzSimilarArtistProvider` are the reference implementations.
3. **Registration.** Jellyfin discovers `ISimilarItemsProvider` implementations
   from loaded assemblies. Plugin dependencies are registered through the
   parameterless `IPluginServiceRegistrator.RegisterServices(IServiceCollection,
   IServerApplicationHost)` contract. FIntel registers its client, mapping,
   cache, matcher, and provider dependencies there.
4. **Library selection.** `LibraryOptions.TypeOptions` contains
   `SimilarItemProviders` and `SimilarItemProviderOrder`. Jellyfin 12.1 applies
   that allow-list to remote providers but always invokes compatible local
   providers. FIntel therefore self-gates on the movie library's configured
   provider list as well as its global switch.
5. **User context.** `SimilarItemsQuery.User` is the requesting Jellyfin user.
   Its GUID is resolved only through explicit plugin mappings; the plugin never
   assumes that Jellyfin and FIntel usernames match.
6. **Order.** A local provider's returned list position becomes its per-provider
   ranking signal. FIntel preserves backend order. `SimilarItemsManager` may
   blend that list with other providers using configured provider order, so
   administrators should place FIntel first when desired.
7. **Native client consumption.** Item-level
   `GET /Items/{itemId}/Similar` uses `SimilarItemsManager`; clients showing
   More Like This consume FIntel results without client modification.
8. **Constraints.** `GET /Recommendations` has no independent personalized-feed
   provider contract. It uses the first `IBatchLocalSimilarItemsProvider`, not
   the configured remote-provider path. FIntel does not rely on ordering itself
   first in that internal list and does not patch Jellyfin core.

## Request path

For a movie similarity request, FIntel verifies the global and per-library
switches, resolves `query.User.Id`, obtains a successful cached ranking or calls
the backend, and asks `IMediaMatcher` to resolve visible library movies. The
matcher loads movies through an `InternalItemsQuery(user)`, which carries
Jellyfin's user access filter. It then evaluates each backend entry in rank
order: TMDB, IMDb, TVDB, exact normalized title/year.

Title normalization uses invariant case folding, Unicode decomposition with
diacritic removal, punctuation removal, and whitespace collapsing. A title/year
key must identify exactly one accessible movie. Results are not cached because
visibility and library state can change.

## Failure and security model

The API token is sent only in `X-API-Key`. It is never placed in query strings,
responses, or explicit logs. The health endpoint requires the same token and
performs a database query. The plugin health endpoint requires Jellyfin's
elevated administrator policy and exposes only four booleans/timing fields plus
a bounded diagnostic message.

Only successful recommendation responses enter the five-minute in-process
cache. Concurrent identical misses share one request. Exceptions at the HTTP,
deserialization, cache, matching, or provider boundary yield an empty FIntel
list so other Jellyfin providers continue normally. There are no background
workers or unmanaged resources.

## Independent-feed limitation

Phase 1 intentionally proves personalized native consumption through movie
similarity. A standalone home-screen FIntel row or replacement recommendation
feed needs a future upstream extension point or client work and is not presented
as supported here.
