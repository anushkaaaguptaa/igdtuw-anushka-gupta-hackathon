import React, { useState, useEffect, lazy, Suspense } from 'react';
import './App.css';
import { Header } from './components/common/Header';
import { LoadingSpinner } from './components/common/StateViews';
import { healthService } from './services/healthService';
import { API_BASE_URL, ApiError } from './services/apiClient';
import type { HealthResponse, RiskSignalRead } from './types/api';
import type { ActiveTab } from './types/navigation';
import { AlertCircle } from 'lucide-react';

// Route-level code splitting with dynamic chunking
const OverviewDashboard = lazy(() =>
  import('./components/dashboard/OverviewDashboard').then((m) => ({ default: m.OverviewDashboard }))
);
const IntelligenceFeed = lazy(() =>
  import('./components/intelligence/IntelligenceFeed').then((m) => ({ default: m.IntelligenceFeed }))
);
const PortfolioManager = lazy(() =>
  import('./components/portfolio/PortfolioManager').then((m) => ({ default: m.PortfolioManager }))
);
const StressTestingWorkspace = lazy(() =>
  import('./components/stress/StressTestingWorkspace').then((m) => ({ default: m.StressTestingWorkspace }))
);

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('dashboard');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [healthError, setHealthError] = useState<string | null>(null);

  // Active risk signal triggering an automated scenario simulation
  const [activeTriggerSignal, setActiveTriggerSignal] = useState<RiskSignalRead | null>(null);

  const checkHealth = async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const data = await healthService.getHealth();
      setHealth(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setHealthError(err.detail);
      } else if (err instanceof Error) {
        setHealthError(err.message);
      } else {
        setHealthError('Unknown network connection error');
      }
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    healthService
      .getHealth()
      .then((data) => {
        if (isMounted) {
          setHealth(data);
          setHealthLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          if (err instanceof ApiError) {
            setHealthError(err.detail);
          } else if (err instanceof Error) {
            setHealthError(err.message);
          } else {
            setHealthError('Unknown network connection error');
          }
          setHealth(null);
          setHealthLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Handler for Signal-to-Scenario Automated Trigger
  const handleTriggerStressForSignal = (signal: RiskSignalRead) => {
    setActiveTriggerSignal(signal);
    setActiveTab('stress_testing');
  };

  return (
    <div className="app-container">
      {/* Top Application Header */}
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        health={health}
        healthLoading={healthLoading}
        onRefreshHealth={checkHealth}
      />

      {/* Main Content Area */}
      <main className="app-main">
        {/* Backend Offline Alert */}
        {healthError && (
          <div
            style={{
              padding: '1rem 1.25rem',
              backgroundColor: 'var(--accent-rose-bg)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              borderRadius: 'var(--radius-md)',
              marginBottom: '1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <AlertCircle size={20} color="var(--accent-rose)" />
              <div>
                <div style={{ fontWeight: 600, color: '#fda4af' }}>
                  Cannot connect to FastAPI backend at {API_BASE_URL}
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  {healthError}. Ensure the backend service is running with{' '}
                  <code className="mono" style={{ color: '#ffffff' }}>
                    uvicorn app.main:app --port 8000
                  </code>
                  .
                </div>
              </div>
            </div>
            <button onClick={checkHealth} className="btn btn-outline" style={{ fontSize: '0.75rem' }} type="button">
              Retry Connection
            </button>
          </div>
        )}

        <Suspense fallback={<LoadingSpinner message="Loading workspace view..." />}>
          {/* Tab 1: Screen A — Overview Dashboard */}
          {activeTab === 'dashboard' && (
            <OverviewDashboard
              onNavigateTab={setActiveTab}
              onTriggerStressForSignal={handleTriggerStressForSignal}
            />
          )}

          {/* Tab 2: Screen B — Financial Intelligence Feed & Ingestion Telemetry */}
          {activeTab === 'intelligence' && (
            <IntelligenceFeed onTriggerStressForSignal={handleTriggerStressForSignal} />
          )}

          {/* Tab 3: Screen C — Portfolio Management */}
          {activeTab === 'portfolio' && (
            <PortfolioManager onNavigateTab={setActiveTab} />
          )}

          {/* Tab 4: Screen D — Stress-Testing Workspace & Scenario Simulator */}
          {activeTab === 'stress_testing' && (
            <StressTestingWorkspace
              triggerSignal={activeTriggerSignal}
              onClearTriggerSignal={() => setActiveTriggerSignal(null)}
            />
          )}
        </Suspense>
      </main>
    </div>
  );
};

export default App;
