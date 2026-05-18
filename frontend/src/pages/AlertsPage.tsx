import React, { useEffect, useState } from 'react';
import { Alert, Button, Card, Empty, Modal, Select, Space, Table, Tag, Typography, message } from 'antd';
import { CheckCircleOutlined, EyeOutlined, IssuesCloseOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { alertsApi } from '../services/api';
import type { RiskAlert } from '../types/api';
import { THEME } from '../constants/theme';

const { Title, Paragraph, Text } = Typography;

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

const ALERT_LEVEL_LABELS: Record<string, string> = {
  critical: '严重',
  warning: '警告',
  info: '信息',
};

const ALERT_STATUS_LABELS: Record<string, string> = {
  active: '活跃',
  acknowledged: '已确认',
  resolved: '已解决',
};

const SEVERITY_COLORS: Record<string, string> = {
  high: 'red',
  medium: 'orange',
  low: 'green',
};

const SEVERITY_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
};

const AlertsPage: React.FC = () => {
  const navigate = useNavigate();
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

  const handleAcknowledge = (id: number) => {
    Modal.confirm({
      title: '确认告警',
      content: '确认后表示已知悉该风险，是否继续？',
      okText: '确认',
      onOk: async () => {
        try {
          await alertsApi.acknowledge(id);
          message.success('已确认告警');
          void loadAlerts();
        } catch {
          message.error('确认告警失败');
        }
      },
    });
  };

  const handleResolve = (id: number) => {
    Modal.confirm({
      title: '解决告警',
      content: '解决后该告警将标记为已处理，是否继续？',
      okText: '解决',
      onOk: async () => {
        try {
          await alertsApi.resolve(id);
          message.success('已解决告警');
          void loadAlerts();
        } catch {
          message.error('解决告警失败');
        }
      },
    });
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '级别',
      dataIndex: 'alert_level',
      key: 'alert_level',
      width: 90,
      render: (level: string) => <Tag color={ALERT_LEVEL_COLORS[level] || 'default'}>{ALERT_LEVEL_LABELS[level] || level}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => <Tag color={STATUS_COLORS[status] || 'default'}>{ALERT_STATUS_LABELS[status] || status}</Tag>,
    },
    {
      title: '发现',
      key: 'finding',
      render: (_: unknown, record: RiskAlert) => (
        <Space direction="vertical" size={0}>
          <Text strong>{record.finding_title || `发现 #${record.finding_id}`}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {(record.finding_description || '').slice(0, 80)}{(record.finding_description || '').length > 80 ? '...' : ''}
          </Text>
        </Space>
      ),
    },
    {
      title: '严重程度',
      key: 'finding_severity',
      width: 100,
      render: (_: unknown, record: RiskAlert) => (
        <Tag color={SEVERITY_COLORS[record.finding_severity || ''] || 'default'}>
          {SEVERITY_LABELS[record.finding_severity || ''] || record.finding_severity || '-'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (value: string) => (value ? new Date(value).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: RiskAlert) => (
        <Space>
          {record.task_id && (
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/audit?task_id=${record.task_id}`)}>
              任务
            </Button>
          )}
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
          borderLeft: `4px solid ${THEME.primary}`,
        }}
        styles={{ body: { padding: 28 } }}
      >
        <Title level={2} style={{ color: THEME.text, marginTop: 0 }}>
          风险告警
        </Title>
        <Paragraph style={{ color: THEME.textSecondary, fontSize: 16, marginBottom: 0 }}>
          审查并关闭审计流程中发现的高风险问题
        </Paragraph>
      </Card>

      <Alert
        message="告警由审计任务完成后自动生成：高风险发现 → 严重告警，中风险发现 → 警告告警"
        type="info"
        showIcon
        style={{ marginBottom: 16, borderRadius: 8 }}
      />

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
