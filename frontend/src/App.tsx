import { BrowserRouter } from 'react-router-dom';
import { KeyboardShortcuts } from './components/KeyboardShortcuts';
import { Layout } from './components/Layout';
import { PersistentRoutes } from './components/PersistentRoutes';
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

const ROUTES = [
  { path: '/', Component: LogViewerPage },
  { path: '/spectral', Component: SpectralAnalyzerPage },
  { path: '/step-response', Component: StepResponsePage },
  { path: '/freq-throttle', Component: FreqThrottlePage },
  { path: '/freq-time', Component: FreqTimePage },
  { path: '/filter-sim', Component: FilterSimPage },
  { path: '/setup-info', Component: SetupInfoPage },
  { path: '/stats', Component: StatsPage },
] as const;

export default function App() {
  return (
    <BrowserRouter>
      <ThemeSync />
      <SessionBootstrap />
      <KeyboardShortcuts />
      <Layout>
        <PersistentRoutes routes={[...ROUTES]} />
      </Layout>
    </BrowserRouter>
  );
}
