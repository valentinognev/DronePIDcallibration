import { useEffect } from 'react';
import { useSessionStore } from '../store/sessionStore';

/** Rehydrate persisted session from the API once on app load. */
export function SessionBootstrap() {
  const restoreSession = useSessionStore((s) => s.restoreSession);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  return null;
}
