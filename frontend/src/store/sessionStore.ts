import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../lib/api';
import type { FileInfo, TraceData } from '../lib/api';
import { FALLBACK_FIRMWARES, type FirmwareOption } from '../lib/constants';

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
  firmwareOptions: FirmwareOption[];

  setSettings: (s: Partial<AppSettings>) => void;
  loadFirmwares: () => Promise<void>;
  setFirmware: (firmware: string, force?: boolean) => Promise<void>;
  toggleTrace: (trace: string) => void;
  initSession: () => Promise<void>;
  restoreSession: () => Promise<void>;
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

function fileListHasUlg(files: FileList): boolean {
  return Array.from(files).some((f) => f.name.toLowerCase().endsWith('.ulg'));
}

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
      firmwareOptions: FALLBACK_FIRMWARES,

      loadFirmwares: async () => {
        try {
          const list = await api.firmwares();
          if (list.length > 0) {
            set({ firmwareOptions: list });
          }
        } catch {
          // keep FALLBACK_FIRMWARES
        }
      },

      setFirmware: async (firmware, force = false) => {
        const { settings } = get();
        if (!force && settings.firmware === firmware) return;

        set({ loading: true, error: null });
        try {
          const session = await api.createSession(firmware);
          set({
            sessionId: session.session_id,
            settings: { ...settings, firmware },
            files: [],
            traceData: null,
            selectedFileIdx: 0,
            selectedLogIdx: 0,
            error: null,
          });
        } catch (e) {
          set({ error: String(e) });
        } finally {
          set({ loading: false });
        }
      },

      setSettings: (s) =>
        set((st) => {
          const settings = { ...st.settings, ...s };
          if (s.theme !== undefined) {
            document.body.className = s.theme;
          }
          return { settings };
        }),
      toggleTrace: (trace) =>
        set((st) => ({
          visibleTraces: st.visibleTraces.includes(trace)
            ? st.visibleTraces.filter((t) => t !== trace)
            : [...st.visibleTraces, trace],
        })),

      initSession: async () => {
        const { sessionId, settings } = get();
        if (sessionId) return;

        set({ loading: true, error: null });
        try {
          const session = await api.createSession(settings.firmware);
          set({ sessionId: session.session_id });
        } catch (e) {
          set({ error: String(e) });
        } finally {
          set({ loading: false });
        }
      },

      restoreSession: async () => {
        const { sessionId } = get();
        if (!sessionId) return;

        set({ loading: true, error: null });
        try {
          const session = await api.getSession(sessionId);
          set({ files: session.files, error: null });
          if (session.files.length > 0) {
            await get().refreshTraces();
          }
        } catch {
          set({
            sessionId: null,
            files: [],
            traceData: null,
            selectedFileIdx: 0,
            selectedLogIdx: 0,
            error: null,
          });
        } finally {
          set({ loading: false });
        }
      },

      uploadFiles: async (fileList) => {
        if (fileListHasUlg(fileList)) {
          const { settings, sessionId } = get();
          let needPx4Session = settings.firmware !== 'px4';
          if (!needPx4Session && sessionId) {
            try {
              const session = await api.getSession(sessionId);
              needPx4Session = session.firmware !== 'px4';
            } catch {
              needPx4Session = true;
            }
          } else if (!sessionId) {
            needPx4Session = true;
          }
          if (needPx4Session) {
            await get().setFirmware('px4', true);
          }
        }

        let { sessionId } = get();
        if (!sessionId) {
          await get().initSession();
          sessionId = get().sessionId;
        }
        if (!sessionId) return;

        const files = Array.from(fileList);
        set({ loading: true, error: null });
        try {
          for (const file of files) {
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
          selectedLogIdx: 0,
          error: null,
        }),
    }),
    {
      name: 'pidbox-settings',
      partialize: (s) => ({
        settings: s.settings,
        visibleTraces: s.visibleTraces,
        sessionId: s.sessionId,
        files: s.files,
        selectedFileIdx: s.selectedFileIdx,
        selectedLogIdx: s.selectedLogIdx,
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.settings.theme) {
          document.body.className = state.settings.theme;
        }
      },
    },
  ),
);
