import React from 'react';
import { Layout, Typography, Button, Dropdown, message } from 'antd';
import { UserOutlined, SettingOutlined, LogoutOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Header: AntHeader } = Layout;
const { Title } = Typography;

const Header: React.FC = () => {
  const navigate = useNavigate();

  let userName = '管理员';
  try {
    const userStr = localStorage.getItem('user');
    if (userStr) {
      const user = JSON.parse(userStr);
      userName = user.name || user.username || '管理员';
    }
  } catch {
    // ignore parse errors
  }

  const handleMenuClick = ({ key }: { key: string }) => {
    if (key === 'settings') {
      navigate('/settings');
    } else if (key === 'logout') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      message.success('已退出登录');
      navigate('/login', { replace: true });
    }
  };

  const menuItems = [
    { key: 'settings', icon: <SettingOutlined />, label: '设置' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出' },
  ];

  return (
    <AntHeader style={{ background: '#fff', padding: '0 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f0f0f0' }}>
      <Title level={4} style={{ margin: 0 }}>GMP合规性审计系统</Title>
      <Dropdown menu={{ items: menuItems, onClick: handleMenuClick }} placement="bottomRight">
        <Button icon={<UserOutlined />}>{userName}</Button>
      </Dropdown>
    </AntHeader>
  );
};

export default Header;
