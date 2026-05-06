import React from 'react';
import { Layout, Typography, Button, Dropdown } from 'antd';
import { UserOutlined, SettingOutlined, LogoutOutlined } from '@ant-design/icons';

const { Header: AntHeader } = Layout;
const { Title } = Typography;

const Header: React.FC = () => {
  const menuItems = [
    { key: 'settings', icon: <SettingOutlined />, label: '设置' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出' },
  ];

  return (
    <AntHeader style={{ background: '#fff', padding: '0 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f0f0f0' }}>
      <Title level={4} style={{ margin: 0 }}>GMP合规性审计系统</Title>
      <Dropdown menu={{ items: menuItems }} placement="bottomRight">
        <Button icon={<UserOutlined />}>管理员</Button>
      </Dropdown>
    </AntHeader>
  );
};

export default Header;
