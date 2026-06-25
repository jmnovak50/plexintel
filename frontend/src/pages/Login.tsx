import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Check,
  Copy,
  ExternalLink,
  KeyRound,
  Loader2,
  Tv,
} from "lucide-react";

const PLEX_LINK_URL = "https://plex.tv/link";

const STEPS = [
  {
    icon: Tv,
    title: "Use your Plex account",
    description: "Sign in with the same credentials you use to watch on Plex.",
  },
  {
    icon: KeyRound,
    title: "Copy your linking code",
    description: "Tap the code below to copy it to your clipboard.",
  },
  {
    icon: ExternalLink,
    title: "Authorize at Plex",
    description: "Open plex.tv/link and enter the code when prompted.",
  },
] as const;

export default function Login() {
  const [pin, setPin] = useState<string | null>(null);
  const [pinId, setPinId] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [copied, setCopied] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetch("/api/auth/initiate")
      .then((res) => res.json())
      .then((data) => {
        setPin(data.code);
        setPinId(data.pin_id);
        setPolling(true);
      });
  }, []);

  useEffect(() => {
    if (!polling || !pinId) return;

    const interval = setInterval(() => {
      fetch(`/api/auth/status/${pinId}`)
        .then((res) => res.json())
        .then((data) => {
          if (data.authenticated) {
            clearInterval(interval);
            navigate("/recs");
          }
        });
    }, 10000);

    return () => clearInterval(interval);
  }, [polling, pinId, navigate]);

  const copyPin = async () => {
    if (!pin) return;
    try {
      await navigator.clipboard.writeText(pin);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard may be unavailable in some browsers or contexts.
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-amber-50/40 px-4 py-10 sm:py-16">
      <div className="mx-auto w-full max-w-lg">
        <header className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center overflow-hidden rounded-2xl shadow-md shadow-amber-200/60 ring-1 ring-amber-200/50">
            <img
              src="/favicon.ico"
              alt=""
              className="h-full w-full object-cover"
            />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            Welcome to PlexIntel
          </h1>
          <p className="mt-3 text-base leading-relaxed text-slate-600">
            Connect your Plex library to unlock personalized movie and show
            recommendations tailored to your taste.
          </p>
        </header>

        <main className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-xl shadow-slate-200/50">
          {!pin ? (
            <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
              <Loader2
                aria-hidden="true"
                className="animate-spin text-amber-500"
                size={32}
                strokeWidth={2}
              />
              <p className="text-sm font-medium text-slate-700">
                Generating your secure linking code…
              </p>
            </div>
          ) : (
            <>
              <div className="border-b border-slate-100 bg-slate-50/80 px-6 py-5">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                  How to sign in
                </h2>
                <ol className="mt-4 space-y-4">
                  {STEPS.map((step, index) => {
                    const Icon = step.icon;
                    return (
                      <li key={step.title} className="flex gap-3 text-left">
                        <div className="flex shrink-0 flex-col items-center">
                          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100 text-sm font-bold text-amber-800">
                            {index + 1}
                          </span>
                          {index < STEPS.length - 1 && (
                            <span
                              aria-hidden="true"
                              className="mt-1 h-full w-px flex-1 bg-slate-200"
                            />
                          )}
                        </div>
                        <div className="pb-1 pt-0.5">
                          <div className="flex items-center gap-2">
                            <Icon
                              aria-hidden="true"
                              className="text-amber-600"
                              size={16}
                              strokeWidth={2}
                            />
                            <p className="font-semibold text-slate-900">
                              {step.title}
                            </p>
                          </div>
                          <p className="mt-1 text-sm leading-relaxed text-slate-600">
                            {step.description}
                          </p>
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </div>

              <div className="px-6 py-8 text-center">
                <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Your linking code
                </p>
                <button
                  type="button"
                  onClick={() => void copyPin()}
                  className="group relative mx-auto flex w-full max-w-xs items-center justify-center gap-3 rounded-xl border-2 border-dashed border-amber-200 bg-amber-50 px-6 py-5 transition-colors hover:border-amber-300 hover:bg-amber-100/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2"
                  aria-label={copied ? "Code copied" : "Copy linking code"}
                >
                  <span className="font-mono text-4xl font-bold tracking-[0.35em] text-slate-900 sm:text-5xl">
                    {pin}
                  </span>
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 transition-colors group-hover:text-amber-700">
                    {copied ? (
                      <Check aria-hidden="true" size={20} strokeWidth={2} />
                    ) : (
                      <Copy aria-hidden="true" size={20} strokeWidth={2} />
                    )}
                  </span>
                </button>
                <p className="mt-2 text-xs text-slate-500">
                  {copied ? "Copied to clipboard" : "Click the code to copy"}
                </p>

                <a
                  href={PLEX_LINK_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 focus-visible:ring-offset-2 sm:w-auto"
                >
                  <ExternalLink aria-hidden="true" size={16} strokeWidth={2} />
                  Open plex.tv/link
                </a>
              </div>

              <div className="flex items-center justify-center gap-2 border-t border-slate-100 bg-slate-50/60 px-6 py-4 text-sm text-slate-600">
                <Loader2
                  aria-hidden="true"
                  className="animate-spin text-amber-500"
                  size={16}
                  strokeWidth={2}
                />
                <span>Waiting for Plex authorization — this page will continue automatically.</span>
              </div>
            </>
          )}
        </main>

        <p className="mt-6 text-center text-xs leading-relaxed text-slate-500">
          PlexIntel only reads your watch history to generate recommendations.
          Your credentials are handled entirely by Plex.
        </p>
      </div>
    </div>
  );
}
