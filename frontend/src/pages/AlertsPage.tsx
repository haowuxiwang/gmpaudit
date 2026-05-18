import React, { useEffect, useState } from 'react';
import { Button, Card, Empty, Select, Space, Table, Tag, Typography, message } from 'antd';
import { CheckCircleOutlined, IssuesCloseOutlined } from '@ant-design/icons';

import { alertsApi } from '../services/api';
import type { RiskAlert } from '../types/api';

const { Title, Paragraph } = Typography;

const ALERT_LEVEL_COLORS: Record<string, string> = {
  critical: 'red',
  high: 'red',
  medium: 'orange',
  low: 'blue',
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
      message.error('Failed to load alerts');
    } finally {
      setLoading(false);
    }
  };

  const handleAcknowledge = async (id: number) => {
    try {
      await alertsApi.acknowledge(id);
      message.success('Alert acknowledged');
      void loadAlerts();
    } catch {
      message.error('Failed to update alert');
    }
  };

  const handleResolve = async (id: number) => {
    try {
      await alertsApi.resolve(id);
      message.success('Alert resolved');
      void loadAlerts();
    } catch {
      message.error('Failed to update alert');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
    {
      title: 'Level',
      dataIndex: 'alert_level',
      key: 'alert_level',
      width: 120,
      render: (level: string) => <Tag color={ALERT_LEVEL_COLORS[level] || 'default'}>{level}</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (status: string) => <Tag color={STATUS_COLORS[status] || 'default'}>{status}</Tag>,
    },
    {
      title: 'Finding',
      dataIndex: 'finding_id',
      key: 'finding_id',
      width: 120,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 220,
      render: (value: string) => (value ? new Date(value).toLocaleString() : '-'),
    },
    {
      title: 'Resolved',
      dataIndex: 'resolved_at',
      key: 'resolved_at',
      width: 220,
      render: (value: string) => (value ? new Date(value).toLocaleString() : '-'),
    },
    {
      title: 'Action',
      key: 'action',
      width: 180,
      render: (_: unknown, record: RiskAlert) => (
        <Space>
          {record.status === 'active' && (
            <Button type="link" icon={<CheckCircleOutlined />} onClick={() => void handleAcknowledge(record.id)}>
              Acknowledge
            </Button>
          )}
          {record.status !== 'resolved' && (
            <Button type="link" icon={<IssuesCloseOutlined />} onClick={() => void handleResolve(record.id)}>
              Resolve
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
          borderRadius: 24,
          background: 'linear-gradient(135deg, #7f1d1d 0%, #1f2937 100%)',
          color: '#fff',
        }}
        bodyStyle={{ padding: 28 }}
      >
        <Title level={2} style={{ color: '#fff', marginTop: 0 }}>
          Risk alerts
        </Title>
        <Paragraph style={{ color: 'rgba(255,255,255,0.82)', fontSize: 16, marginBottom: 0 }}>
          Review and close the highest-risk findings surfaced by the audit workflow.
        </Paragraph>
      </Card>

      <Card bordered={false} style={{ borderRadius: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Title level={4} style={{ margin: 0 }}>Alert queue</Title>
          <Select
            allowClear
            placeholder="Filter by status"
            value={statusFilter}
            onChange={(value) => setStatusFilter(value)}
            style={{ width: 180 }}
            options={[
              { value: 'active', label: 'active' },
              { value: 'acknowledged', label: 'acknowledged' },
              { value: 'resolved', label: 'resolved' },
            ]}
          />
        </div>

        <Table
          columns={columns}
          dataSource={alerts}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="No alerts found" /> }}
        />
      </Card>
    </div>
  );
};

export default AlertsPage;
