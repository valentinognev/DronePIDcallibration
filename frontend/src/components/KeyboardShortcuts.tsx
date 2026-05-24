import { useEffect } from 'react';
import { useKeyboardShortcuts } from '../lib/utils';
import { useSessionStore } from '../store/sessionStore';

/** Global keyboard shortcuts: Ctrl+R refresh, Ctrl+O focus file input */
export function KeyboardShortcuts() {
  const refreshTraces = useSessionStore((s) => s.refreshTraces);

  useEffect(() => {
    return useKeyboardShortcuts({
      'ctrl+r': () => refreshTraces(),
    });
  }, [refreshTraces]);

  return null;
}
