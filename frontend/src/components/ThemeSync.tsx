import { useEffect } from 'react';
import { useSessionStore } from '../store/sessionStore';

export function ThemeSync() {
  const theme = useSessionStore((s) => s.settings.theme);

  useEffect(() => {
    document.body.className = theme;
  }, [theme]);

  return null;
}
