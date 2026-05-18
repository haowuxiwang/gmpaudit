import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider, Layout, Spin } from 'antd';
import zhCN from 'antd/locale/zh_CN';
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
  <Layout style={{ minHeight: '100vh', background: '#FAFAF8' }}>
    <Sidebar />
    <Layout>
      <Header />
      <Content style={{ padding: '24px', background: '#FAFAF8' }}>
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
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#D97757',
          colorBgLayout: '#FAFAF8',
          colorBgContainer: '#FFFFFF',
          borderRadius: 8,
          colorText: '#1A1A1A',
          colorTextSecondary: '#6B7280',
          colorBorder: '#E8E5E0',
        },
      }}
    >
      <Router>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/*" element={<AppLayout />} />
          </Routes>
        </Suspense>
      </Router>
    </ConfigProvider>
  );
};

export default App;
