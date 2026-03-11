import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

interface AdminMe {
  username: string;
  friendly_name: string | null;
  display_name: string | null;
  is_admin: boolean;
}

interface SettingField {
  key: string;
  label: string;
  description: string;
  type: "string" | "integer" | "float" | "boolean";
  secret: boolean;
  default_value: string | number | boolean | null;
  source: string;
  updated_at: string | null;
  updated_by: string | null;
  has_value: boolean;
  value: string | number | boolean | null;
  masked_value: string | null;
  choices: string[];
  minimum: number | null;
  maximum: number | null;
}

interface SettingSection {
  key: string;
  label: string;
  fields: SettingField[];
}

type DraftMap = Record<string, string>;

function formatDate(value: string | null) {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

function buildFieldDraft(field: SettingField) {
  if (field.secret) return "";
  if (field.type === "boolean") {
    return String(Boolean(field.value));
  }
  if (field.value === null || field.value === undefined) return "";
  return String(field.value);
}

function serializeDraft(field: SettingField, draftValue: string) {
  if (draftValue === "") return undefined;
  if (field.type === "boolean") return draftValue === "true";
  if (field.type === "integer") return Number.parseInt(draftValue, 10);
  if (field.type === "float") return Number.parseFloat(draftValue);
  return draftValue;
}

function sourceLabel(source: string) {
  switch (source) {
    case "admin_ui":
      return "Saved in admin";
    case "env_bootstrap":
      return "Imported from env";
    case "env":
      return "Env fallback";
    case "cleared":
      return "Reset to default";
    case "override":
      return "Pending override";
    default:
      return "Code default";
  }
}

export default function AdminSettings() {
  const navigate = useNavigate();
  const [me, setMe] = useState<AdminMe | null>(null);
  const [sections, setSections] = useState<SettingSection[]>([]);
  const [drafts, setDrafts] = useState<DraftMap>({});
  const [baselineDrafts, setBaselineDrafts] = useState<DraftMap>({});
  const [clearedKeys, setClearedKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingSection, setSavingSection] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [testMessages, setTestMessages] = useState<Record<string, string>>({});

  function applySections(nextSections: SettingSection[]) {
    const nextDrafts: DraftMap = {};
    nextSections.forEach((section) => {
      section.fields.forEach((field) => {
        nextDrafts[field.key] = buildFieldDraft(field);
      });
    });
    setSections(nextSections);
    setDrafts(nextDrafts);
    setBaselineDrafts(nextDrafts);
    setClearedKeys([]);
  }

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
      setLoading(true);
      setError(null);
      try {
        const meRes = await fetch("/api/admin/me", { credentials: "include" });
        if (!meRes.ok) {
          if (meRes.status === 401 || meRes.status === 403) {
            navigate("/", { replace: true });
            return;
          }
          throw new Error(`Unable to load admin identity (${meRes.status})`);
        }

        const meData: AdminMe = await meRes.json();
        if (!mounted) return;
        setMe(meData);

        if (!meData.is_admin) {
          navigate("/recs", { replace: true });
          return;
        }

        const settingsRes = await fetch("/api/admin/settings", { credentials: "include" });
        if (!settingsRes.ok) {
          throw new Error(`Unable to load settings (${settingsRes.status})`);
        }

        const settingsData = await settingsRes.json();
        if (!mounted) return;
        applySections(settingsData.sections ?? []);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load settings.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    bootstrap();
    return () => {
      mounted = false;
    };
  }, [navigate]);

  function updateDraft(key: string, value: string) {
    setDrafts((current) => ({ ...current, [key]: value }));
    setClearedKeys((current) => current.filter((entry) => entry !== key));
  }

  function resetField(key: string) {
    setClearedKeys((current) => (current.includes(key) ? current : [...current, key]));
    setDrafts((current) => ({ ...current, [key]: "" }));
  }

  function buildSectionPayload(section: SettingSection) {
    const updates: Record<string, string | number | boolean> = {};
    const sectionClearKeys = section.fields
      .map((field) => field.key)
      .filter((key) => clearedKeys.includes(key));

    section.fields.forEach((field) => {
      if (sectionClearKeys.includes(field.key)) return;
      const draftValue = drafts[field.key] ?? "";

      if (field.secret) {
        if (draftValue.trim() !== "") {
          updates[field.key] = draftValue;
        }
        return;
      }

      if ((baselineDrafts[field.key] ?? "") === draftValue) return;
      const serialized = serializeDraft(field, draftValue);
      if (serialized !== undefined && !Number.isNaN(serialized)) {
        updates[field.key] = serialized;
      }
    });

    return { updates, clear_keys: sectionClearKeys };
  }

  async function saveSection(section: SettingSection) {
    setSavingSection(section.key);
    setError(null);
    setStatus(null);
    try {
      const payload = buildSectionPayload(section);
      const response = await fetch("/api/admin/settings", {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Failed saving ${section.label}.`);
      }
      applySections(data.sections ?? []);
      setStatus(`${section.label} saved.`);
      setTestMessages((current) => ({ ...current, [section.key]: "" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : `Failed saving ${section.label}.`);
    } finally {
      setSavingSection(null);
    }
  }

  async function testSection(sectionKey: "connectivity" | "llm_embeddings") {
    const section = sections.find((entry) => entry.key === sectionKey);
    if (!section) return;

    const path =
      sectionKey === "connectivity"
        ? "/api/admin/settings/test/tautulli"
        : "/api/admin/settings/test/ollama";

    const relevantKeys =
      sectionKey === "connectivity"
        ? section.fields.filter((field) => field.key.startsWith("tautulli."))
        : section.fields.filter(
            (field) => field.key.startsWith("ollama.") || field.key === "labeling.ollama_model"
          );

    const payload = buildSectionPayload({ ...section, fields: relevantKeys });

    setTestMessages((current) => ({ ...current, [sectionKey]: "Testing…" }));
    try {
      const response = await fetch(path, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Connection test failed.");
      }

      if (sectionKey === "connectivity") {
        setTestMessages((current) => ({
          ...current,
          [sectionKey]: `Connected to Tautulli. Users visible: ${data.user_count ?? "unknown"}.`,
        }));
      } else {
        const missing = Array.isArray(data.missing_models) && data.missing_models.length > 0
          ? ` Missing models: ${data.missing_models.join(", ")}.`
          : "";
        setTestMessages((current) => ({
          ...current,
          [sectionKey]: `Connected to Ollama. Models found: ${data.available_models?.length ?? 0}.${missing}`,
        }));
      }
    } catch (e) {
      setTestMessages((current) => ({
        ...current,
        [sectionKey]: e instanceof Error ? e.message : "Connection test failed.",
      }));
    }
  }

  return (
    <div className="min-h-screen bg-stone-100 text-slate-900">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
        <div className="rounded-3xl border border-stone-200 bg-[linear-gradient(135deg,#0f172a_0%,#1e293b_48%,#f59e0b_48%,#fef3c7_100%)] p-[1px] shadow-lg">
          <div className="rounded-[calc(1.5rem-1px)] bg-stone-50 px-6 py-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-[0.35em] text-amber-700">Admin Settings Workspace</p>
                <h1 className="font-serif text-3xl font-semibold tracking-tight text-slate-900">
                  Live application settings
                </h1>
                <p className="max-w-2xl text-sm text-slate-600">
                  Save operational settings to Postgres, test external services, and stop relying on a
                  long-lived root <code>.env</code>.
                </p>
                <p className="text-sm text-slate-500">
                  Signed in as {me?.display_name || me?.username || "…"}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Link
                  to="/admin"
                  className="inline-flex items-center rounded-full border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
                >
                  Persona View
                </Link>
                <Link
                  to="/recs"
                  className="inline-flex items-center rounded-full border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
                >
                  Recommendations
                </Link>
              </div>
            </div>
          </div>
        </div>

        {error && (
          <div className="rounded-2xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {status && (
          <div className="rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {status}
          </div>
        )}

        {loading ? (
          <div className="rounded-2xl border border-stone-200 bg-white px-5 py-6 text-sm text-slate-500 shadow-sm">
            Loading settings…
          </div>
        ) : (
          <div className="grid gap-5">
            {sections.map((section) => (
              <section key={section.key} className="rounded-3xl border border-stone-200 bg-white p-5 shadow-sm">
                <div className="flex flex-col gap-3 border-b border-stone-200 pb-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h2 className="font-serif text-2xl font-semibold text-slate-900">{section.label}</h2>
                    <p className="mt-1 text-sm text-slate-500">
                      Changes are stored in Postgres and applied on the next request or script run.
                    </p>
                    {testMessages[section.key] && (
                      <p className="mt-2 text-sm text-sky-700">{testMessages[section.key]}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    {section.key === "connectivity" && (
                      <button
                        type="button"
                        onClick={() => testSection("connectivity")}
                        className="rounded-full border border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-700 hover:bg-sky-100"
                      >
                        Test Tautulli
                      </button>
                    )}
                    {section.key === "llm_embeddings" && (
                      <button
                        type="button"
                        onClick={() => testSection("llm_embeddings")}
                        className="rounded-full border border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-700 hover:bg-sky-100"
                      >
                        Test Ollama
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => saveSection(section)}
                      disabled={savingSection === section.key}
                      className="rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {savingSection === section.key ? "Saving…" : `Save ${section.label}`}
                    </button>
                  </div>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  {section.fields.map((field) => {
                    const isCleared = clearedKeys.includes(field.key);
                    const sourceText = isCleared ? "Will reset on save" : sourceLabel(field.source);
                    const sourceClassName = isCleared
                      ? "bg-amber-100 text-amber-800"
                      : "bg-slate-100 text-slate-700";

                    return (
                      <div key={field.key} className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="text-sm font-semibold text-slate-900">{field.label}</h3>
                              {field.secret && (
                                <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white">
                                  Secret
                                </span>
                              )}
                            </div>
                            <p className="mt-1 text-xs text-slate-500">{field.key}</p>
                            {field.description && (
                              <p className="mt-2 text-sm text-slate-600">{field.description}</p>
                            )}
                          </div>
                          <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${sourceClassName}`}>
                            {sourceText}
                          </span>
                        </div>

                        <div className="mt-4 space-y-3">
                          {field.choices.length > 0 ? (
                            <select
                              value={drafts[field.key] ?? ""}
                              onChange={(event) => updateDraft(field.key, event.target.value)}
                              className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm"
                            >
                              {field.choices.map((choice) => (
                                <option key={choice} value={choice}>
                                  {choice}
                                </option>
                              ))}
                            </select>
                          ) : field.type === "boolean" ? (
                            <select
                              value={drafts[field.key] ?? "false"}
                              onChange={(event) => updateDraft(field.key, event.target.value)}
                              className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm"
                            >
                              <option value="true">Enabled</option>
                              <option value="false">Disabled</option>
                            </select>
                          ) : (
                            <input
                              type={field.type === "integer" || field.type === "float" ? "number" : field.secret ? "password" : "text"}
                              step={field.type === "float" ? "any" : field.type === "integer" ? "1" : undefined}
                              min={field.minimum ?? undefined}
                              max={field.maximum ?? undefined}
                              value={drafts[field.key] ?? ""}
                              placeholder={field.secret ? field.masked_value || "Enter new value" : ""}
                              onChange={(event) => updateDraft(field.key, event.target.value)}
                              className="w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm"
                            />
                          )}

                          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
                            <div className="space-y-1">
                              <p>
                                Current:{" "}
                                {field.secret
                                  ? field.masked_value || "Not set"
                                  : field.has_value
                                    ? String(field.value)
                                    : "Not set"}
                              </p>
                              <p>
                                Default:{" "}
                                {field.default_value === null || field.default_value === undefined
                                  ? "None"
                                  : String(field.default_value)}
                              </p>
                              <p>
                                Updated: {formatDate(field.updated_at)}
                                {field.updated_by ? ` by ${field.updated_by}` : ""}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => resetField(field.key)}
                              className="rounded-full border border-stone-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-stone-100"
                            >
                              Reset to default
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
