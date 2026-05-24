import { useState } from 'react';
import { api } from '../lib/api';
import { useSessionStore } from '../store/sessionStore';

export function SetupInfoPage() {
  const { sessionId, files } = useSessionStore();
  const [fileA, setFileA] = useState(0);
  const [fileB, setFileB] = useState(1);
  const [diffOnly, setDiffOnly] = useState(false);
  const [rows, setRows] = useState<Array<{ line: number; key: string; value_a: string; value_b: string; diff: boolean }>>([]);
  const [names, setNames] = useState({ a: '', b: '' });

  const run = async () => {
    if (!sessionId) return;
    const data = await api.setupDiff({
      session_id: sessionId,
      file_idx_a: fileA,
      file_idx_b: fileB,
      differences_only: diffOnly,
    });
    setRows(data.rows as typeof rows);
    setNames({ a: data.file_a as string, b: data.file_b as string });
  };

  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-80px)]">
      <div className="flex gap-4 items-center panel">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={diffOnly} onChange={(e) => setDiffOnly(e.target.checked)} />
          Show Differences Only
        </label>
        <select className="select-input w-48" value={fileA} onChange={(e) => setFileA(Number(e.target.value))}>
          {files.map((f, i) => (
            <option key={f.file_id} value={i}>{f.original_name}</option>
          ))}
        </select>
        <select className="select-input w-48" value={fileB} onChange={(e) => setFileB(Number(e.target.value))}>
          {files.map((f, i) => (
            <option key={f.file_id} value={i}>{f.original_name}</option>
          ))}
        </select>
        <button className="btn-run" onClick={run} disabled={!sessionId || files.length < 2}>
          Compare
        </button>
      </div>

      <div className="flex-1 grid grid-cols-2 gap-2 overflow-auto">
        <SetupPanel title={names.a || 'File A'} rows={rows} side="a" />
        <SetupPanel title={names.b || 'File B'} rows={rows} side="b" />
      </div>
    </div>
  );
}

function SetupPanel({
  title,
  rows,
  side,
}: {
  title: string;
  rows: Array<{ line: number; key: string; value_a: string; value_b: string; diff: boolean }>;
  side: 'a' | 'b';
}) {
  return (
    <div className="panel overflow-auto font-mono text-xs">
      <h3 className="font-semibold mb-2 text-sm font-sans">{title}</h3>
      {rows.map((row) => (
        <div
          key={row.line}
          className={`flex gap-2 py-0.5 ${row.diff ? 'bg-red-900/40' : ''}`}
        >
          <span className="text-[var(--text-secondary)] w-8">{row.line}</span>
          <span className="flex-1">
            {row.key}: {side === 'a' ? row.value_a : row.value_b}
          </span>
        </div>
      ))}
      {rows.length === 0 && (
        <p className="text-[var(--text-secondary)]">Select two files and click Compare</p>
      )}
    </div>
  );
}
