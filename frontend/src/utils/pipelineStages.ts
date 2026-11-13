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
  semantic_labels: "Optional semantic dimension labeling",
  predictive_daily: "Predictive pipeline worker",
  embeddinggemma2_generation: "Archived pipeline worker",
  tautulli_incremental: "Tautulli / library synchronization",
  library_embeddings: "Library embedding refresh",
  watch_embeddings: "Watch embedding refresh",
  user_embeddings: "User-profile reconstruction",
  batch_label: "Semantic dimension labeling",
  controller_dispatch: "Worker dispatch",
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
  seconds: "Recorded seconds", successes: "Successful labels", abstentions: "Abstentions",
  input_tokens: "Input tokens", output_tokens: "Output tokens", total_tokens: "Total tokens",
  estimated_cost_usd: "Estimated cost (USD)",
};

export function stageMetrics(metrics?: Record<string, number | boolean>) {
  return Object.entries(metrics ?? {}).filter(([key]) => key in metricLabels).map(([key, value]) => ({
    key, label: metricLabels[key], value: typeof value === "boolean" ? (value ? "Yes" : "No") :
      Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 4 }),
  }));
}

export function stageDuration(seconds: number | null | undefined, status: string, started?: string | null, completed?: string | null, observedAt?: string, timingActive = false, timingKnown = true) {
  if (status === "pending") return "Not started";
  if (status === "not_recorded") return "Not recorded";
  if (!timingKnown) return "Not separately timed";
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

export function stageProgress(metrics?: Record<string, number | boolean>) {
  const completed = metrics?.completed ?? metrics?.users;
  const expected = metrics?.expected;
  if (typeof completed !== "number" || typeof expected !== "number" ||
      !Number.isFinite(completed) || !Number.isFinite(expected) || completed < 0 || expected <= 0) return null;
  return { completed, expected, percent: Math.min(100, Math.round(completed / expected * 100)) };
}

export function readablePipelineLog(text: string | null | undefined): string {
  return (text ?? "").split("\n").map(line => {
    let value;
    try { value = JSON.parse(line); } catch {
      return line.length > 1000 && /":/.test(line)
        ? "The saved tail starts mid-record; retained stage output is loaded when available." : line;
    }
    if (!value || typeof value !== "object" || Array.isArray(value)) return line;
    const parts: string[] = [];
    if (value.at) parts.push(String(value.at));
    const key = value.stage_key || value.stage;
    if (key) parts.push(stageLabels[key] || String(key));
    if (value.status) parts.push(String(value.status));
    if (value.verified === true) parts.push("Pipeline publication verified");
    if (value.verification_only) parts.push("Verification only");
    for (const field of ["phase", "message", "reason", "error"]) {
      if (typeof value[field] === "string") parts.push(value[field]);
    }
    const metrics = value.event === "plexintel.pipeline-stage/1" ? value.metrics : value;
    parts.push(...stageMetrics(metrics).map(m => `${m.label}: ${m.value}`));
    if (value.elapsed_seconds != null && value.timing_known !== false &&
        !(key === "shap" && String(value.message).startsWith("Measured within scoring"))) {
      parts.push(`Elapsed: ${stageDuration(value.elapsed_seconds, value.status || "success")}`);
    }
    if (value.counts) {
      const labels: Record<string, string> = { media_embeddings: "Media vectors", watch_embeddings: "Watch vectors",
        user_embeddings: "User profiles", training_data: "Training rows", recommendations: "Predictions",
        shap_impact: "SHAP contributions", shap_prediction_context: "SHAP contexts" };
      for (const [name, count] of Object.entries(value.counts)) {
        if (labels[name] && typeof count === "number") parts.push(`${labels[name]}: ${count.toLocaleString()}`);
      }
    }
    if (value.semantic_labeling) parts.push(`Semantic labeling: ${value.semantic_labeling.status}${value.semantic_labeling.reason ? ` — ${value.semantic_labeling.reason}` : ""}`);
    // Unrecognized historical output remains available verbatim.
    return parts.length ? parts.join(" · ") : line;
  }).join("\n");
}

type LogStage = {
  stage_key: string; status: string; stdout_tail?: string | null; stderr_tail?: string | null;
  duration_seconds?: number | null; timing_known?: boolean;
  timing_active?: boolean; observed_at?: string;
  metrics?: Record<string, number | boolean>; message?: string | null;
};

export function operatorStages<T extends LogStage>(stages: T[], details?: T[]): T[] {
  if (!stages.some(s => ["predictive_daily", "embeddinggemma2_generation"].includes(s.stage_key))) return stages;
  const recorded = details || stages.filter(s => !["predictive_daily", "embeddinggemma2_generation"].includes(s.stage_key));
  if (!recorded.length) return stages;
  // Keep the earlier execution-stage view. SHAP runs within scoring; verification
  // and optional labeling belong to the publication log, not extra UI cards.
  const groups = [["source_sync"], ["media_text"], ["watch"], ["users"], ["training_data"],
    ["train_model"], ["score_model", "shap"], ["publication", "verification", "semantic_labels"]];
  const grouped = groups.flatMap(keys => {
    const children = keys.map(key => recorded.find(s => s.stage_key === key)).filter((s): s is T => !!s);
    if (!children.length) return [];
    const primary = children[0];
    const required = children.filter(s => s.stage_key !== "semantic_labels");
    const status = required.find(s => s.status === "failed" || s.status === "cancelled")?.status
      || (required.some(s => s.status === "started") ? "started" : primary.status);
    const active = required.find(s => s.status === "started");
    const timed = required.filter(s => s.stage_key !== "shap" || (s.timing_known !== false && s.duration_seconds != null));
    const known = timed.every(s => s.timing_known !== false && s.duration_seconds != null);
    return [{ ...primary, status,
      duration_seconds: known ? timed.reduce((total,s) => total + s.duration_seconds!, 0) : primary.duration_seconds,
      timing_active: active?.timing_active ?? false,
      observed_at: active?.observed_at ?? primary.observed_at,
    }];
  });
  // The actual worker record holds only output with no recoverable phase key;
  // the API excludes lines already assigned to a stage. No consolidated copy.
  const extra = stages.filter(s => !groups.flat().includes(s.stage_key) && !["predictive_daily", "embeddinggemma2_generation"].includes(s.stage_key));
  const workers = stages.filter(s => ["predictive_daily", "embeddinggemma2_generation"].includes(s.stage_key));
  return [...grouped, ...extra, ...workers.map(s => ({ ...s, worker_output: true }))];
}
