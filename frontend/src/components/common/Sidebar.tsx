import React from 'react';
import { Layout, Menu, Typography } from 'antd';
import {
  AlertOutlined,
  AppstoreOutlined,
  BranchesOutlined,
  FileTextOutlined,
  RobotOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';

const { Sider } = Layout;
const { Text } = Typography;

const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const items = [
    { key: '/', icon: <AppstoreOutlined />, label: '工作台' },
    { key: '/documents', icon: <FileTextOutlined />, label: '文档管理' },
    { key: '/audit', icon: <RobotOutlined />, label: '审计任务' },
    { key: '/reports', icon: <FileTextOutlined />, label: '审计报告' },
    { key: '/kg', icon: <BranchesOutlined />, label: '知识图谱' },
    { key: '/alerts', icon: <AlertOutlined />, label: '风险告警' },
    { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
  ];

  return (
    <Sider width={248} style={{ background: '#FFFFFF', padding: 16, borderRight: '1px solid #E8E5E0' }}>
      <div
        style={{
          minHeight: 92,
          padding: 16,
          marginBottom: 16,
          borderRadius: 12,
          background: '#FFFFFF',
          borderLeft: '4px solid #D97757',
        }}
      >
        <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 4, color: '#1A1A1A' }}>AuditBee</div>
        <Text style={{ color: '#6B7280' }}>
          多智能体 GMP 合规审计
        </Text>
      </div>
      <Menu
        mode="inline"
        selectedKeys={[location.pathname]}
        items={items}
        onClick={({ key }) => navigate(key)}
        style={{
          background: 'transparent',
          borderInlineEnd: 'none',
        }}
      />
    </Sider>
  );
};

export default Sidebar;
