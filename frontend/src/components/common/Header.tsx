import React from 'react';
import { Layout, Space, Typography } from 'antd';
import { useLocation } from 'react-router-dom';
import { THEME } from '../../constants/theme';

const { Header: AntHeader } = Layout;
const { Title } = Typography;

const PAGE_TITLES: Record<string, string> = {
  '/': '审计工作台',
  '/documents': '文档管理',
  '/audit': '审计任务',
  '/reports': '审计报告',
  '/kg': '知识图谱',
  '/alerts': '风险告警',
  '/settings': '系统设置',
};

const Header: React.FC = () => {
  const location = useLocation();
  const title = PAGE_TITLES[location.pathname] || '审计工作台';

  return (
    <AntHeader
      style={{
        background: THEME.bgContainer,
        padding: '0 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: `1px solid ${THEME.border}`,
      }}
    >
      <Title level={4} style={{ margin: 0 }}>
        {title}
      </Title>
      <div />
    </AntHeader>
  );
};

export default Header;
