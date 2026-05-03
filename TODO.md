# TODO

This file is a carry-forward list for future sessions. It should track unresolved follow-up work and the context needed to resume it. Do not use it as a changelog, completed-work summary, or scratchpad for issues that have already been implemented.

## Recommendation Explanation Chips

- [ ] Split recommendation explanation chips into separate display groups instead of one mixed `semantic_themes` list:
  - `Title traits`: labels from positive SHAP contributors in media dimensions `0-767`.
  - `Taste match`: labels from positive SHAP contributors in user-preference dimensions `768-1535`.
- [ ] Update the API/UI payload so the frontend can render those groups separately.

## Context

- Combined embedding layout is `[media_embedding, user_embedding]`.
- Dimensions `0-767` are media dimensions.
- Dimensions `768-1535` are user-preference dimensions.
- Positive-only SHAP filtering and media/user dimension routing are already implemented; the remaining work is presentation/payload separation.
