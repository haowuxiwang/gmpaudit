import React, { useState, useEffect } from 'react';
import { Typography, Table, Button, Tag, Select, Space, message } from 'antd';
import { CheckCircleOutlined, IssuesCloseOutlined } from '@ant-design/icons';
import { alertsApi } from '../services/api';
import type { RiskAlert } from '../types/api';

const { Title } = Typography;

const alertLevelColors: Record<string, string> = {
  critical: 'red',
  high: 'red',
  medium: 'orange',
  low: 'blue',
};

const alertLevelLabels: Record<string, string> = {
  critical: '严重',
  high: '高',
  medium: '中',
  low: '低',
};

const statusColors: Record<string, string> = {
  active: 'red',
  acknowledged: 'processing',
  resolved: 'success',
};

const statusLabels: Record<string, string> = {
  active: '活跃',
  acknowledged: '已确认',
  resolved: '已解决',
};

const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);

  useEffect(() => { void loadAlerts(); }, [statusFilter]);

  const loadAlerts = async () => {
    try {
      setLoading(true);
      const result = await alertsApi.list(statusFilter);
      setAlerts(result?.items || []);
    } catch {
      message.error('加载警报列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledge = async (id: number) => {
    try {
      await alertsApi.acknowledge(id);
      message.success('已确认警报');
      void loadAlerts();
    } catch {
      message.error('操作失败');
    }
  };

  const handleResolve = async (id: number) => {
    try {
      await alertsApi.resolve(id);
      message.success('已解决警报');
      void loadAlerts();
    } catch {
      message.error('操作失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '警报级别',
      dataIndex: 'alert_level',
      key: 'alert_level',
      width: 100,
      render: (level: string) => (
        <Tag color={alertLevelColors[level] || 'default'}>{alertLevelLabels[level] || level}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={statusColors[status] || 'default'}>{statusLabels[status] || status}</Tag>
      ),
    },
    { title: '关联发现', dataIndex: 'finding_id', key: 'finding_id', width: 100 },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => (time ? new Date(time).toLocaleString() : '-'),
    },
    {
      title: '解决时间',
      dataIndex: 'resolved_at',
      key: 'resolved_at',
      width: 180,
      render: (time: string) => (time ? new Date(time).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: unknown, record: RiskAlert) => (
        <Space>
          {record.status === 'active' && (
            <Button
              type="link"
              icon={<CheckCircleOutlined />}
              onClick={() => void handleAcknowledge(record.id)}
            >
              确认
            </Button>
          )}
          {record.status !== 'resolved' && (
            <Button
              type="link"
              icon={<IssuesCloseOutlined />}
              onClick={() => void handleResolve(record.id)}
            >
              解决
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>风险警报</Title>
        <Select
          placeholder="按状态筛选"
          allowClear
          style={{ width: 150 }}
          value={statusFilter}
          onChange={(value) => setStatusFilter(value)}
          options={[
            { value: 'active', label: '活跃' },
            { value: 'acknowledged', label: '已确认' },
            { value: 'resolved', label: '已解决' },
          ]}
        />
      </div>
      <Table columns={columns} dataSource={alerts} loading={loading} rowKey="id" pagination={{ pageSize: 10 }} />
    </div>
  );
};

export default AlertsPage;
