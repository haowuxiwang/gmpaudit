import React, { useState } from 'react';
import { Card, Button, Typography, Space, message } from 'antd';
import { LoginOutlined } from '@ant-design/icons';
import { authApi } from '../services/api';

const { Title, Text } = Typography;

const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);

  const handleFeishuLogin = async () => {
    setLoading(true);
    try {
      const data: any = await authApi.getFeishuLoginUrl();
      window.location.href = data.url;
    } catch (error) {
      message.error('获取飞书登录链接失败，请稍后重试');
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: '#f0f2f5',
      }}
    >
      <Card style={{ width: 400, textAlign: 'center' }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={3} style={{ marginBottom: 8 }}>
              GMP合规性审计系统
            </Title>
            <Text type="secondary">请使用飞书账号登录</Text>
          </div>
          <Button
            type="primary"
            size="large"
            icon={<LoginOutlined />}
            loading={loading}
            onClick={handleFeishuLogin}
            block
          >
            飞书登录
          </Button>
        </Space>
      </Card>
    </div>
  );
};

export default LoginPage;
