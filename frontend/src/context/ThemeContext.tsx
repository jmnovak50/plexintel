import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

const STORAGE_KEY = 'plexintel.darkMode';

interface ThemeContextValue {
  darkMode: boolean;
  setDarkMode: (value: boolean) => void;
  toggleDarkMode: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readStoredDarkMode() {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [darkMode, setDarkModeState] = useState(readStoredDarkMode);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(darkMode));
    } catch {
      // Ignore storage failures (private browsing, etc.).
    }
  }, [darkMode]);

  const setDarkMode = useCallback((value: boolean) => {
    setDarkModeState(value);
  }, []);

  const toggleDarkMode = useCallback(() => {
    setDarkModeState((prev) => !prev);
  }, []);

  const value = useMemo(
    () => ({ darkMode, setDarkMode, toggleDarkMode }),
    [darkMode, setDarkMode, toggleDarkMode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}
