import React, { useEffect, useState } from 'react';
import { Button, Card, Empty, Select, Space, Table, Tag, Typography, message } from 'antd';
import { CheckCircleOutlined, IssuesCloseOutlined } from '@ant-design/icons';

import { alertsApi } from '../services/api';
import type { RiskAlert } from '../types/api';

const { Title, Paragraph } = Typography;

const ALERT_LEVEL_COLORS: Record<string, string> = {
  critical: 'red',
  warning: 'orange',
  info: 'blue',
};

const STATUS_COLORS: Record<string, string> = {
  active: 'red',
  acknowledged: 'processing',
  resolved: 'success',
};

const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);

  useEffect(() => {
    void loadAlerts();
  }, [statusFilter]);

  const loadAlerts = async () => {
    try {
      setLoading(true);
      const result = await alertsApi.list(statusFilter);
      setAlerts(result?.items || []);
    } catch {
      message.error('加载告警失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledge = async (id: number) => {
    try {
      await alertsApi.acknowledge(id);
      message.success('已确认告警');
      void loadAlerts();
    } catch {
      message.error('更新告警失败');
    }
  };

  const handleResolve = async (id: number) => {
    try {
      await alertsApi.resolve(id);
      message.success('已解决告警');
      void loadAlerts();
    } catch {
      message.error('更新告警失败');
    }
  };

  const ALERT_LEVEL_LABELS: Record<string, string> = {
    critical: '严重',
    warning: '警告',
    info: '信息',
  };

  const STATUS_LABELS: Record<string, string> = {
    active: '活跃',
    acknowledged: '已确认',
    resolved: '已解决',
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    {
      title: '级别',
      dataIndex: 'alert_level',
      key: 'alert_level',
      width: 120,
      render: (level: string) => <Tag color={ALERT_LEVEL_COLORS[level] || 'default'}>{ALERT_LEVEL_LABELS[level] || level}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (status: string) => <Tag color={STATUS_COLORS[status] || 'default'}>{STATUS_LABELS[status] || status}</Tag>,
    },
    {
      title: '发现',
      dataIndex: 'finding_id',
      key: 'finding_id',
      width: 120,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 220,
      render: (value: string) => (value ? new Date(value).toLocaleString() : '-'),
    },
    {
      title: '解决时间',
      dataIndex: 'resolved_at',
      key: 'resolved_at',
      width: 220,
      render: (value: string) => (value ? new Date(value).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: unknown, record: RiskAlert) => (
        <Space>
          {record.status === 'active' && (
            <Button type="link" icon={<CheckCircleOutlined />} onClick={() => void handleAcknowledge(record.id)}>
              确认
            </Button>
          )}
          {record.status !== 'resolved' && (
            <Button type="link" icon={<IssuesCloseOutlined />} onClick={() => void handleResolve(record.id)}>
              解决
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        bordered={false}
        style={{
          marginBottom: 24,
          borderRadius: 12,
          background: '#FFFFFF',
          borderLeft: '4px solid #D97757',
        }}
        styles={{ body: { padding: 28 } }}
      >
        <Title level={2} style={{ color: '#1A1A1A', marginTop: 0 }}>
          风险告警
        </Title>
        <Paragraph style={{ color: '#6B7280', fontSize: 16, marginBottom: 0 }}>
          审查并关闭审计流程中发现的高风险问题
        </Paragraph>
      </Card>

      <Card bordered={false} style={{ borderRadius: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Title level={4} style={{ margin: 0 }}>告警列表</Title>
          <Select
            allowClear
            placeholder="按状态筛选"
            value={statusFilter}
            onChange={(value) => setStatusFilter(value)}
            style={{ width: 180 }}
            options={[
              { value: 'active', label: '活跃' },
              { value: 'acknowledged', label: '已确认' },
              { value: 'resolved', label: '已解决' },
            ]}
          />
        </div>

        <Table
          columns={columns}
          dataSource={alerts}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="暂无告警" /> }}
        />
      </Card>
    </div>
  );
};

export default AlertsPage;
