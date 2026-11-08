export const stageLabels: Record<string, string> = {
  source_sync: "Tautulli / library synchronization",
  media_text: "Media-text embedding refresh",
  watch: "Watch embedding refresh",
  users: "User-profile reconstruction",
  training_data: "Training data preparation",
  train_model: "Model training and quality validation",
  score_model: "Recommendation scoring",
  shap: "SHAP explanation generation",
  publication: "Production publication",
  verification: "Final verification",
};

const metricLabels: Record<string, string> = {
  expected: "Expected", completed: "Completed", succeeded: "Succeeded", failed: "Failed",
  pending: "Pending", reused: "Reused", inferred: "Inferred", new: "New", regenerated: "Regenerated",
  rebuilt: "Rebuilt", requests: "Inference requests", rows: "Training rows", users: "Users", predictions: "Predictions",
  contexts: "SHAP contexts", contributions: "SHAP contributions", limited_history_skips: "Limited-history skips",
  label_policy_skips: "Label-policy skips", metadata_seconds: "Metadata preparation (s)",
  context_seconds: "Working context (s)", inference_seconds: "Inference (s)", checkpoint_reused: "Checkpoint reused",
  previous_seconds: "Previous checkpoint duration (s)", chronological_balanced_accuracy: "Chronological balanced accuracy",
  chronological_average_precision: "Chronological AP", show_balanced_accuracy: "Show-heldout balanced accuracy",
  quality_passed: "Quality gates passed", new_media: "New media", new_watch_events: "New watch events",
  quarantined: "Quarantined events", verified_vectors: "Verified vectors", poster_requests: "Poster requests",
};

export function stageMetrics(metrics?: Record<string, number | boolean>) {
  return Object.entries(metrics ?? {}).filter(([key]) => key in metricLabels).map(([key, value]) => ({
    key, label: metricLabels[key], value: typeof value === "boolean" ? (value ? "Yes" : "No") :
      Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 4 }),
  }));
}

export function stageDuration(seconds: number | null | undefined, status: string, started?: string | null, completed?: string | null, observedAt?: string, timingActive = false) {
  if (status === "pending") return "Not started";
  if (status === "not_recorded") return "Not recorded";
  let elapsed = seconds;
  if (elapsed != null && timingActive && observedAt) elapsed += Math.max(0, (Date.now() - new Date(observedAt).getTime()) / 1000);
  if (elapsed == null && started) {
    const end = completed ? new Date(completed).getTime() : status === "started" ? Date.now() : NaN;
    elapsed = (end - new Date(started).getTime()) / 1000;
  }
  if (elapsed == null || !Number.isFinite(elapsed)) return "Not separately timed";
  const rounded = Math.max(0, Math.round(elapsed));
  return rounded < 60 ? `${rounded}s` : `${Math.floor(rounded / 60)}m ${rounded % 60}s`;
}
