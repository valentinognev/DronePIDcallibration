import { useEffect, useState, type ComponentType } from 'react';
import { useLocation } from 'react-router-dom';

export interface PersistentRoute {
  path: string;
  Component: ComponentType;
}

/**
 * Keeps visited analysis pages mounted so local state (plots, params) survives tab switches.
 * Pages mount on first visit only to avoid loading every tool at startup.
 */
export function PersistentRoutes({ routes }: { routes: PersistentRoute[] }) {
  const { pathname } = useLocation();
  const [mountedPaths, setMountedPaths] = useState<Set<string>>(() => new Set([pathname]));

  useEffect(() => {
    setMountedPaths((prev) => {
      if (prev.has(pathname)) return prev;
      const next = new Set(prev);
      next.add(pathname);
      return next;
    });
  }, [pathname]);

  // Plotly only listens to window resize; reflow when a kept-alive tab becomes visible.
  useEffect(() => {
    const id = window.requestAnimationFrame(() => {
      window.dispatchEvent(new Event('resize'));
    });
    return () => window.cancelAnimationFrame(id);
  }, [pathname]);

  return (
    <div className="flex flex-1 flex-col min-h-0 min-w-0 w-full">
      {routes.map(({ path, Component }) => {
        if (!mountedPaths.has(path)) return null;
        const active = pathname === path;
        return (
          <div
            key={path}
            className={active ? 'flex flex-1 flex-col min-h-0 min-w-0 w-full' : 'hidden'}
            aria-hidden={!active}
          >
            <Component />
          </div>
        );
      })}
    </div>
  );
}
