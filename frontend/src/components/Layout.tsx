import { Link, useLocation } from 'react-router-dom';

const NAV = [
  { path: '/', label: 'Log Viewer' },
  { path: '/spectral', label: 'Spectral Analyzer' },
  { path: '/step-response', label: 'Step Response' },
  { path: '/freq-throttle', label: 'Freq × Throttle' },
  { path: '/freq-time', label: 'Freq × Time' },
  { path: '/filter-sim', label: 'Filter Sim' },
  { path: '/setup-info', label: 'Setup Info' },
  { path: '/stats', label: 'PID Stats' },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const loc = useLocation();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b px-4 py-2 flex items-center justify-between" style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary)' }}>
        <div className="flex items-center gap-6">
          <h1 className="text-lg font-bold">PIDToolBox</h1>
          <nav className="flex gap-1 flex-wrap">
            {NAV.map(({ path, label }) => (
              <Link
                key={path}
                to={path}
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  loc.pathname === path
                    ? 'bg-blue-900/50 text-blue-300'
                    : 'text-[var(--text-secondary)] hover:text-white hover:bg-white/5'
                }`}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
        <span className="text-xs text-[var(--text-secondary)]">v0.1.18</span>
      </header>
      <main className="flex-1 p-4 overflow-auto">{children}</main>
    </div>
  );
}
