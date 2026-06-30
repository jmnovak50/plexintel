import { Moon, Sun } from 'lucide-react';
import type { ReactNode } from 'react';
import AdminNav from './AdminNav';
import { useTheme } from '../context/ThemeContext';

interface AppShellProps {
  eyebrow?: string;
  title: string;
  description?: string;
  signedInAs?: string | null;
  headerActions?: ReactNode;
  showAdminNav?: boolean;
  maxWidthClass?: string;
  children: ReactNode;
}

export default function AppShell({
  eyebrow,
  title,
  description,
  signedInAs,
  headerActions,
  showAdminNav = true,
  maxWidthClass = 'max-w-7xl',
  children,
}: AppShellProps) {
  const { darkMode, toggleDarkMode } = useTheme();

  return (
    <div className={`recs-page ${darkMode ? 'recs-dark' : ''}`}>
      <div className={`mx-auto w-full ${maxWidthClass} overflow-x-hidden px-3 py-6 sm:px-4 sm:py-8`}>
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            {eyebrow && (
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-600">{eyebrow}</p>
            )}
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">{title}</h1>
            {description && (
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">{description}</p>
            )}
            {signedInAs && (
              <p className="mt-2 text-sm text-slate-500">Signed in as {signedInAs}</p>
            )}
          </div>

          <div className="flex flex-col gap-3 sm:items-end">
            {headerActions && (
              <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                {headerActions}
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2 sm:justify-end">
              {showAdminNav && <AdminNav />}
              <button
                type="button"
                onClick={toggleDarkMode}
                className="recs-btn-secondary px-3 py-2"
                aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
                aria-pressed={darkMode}
              >
                {darkMode ? (
                  <Sun aria-hidden="true" size={16} strokeWidth={2} />
                ) : (
                  <Moon aria-hidden="true" size={16} strokeWidth={2} />
                )}
                <span className="sr-only">{darkMode ? 'Light mode' : 'Dark mode'}</span>
              </button>
            </div>
          </div>
        </div>

        {children}
      </div>
    </div>
  );
}
