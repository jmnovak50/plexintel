# TODO

## Recommendation Labels

- [ ] Apply `db_update_positive_recommendation_labels.sql` to the target database.
- [ ] Back up and clear existing `embedding_labels` with `reset_embedding_labels.py --scope all --execute`.
- [ ] Re-run `batch_label_embeddings.py --label --save_label --refresh_existing --export_csv shap_labels_<date>.csv --limit 100`.
- [ ] Spot-check known bad examples, including `The Killer`, after relabeling.
- [ ] Consider splitting UI chips into `Title traits` and `Taste match` instead of mixed labels.

## Notes

- Combined embedding layout is `[media_embedding, user_embedding]`.
- Dimensions `0-767` are media dimensions.
- Dimensions `768-1535` are user-preference dimensions.
- Recommendation chips should represent positive SHAP contributors only.
