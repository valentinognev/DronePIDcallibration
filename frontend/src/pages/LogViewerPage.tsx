import { useEffect } from 'react';
import { EpochRangeSlider } from '../components/EpochRangeSlider';
import { FileDropzone } from '../components/FileDropzone';
import { TimeSeriesPlot } from '../components/TimeSeriesPlot';
import { TraceTogglePanel } from '../components/TraceTogglePanel';
import { api } from '../lib/api';
import { useSessionStore } from '../store/sessionStore';

export function LogViewerPage() {
  const {
    files, traceData, loading, error, settings, visibleTraces,
    uploadFiles, refreshTraces, setSettings, toggleTrace,
    selectedFileIdx, setSelectedFile, setEpoch, reset, initSession,
  } = useSessionStore();

  useEffect(() => {
    initSession();
  }, [initSession]);

  useEffect(() => {
    if (files.length > 0) refreshTraces();
  }, [settings.plotR, settings.plotP, settings.plotY, settings.lineSmooth, visibleTraces]);

  const available = traceData?.available_traces || [
    'gyro', 'setpoint', 'pterm', 'iterm', 'dterm', 'dterm_pf', 'fterm',
    'pidsum', 'piderr', 'throttle', 'motor_0', 'motor_1', 'motor_2', 'motor_3',
  ];

  const motorPanelTraces =
    traceData?.motor_panel?.filter((t) => visibleTraces.includes(t.key)) ?? [];
  const throttleTraces = motorPanelTraces.filter((t) => t.key === 'throttle');
  const motorRpmTraces = motorPanelTraces.filter((t) => t.key.startsWith('motor_'));
  const motorsUseRpm =
    traceData?.motor_panel_units?.motors === 'rpm' ||
    motorRpmTraces.some((t) => t.yaxis === 'y2');

  return (
    <div className="flex gap-4 h-[calc(100vh-80px)]">
      <TraceTogglePanel
        traces={available}
        visible={visibleTraces}
        onToggle={toggleTrace}
        yScale={settings.yScale}
        onYScaleChange={(v) => setSettings({ yScale: v })}
      />

      <div className="flex-1 flex flex-col min-h-0 gap-2">
        {files.length === 0 ? (
          <FileDropzone onFiles={uploadFiles} />
        ) : (
          <>
            {traceData?.full_time_range && traceData.epoch && (
              <div className="shrink-0">
                <EpochRangeSlider
                  min={traceData.full_time_range[0]}
                  max={traceData.full_time_range[1]}
                  start={traceData.epoch[0]}
                  end={traceData.epoch[1]}
                  onCommit={setEpoch}
                  disabled={loading}
                />
              </div>
            )}
            <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-2">
            {traceData?.panels?.roll && settings.plotR && (
              <TimeSeriesPlot
                title="Roll (deg/s)"
                traces={traceData.panels.roll.filter((t) => visibleTraces.includes(t.key))}
                yLabel="Roll (deg/s)"
                yRange={[-settings.yScale, settings.yScale]}
                lineWidth={settings.lineWidth}
              />
            )}
            {traceData?.panels?.pitch && settings.plotP && (
              <TimeSeriesPlot
                title="Pitch (deg/s)"
                traces={traceData.panels.pitch.filter((t) => visibleTraces.includes(t.key))}
                yLabel="Pitch (deg/s)"
                yRange={[-settings.yScale, settings.yScale]}
                lineWidth={settings.lineWidth}
              />
            )}
            {traceData?.panels?.yaw && settings.plotY && (
              <TimeSeriesPlot
                title="Yaw (deg/s)"
                traces={traceData.panels.yaw.filter((t) => visibleTraces.includes(t.key))}
                yLabel="Yaw (deg/s)"
                yRange={[-settings.yScale, settings.yScale]}
                lineWidth={settings.lineWidth}
              />
            )}
            {motorPanelTraces.length > 0 && motorsUseRpm ? (
              <>
                {throttleTraces.length > 0 && (
                  <TimeSeriesPlot
                    title="Throttle (%)"
                    traces={throttleTraces}
                    yLabel="Throttle (%)"
                    yRange={[0, 100]}
                    lineWidth={settings.lineWidth}
                  />
                )}
                {motorRpmTraces.length > 0 && (
                  <TimeSeriesPlot
                    title="Motor (RPM)"
                    traces={motorRpmTraces}
                    yLabel="RPM"
                    lineWidth={settings.lineWidth}
                  />
                )}
              </>
            ) : motorPanelTraces.length > 0 ? (
              <TimeSeriesPlot
                title="Throttle (%) | Motor (%)"
                traces={motorPanelTraces}
                yLabel="Throttle | Motor (%)"
                yRange={[0, 100]}
                lineWidth={settings.lineWidth}
              />
            ) : null}
            </div>
          </>
        )}
        {loading && <p className="text-sm text-blue-400 shrink-0">Loading...</p>}
        {error && <p className="text-sm text-red-400 shrink-0">{error}</p>}
      </div>

      <div className="panel w-56 shrink-0 space-y-3">
        <h3 className="text-sm font-semibold">Control Panel</h3>
        <select
          className="select-input"
          value={settings.firmware}
          onChange={(e) => setSettings({ firmware: e.target.value })}
        >
          <option value="betaflight">Betaflight</option>
          <option value="emuflight">Emuflight</option>
          <option value="inav">INAV</option>
          <option value="fettec">FETTEC</option>
          <option value="quicksilver">QuickSilver</option>
          <option value="rotorflight">Rotorflight</option>
          <option value="kiss">KISS Ultra</option>
          <option value="ardupilot">ArduPilot</option>
        </select>

        <FileDropzone onFiles={uploadFiles} label="Open File" />

        <button className="btn-reset w-full" onClick={reset}>Reset</button>

        {files.length > 0 && (
          <select
            className="select-input"
            value={selectedFileIdx}
            onChange={(e) => setSelectedFile(Number(e.target.value))}
          >
            {files.map((f, i) => (
              <option key={f.file_id} value={i}>{f.original_name}</option>
            ))}
          </select>
        )}

        <div className="flex gap-2">
          {(['plotR', 'plotP', 'plotY'] as const).map((k, i) => (
            <label key={k} className="text-sm">
              <input
                type="checkbox"
                checked={settings[k]}
                onChange={(e) => setSettings({ [k]: e.target.checked })}
              />{' '}
              {['R', 'P', 'Y'][i]}
            </label>
          ))}
        </div>

        <select
          className="select-input"
          value={settings.lineSmooth}
          onChange={(e) => setSettings({ lineSmooth: Number(e.target.value) })}
        >
          <option value={1}>line smooth off</option>
          <option value={2}>line smooth low</option>
          <option value={3}>line smooth med</option>
          <option value={4}>line smooth high</option>
        </select>

        <select
          className="select-input"
          value={settings.lineWidth}
          onChange={(e) => setSettings({ lineWidth: Number(e.target.value) })}
        >
          {[1, 2, 3, 4, 5].map((w) => (
            <option key={w} value={w}>line width {w}</option>
          ))}
        </select>

        <select
          className="select-input"
          value={settings.theme}
          onChange={(e) => setSettings({ theme: e.target.value as 'dark' | 'light' })}
        >
          <option value="dark">Dark Theme</option>
          <option value="light">Light Theme</option>
        </select>

        <button
          className="btn-run w-full text-sm"
          onClick={() => api.saveSettings(settings as unknown as Record<string, unknown>)}
        >
          Save Settings
        </button>

        {traceData?.metadata && (
          <div className="text-xs text-[var(--text-secondary)] space-y-1 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
            <p>{String(traceData.metadata.fw_type)}</p>
            <p>Rate: {traceData.lograte_khz} kHz</p>
            <p>Epoch: {traceData.epoch?.join(' – ')} s</p>
          </div>
        )}
      </div>
    </div>
  );
}
