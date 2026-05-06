import React from 'react';
import { Layout, Menu } from 'antd';
import { DashboardOutlined, FileTextOutlined, AuditOutlined, BarChartOutlined, AlertOutlined, SettingOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider } = Layout;

const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: '/documents', icon: <FileTextOutlined />, label: '文档管理' },
    { key: '/audit', icon: <AuditOutlined />, label: '审计任务' },
    { key: '/reports', icon: <BarChartOutlined />, label: '审计报告' },
    { key: '/alerts', icon: <AlertOutlined />, label: '风险警报' },
    { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
  ];

  return (
    <Sider width={200} style={{ background: '#fff' }}>
      <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', borderBottom: '1px solid #f0f0f0' }}>
        <AuditOutlined style={{ fontSize: 24, color: '#1890ff' }} />
        <span style={{ marginLeft: 8, fontWeight: 'bold' }}>GMP审计</span>
      </div>
      <Menu mode="inline" selectedKeys={[location.pathname]} items={menuItems} onClick={({ key }) => navigate(key)} style={{ height: '100%', borderRight: 0 }} />
    </Sider>
  );
};

export default Sidebar;
