import React, { useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Spin, message } from 'antd';
import { authApi } from '../services/api';

const AuthCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!code || !state) {
      message.error('登录参数缺失');
      navigate('/login', { replace: true });
      return;
    }

    authApi
      .handleCallback(code, state)
      .then((data: any) => {
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        message.success('登录成功');
        navigate('/', { replace: true });
      })
      .catch(() => {
        message.error('飞书登录失败，请重试');
        navigate('/login', { replace: true });
      });
  }, [searchParams, navigate]);

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      <Spin size="large" tip="正在登录中..." />
    </div>
  );
};

export default AuthCallbackPage;
