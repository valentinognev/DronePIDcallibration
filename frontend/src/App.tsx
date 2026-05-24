import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { KeyboardShortcuts } from './components/KeyboardShortcuts';
import { Layout } from './components/Layout';
import { SessionBootstrap } from './components/SessionBootstrap';
import { ThemeSync } from './components/ThemeSync';
import { FilterSimPage } from './pages/FilterSimPage';
import { FreqThrottlePage } from './pages/FreqThrottlePage';
import { FreqTimePage } from './pages/FreqTimePage';
import { LogViewerPage } from './pages/LogViewerPage';
import { SetupInfoPage } from './pages/SetupInfoPage';
import { SpectralAnalyzerPage } from './pages/SpectralAnalyzerPage';
import { StatsPage } from './pages/StatsPage';
import { StepResponsePage } from './pages/StepResponsePage';

export default function App() {
  return (
    <BrowserRouter>
      <ThemeSync />
      <SessionBootstrap />
      <KeyboardShortcuts />
      <Layout>
        <Routes>
          <Route path="/" element={<LogViewerPage />} />
          <Route path="/spectral" element={<SpectralAnalyzerPage />} />
          <Route path="/step-response" element={<StepResponsePage />} />
          <Route path="/freq-throttle" element={<FreqThrottlePage />} />
          <Route path="/freq-time" element={<FreqTimePage />} />
          <Route path="/filter-sim" element={<FilterSimPage />} />
          <Route path="/setup-info" element={<SetupInfoPage />} />
          <Route path="/stats" element={<StatsPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
