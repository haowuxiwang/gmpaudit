import React from 'react';
import { Spin } from 'antd';

interface LoadingProps {
  tip?: string;
}

const Loading: React.FC<LoadingProps> = ({ tip = '加载中...' }) => {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 200 }}>
      <Spin size="large" tip={tip}>
        <div style={{ padding: 50 }} />
      </Spin>
    </div>
  );
};

export default Loading;
