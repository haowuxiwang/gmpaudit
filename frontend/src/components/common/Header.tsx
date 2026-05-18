import React from 'react';
import { Button, Layout, Space, Tag, Typography } from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Header: AntHeader } = Layout;
const { Title } = Typography;

const Header: React.FC = () => {
  const navigate = useNavigate();

  return (
    <AntHeader
      style={{
        background: '#fff',
        padding: '0 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '1px solid #e5e7eb',
      }}
    >
      <Space direction="vertical" size={0}>
        <Title level={4} style={{ margin: 0 }}>
          审计工作台
        </Title>
      </Space>

      <Space size="middle">
        <Tag color="blue" style={{ borderRadius: 999 }}>
          智能体循环
        </Tag>
        <Button icon={<SettingOutlined />} onClick={() => navigate('/settings')}>
          设置
        </Button>
      </Space>
    </AntHeader>
  );
};

export default Header;
