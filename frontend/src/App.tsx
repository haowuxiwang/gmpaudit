import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Layout, Spin } from 'antd';
import Header from './components/common/Header';
import Sidebar from './components/common/Sidebar';
import ErrorBoundary from './components/common/ErrorBoundary';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const DocumentsPage = lazy(() => import('./pages/DocumentsPage'));
const AuditTasksPage = lazy(() => import('./pages/AuditTasksPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const AlertsPage = lazy(() => import('./pages/AlertsPage'));
const KnowledgeGraphPage = lazy(() => import('./pages/KnowledgeGraphPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

const { Content } = Layout;

const Loading = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 200 }}>
    <Spin size="large" />
  </div>
);

const AppLayout: React.FC = () => (
  <Layout style={{ minHeight: '100vh', background: '#e5e7eb' }}>
    <Sidebar />
    <Layout>
      <Header />
      <Content style={{ padding: '24px', background: 'linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)' }}>
        <ErrorBoundary>
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/documents" element={<DocumentsPage />} />
              <Route path="/audit" element={<AuditTasksPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/kg" element={<KnowledgeGraphPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </Content>
    </Layout>
  </Layout>
);

const App: React.FC = () => {
  return (
    <Router>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/*" element={<AppLayout />} />
        </Routes>
      </Suspense>
    </Router>
  );
};

export default App;
