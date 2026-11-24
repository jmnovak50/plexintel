# Recommendation presentation

Recommendation information has three separate purposes:

- **Title Traits:** existing media-side labels, retained pending the focused
  content-characterization decision described below.
- **Taste Match:** a factual, viewer-specific relationship from the existing
  version 2 viewing-history connection engine.
- **Score:** the existing engagement prediction. A relationship does not claim
  to explain or cause that score.

The authenticated desktop table places Title Traits and factual Taste Match in
Why This?. Mobile keeps the existing Why this? disclosure and card structure.
Factual text uses the green Taste Match treatment. The former separate history
connection panel is removed. No suitable connection means no Taste Match;
embedding-derived preference chips are not a fallback. Scope and watching/liking
wording come unchanged from `viewing_history_connection.display_text`.

## Consumers and compatibility

`viewing_history_connection` remains the structured private source. Existing
`explanation`, `semantic_themes` and `taste_match` payloads retain their prior
machine-readable semantics for compatibility; their legacy preference content
is not rendered as Taste Match by updated first-party consumers. Do not relabel
or overwrite those fields with prose. Authorized agent/MCP recommendations also
expose the existing `title_traits` array additively for explicit presentation.

The optional OpenWebUI REST adapter renders structured factual Taste Match and
Title Traits; a synopsis is identified as Summary. Its optional existing narrator
no longer receives legacy explanation labels or private connection evidence,
and is instructed to describe content facts without inferring preferences or
score causes. No narration or labeling request is needed for this rollout.
The optional adapter must be installed through the deployment mechanism of its
own OpenWebUI host; updating this checkout does not remotely install that file.

Recipient-specific HTML and plain-text digests use the same factual Taste Match,
with green treatment in HTML, alongside the existing media-side Title Traits.
Digest title-trait selection calls the same existing selection function. Preview
sends no mail. No private connection is added to unauthenticated or global-key
recommendation endpoints. Consumer authorization, filtering, ordering and
pagination remain unchanged.

## Title Traits decision boundary

The current implementation is not an independent title-content classifier.
`selected_embedding_labels(user,title,0,768,3)` selects eligible labels on the
media side using **positive SHAP values for that viewer's prediction**, groups
by display label and ranks by maximum SHAP contribution. Encoder/configuration,
current scored-context, review and suppression gates remain in force.
Consequently, one title embedding can produce different Title Traits for
separate viewers. A positive SHAP value does not establish that the semantic
label describes the title or that the coordinate is HIGH.

Existing coordinate labels interpret small HIGH/LOW title samples. Such a
label can summarize its sampled cluster without being a reliable category for
every other title. Model-estimated sample coverage and label confidence are not
independent validation of title-level accuracy. Deduplicating label strings does
not resolve that distinction. Sorting title coordinates instead of viewer SHAP
would remove viewer dependence but would not establish reliable content tags.

The bounded current-title inspection and illustrative title-only preview are
retained privately in `.secrets/taste-match-consolidation-20261124/`. They do not
change selection, labels, suppression or source metadata. No additional
label-generation or qualification campaign is part of this change.

For a subsequent decision, prefer canonical-title-scoped descriptors grounded
in existing metadata, with explicit provenance, unknowns and abstention. More
nuanced themes/style require their own validated title-level evidence, rather
than treating coordinate names or SHAP values as assertions. Existing review,
provenance and audit controls remain useful; coordinate analysis remains useful
for diagnostics. A replacement descriptor store or classifier is not implemented
here. Existing labels, assessments, histories, search and Dimension Explorer
remain available, and automatic labeling stays disabled.

## Deployment and rollback

Deploy the coherent backend and committed frontend with the existing shared
pipeline exclusion and guarded backend restart on birch. Verify no active
pipeline or labeling worker, preserve scheduling and current slot behavior, and
compare protected data/artifacts/settings before and after. No database migration,
imports, predictive run or labeling job is required. Keep historical hashed
frontend assets for cached clients. The rollback baseline for this presentation
rollout is `8d6c7ba`, preserving the incomplete-new-title ingestion fix.

Rollback only the presentation code/build to that baseline under the same guard;
keep the connection flag, persistence, invalidation and existing source data.
Do not drop tables or restore old metadata/labels as a presentation rollback.

Production activation of this presentation was verified on November 24, 2026,
using application commit `9d74a60`; subsequent operator-documentation commits do
not change its runtime files. Actual public HTTPS desktop/mobile screenshots,
recipient digest preview, authorized REST results, warm-reuse checks and the
focused Title Traits assessment are retained in the private rollout folder.
The startup comparison preserved all 46 existing production data tables and
model/configuration fingerprints. No migration or production job was run.

The optional external OpenWebUI adapter source and formatter were updated and
tested against actual production response data. This rollout does not claim to
have uploaded a separate copy to an external OpenWebUI host or reauthenticated
an OAuth MCP client. Existing OAuth settings and read scopes remain unchanged.
