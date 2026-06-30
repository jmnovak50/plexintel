import { AlertCircle, CheckCircle2 } from 'lucide-react';

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="mb-4 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} strokeWidth={2} />
      <p>{message}</p>
    </div>
  );
}

export function SuccessBanner({ message }: { message: string }) {
  return (
    <div className="mb-4 flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
      <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={16} strokeWidth={2} />
      <p>{message}</p>
    </div>
  );
}
