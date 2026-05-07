import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from 'antd';
import Header from './components/common/Header';
import Sidebar from './components/common/Sidebar';
import DashboardPage from './pages/DashboardPage';
import DocumentsPage from './pages/DocumentsPage';
import AuditTasksPage from './pages/AuditTasksPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import AlertsPage from './pages/AlertsPage';
import LoginPage from './pages/LoginPage';
import AuthCallbackPage from './pages/AuthCallbackPage';

const { Content } = Layout;

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('access_token');
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/callback" element={<AuthCallbackPage />} />
        <Route
          path="*"
          element={
            <ProtectedRoute>
              <Layout style={{ minHeight: '100vh' }}>
                <Sidebar />
                <Layout>
                  <Header />
                  <Content style={{ padding: '24px', background: '#fff' }}>
                    <Routes>
                      <Route path="/" element={<DashboardPage />} />
                      <Route path="/documents" element={<DocumentsPage />} />
                      <Route path="/audit" element={<AuditTasksPage />} />
                      <Route path="/reports" element={<ReportsPage />} />
                      <Route path="/alerts" element={<AlertsPage />} />
                      <Route path="/settings" element={<SettingsPage />} />
                    </Routes>
                  </Content>
                </Layout>
              </Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  );
};

export default App;
