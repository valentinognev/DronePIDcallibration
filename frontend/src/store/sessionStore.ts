import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../lib/api';
import type { FileInfo, TraceData } from '../lib/api';

export interface AppSettings {
  firmware: string;
  theme: 'dark' | 'light';
  plotR: boolean;
  plotP: boolean;
  plotY: boolean;
  lineSmooth: number;
  lineWidth: number;
  yScale: number;
  singlePanel: boolean;
}

interface SessionState {
  sessionId: string | null;
  files: FileInfo[];
  selectedFileIdx: number;
  selectedLogIdx: number;
  traceData: TraceData | null;
  loading: boolean;
  error: string | null;
  settings: AppSettings;
  visibleTraces: string[];

  setSettings: (s: Partial<AppSettings>) => void;
  toggleTrace: (trace: string) => void;
  initSession: () => Promise<void>;
  uploadFiles: (files: FileList) => Promise<void>;
  refreshTraces: () => Promise<void>;
  setSelectedFile: (idx: number) => void;
  setEpoch: (start: number, end: number) => Promise<void>;
  reset: () => void;
}

const DEFAULT_TRACES = [
  'gyro', 'setpoint', 'pterm', 'iterm', 'dterm', 'dterm_pf', 'fterm',
  'pidsum', 'piderr', 'throttle', 'motor_0', 'motor_1', 'motor_2', 'motor_3',
];

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      sessionId: null,
      files: [],
      selectedFileIdx: 0,
      selectedLogIdx: 0,
      traceData: null,
      loading: false,
      error: null,
      settings: {
        firmware: 'betaflight',
        theme: 'dark',
        plotR: true,
        plotP: true,
        plotY: true,
        lineSmooth: 1,
        lineWidth: 3,
        yScale: 500,
        singlePanel: false,
      },
      visibleTraces: ['gyro', 'setpoint', 'pterm', 'iterm', 'dterm', 'throttle', 'motor_0', 'motor_1', 'motor_2', 'motor_3'],

      setSettings: (s) => set((st) => ({ settings: { ...st.settings, ...s } })),
      toggleTrace: (trace) =>
        set((st) => ({
          visibleTraces: st.visibleTraces.includes(trace)
            ? st.visibleTraces.filter((t) => t !== trace)
            : [...st.visibleTraces, trace],
        })),

      initSession: async () => {
        const { settings } = get();
        set({ loading: true, error: null });
        try {
          const session = await api.createSession(settings.firmware);
          set({ sessionId: session.session_id, files: [], traceData: null });
        } catch (e) {
          set({ error: String(e) });
        } finally {
          set({ loading: false });
        }
      },

      uploadFiles: async (fileList) => {
        let { sessionId } = get();
        if (!sessionId) {
          await get().initSession();
          sessionId = get().sessionId;
        }
        if (!sessionId) return;

        set({ loading: true, error: null });
        try {
          for (const file of Array.from(fileList)) {
            await api.uploadFile(sessionId, file);
          }
          const session = await api.getSession(sessionId);
          set({ files: session.files, selectedFileIdx: session.files.length - 1 });
          await get().refreshTraces();
        } catch (e) {
          set({ error: String(e) });
        } finally {
          set({ loading: false });
        }
      },

      refreshTraces: async () => {
        const { sessionId, selectedFileIdx, selectedLogIdx, visibleTraces, settings } = get();
        if (!sessionId || get().files.length === 0) return;

        const axes: number[] = [];
        if (settings.plotR) axes.push(0);
        if (settings.plotP) axes.push(1);
        if (settings.plotY) axes.push(2);

        set({ loading: true });
        try {
          const data = await api.getTraces(sessionId, {
            file_idx: selectedFileIdx,
            log_idx: selectedLogIdx,
            axes,
            traces: visibleTraces.filter((t) => DEFAULT_TRACES.includes(t)),
            smooth_factor: settings.lineSmooth,
          });
          set({ traceData: data, error: null });
        } catch (e) {
          set({ error: String(e) });
        } finally {
          set({ loading: false });
        }
      },

      setSelectedFile: (idx) => {
        set({ selectedFileIdx: idx, selectedLogIdx: 0 });
        get().refreshTraces();
      },

      setEpoch: async (start, end) => {
        const { sessionId, selectedFileIdx, selectedLogIdx } = get();
        if (!sessionId) return;
        await api.updateEpoch(sessionId, selectedFileIdx, selectedLogIdx, start, end);
        await get().refreshTraces();
      },

      reset: () =>
        set({
          files: [],
          traceData: null,
          selectedFileIdx: 0,
          error: null,
        }),
    }),
    {
      name: 'pidbox-settings',
      partialize: (s) => ({ settings: s.settings, visibleTraces: s.visibleTraces }),
    },
  ),
);
