import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Badge, Button, Card, Descriptions, Empty, Modal, Select, Space, Table, Tag, Typography, message } from 'antd';
import { AlertOutlined, CaretDownOutlined, CaretRightOutlined, CheckCircleOutlined, EyeOutlined, IssuesCloseOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { alertsApi } from '../services/api';
import type { RiskAlert } from '../types/api';
import { THEME } from '../constants/theme';

const { Title, Paragraph, Text } = Typography;

// Unified semantic color system
const SEMANTIC_COLORS = {
  danger: 'red',      // critical, high, active
  warning: 'orange',  // warning, medium
  info: 'blue',       // info, low, acknowledged
  success: 'green',   // resolved
} as const;

const ALERT_LEVEL_COLORS: Record<string, string> = {
  critical: SEMANTIC_COLORS.danger,
  warning: SEMANTIC_COLORS.warning,
  info: SEMANTIC_COLORS.info,
};

const STATUS_COLORS: Record<string, string> = {
  active: SEMANTIC_COLORS.danger,
  acknowledged: SEMANTIC_COLORS.info,
  resolved: SEMANTIC_COLORS.success,
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
  high: SEMANTIC_COLORS.danger,
  medium: SEMANTIC_COLORS.warning,
  low: SEMANTIC_COLORS.info,
};

const SEVERITY_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
};

const AlertsPage: React.FC = () => {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [allAlerts, setAllAlerts] = useState<RiskAlert[]>([]); // unfiltered for statistics
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [levelFilter, setLevelFilter] = useState<string | undefined>(undefined);
  const [bannerDismissed, setBannerDismissed] = useState(() => {
    try { return localStorage.getItem('alerts-info-banner-dismissed') === 'true'; } catch { return false; }
  });

  const loadAlerts = useCallback(async () => {
    try {
      setLoading(true);
      const [filtered, unfiltered] = await Promise.all([
        alertsApi.list(statusFilter),
        alertsApi.list(), // always fetch all for statistics
      ]);
      let items = filtered?.items || [];
      // Client-side level filter
      if (levelFilter) {
        items = items.filter((a) => a.alert_level === levelFilter);
      }
      setAlerts(items);
      setAllAlerts(unfiltered?.items || []);
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : '加载告警失败');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, levelFilter]);

  useEffect(() => {
    void loadAlerts();
  }, [loadAlerts]);

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
        } catch (e: unknown) {
          message.error(e instanceof Error ? e.message : '确认告警失败');
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
        } catch (e: unknown) {
          message.error(e instanceof Error ? e.message : '解决告警失败');
        }
      },
    });
  };

  const columns = [
    {
      title: '级别',
      dataIndex: 'alert_level',
      key: 'alert_level',
      width: 80,
      render: (level: string) => <Tag color={ALERT_LEVEL_COLORS[level] || 'default'}>{ALERT_LEVEL_LABELS[level] || level}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => <Tag color={STATUS_COLORS[status] || 'default'}>{ALERT_STATUS_LABELS[status] || status}</Tag>,
    },
    {
      title: '发现标题',
      key: 'finding_title',
      render: (_: unknown, record: RiskAlert) => (
        <Space size={8}>
          <Text strong>{record.finding_title || `发现 #${record.finding_id}`}</Text>
          <Tag color={SEVERITY_COLORS[record.finding_severity || ''] || 'default'} style={{ marginLeft: 4 }}>
            {SEVERITY_LABELS[record.finding_severity || ''] || record.finding_severity || '-'}
          </Tag>
        </Space>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      responsive: ['md'] as ('md')[],
      render: (value: string) => (value ? new Date(value).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: RiskAlert) => (
        <Space>
          {record.status === 'active' && (
            <Button type="link" size="small" icon={<CheckCircleOutlined />} onClick={(e) => { e.stopPropagation(); void handleAcknowledge(record.id); }}>
              确认
            </Button>
          )}
          {record.status !== 'resolved' && (
            <Button type="link" size="small" icon={<IssuesCloseOutlined />} onClick={(e) => { e.stopPropagation(); void handleResolve(record.id); }}>
              解决
            </Button>
          )}
        </Space>
      ),
    },
  ];

  const expandedRowRender = (record: RiskAlert) => {
    const borderColor = ALERT_LEVEL_COLORS[record.alert_level] || THEME.primary;
    return (
      <div
        style={{
          padding: '16px 20px',
          margin: '4px 0',
          borderRadius: 8,
          borderLeft: `3px solid ${borderColor}`,
          backgroundColor: THEME.bgWarm,
        }}
      >
        <Descriptions
          column={1}
          size="small"
          labelStyle={{ fontWeight: 600, color: THEME.textSecondary, width: 100, paddingRight: 12 }}
          contentStyle={{ color: THEME.text }}
        >
          <Descriptions.Item label="告警级别">
            <Tag color={ALERT_LEVEL_COLORS[record.alert_level]}>
              {ALERT_LEVEL_LABELS[record.alert_level] || record.alert_level}
            </Tag>
            <Tag color={SEVERITY_COLORS[record.finding_severity || '']} style={{ marginLeft: 8 }}>
              {SEVERITY_LABELS[record.finding_severity || ''] || record.finding_severity || '-'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="完整描述">
            <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
              {record.finding_description || '无描述'}
            </Paragraph>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {record.created_at ? new Date(record.created_at).toLocaleString('zh-CN') : '-'}
          </Descriptions.Item>
          {record.resolved_at && (
            <Descriptions.Item label="解决时间">
              {new Date(record.resolved_at).toLocaleString('zh-CN')}
              {record.resolved_by && <Text type="secondary" style={{ marginLeft: 8 }}>by {record.resolved_by}</Text>}
            </Descriptions.Item>
          )}
        </Descriptions>

        {record.task_id && (
          <div style={{ marginTop: 16, paddingTop: 12, borderTop: `1px solid ${THEME.border}` }}>
            <Space>
              <Button type="primary" ghost size="small" icon={<EyeOutlined />} onClick={() => navigate(`/audit?task_id=${record.task_id}`)}>
                查看关联任务
              </Button>
              <Text type="secondary" style={{ fontSize: 12 }}>跳转到审计任务详情页查看更多信息</Text>
            </Space>
          </div>
        )}
      </div>
    );
  };

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

      {!bannerDismissed && (
        <Alert
          message="告警由审计任务完成后自动生成：高风险发现 → 严重告警，中风险发现 → 警告告警"
          type="info"
          showIcon
          closable
          onClose={() => { try { localStorage.setItem('alerts-info-banner-dismissed', 'true'); } catch {} setBannerDismissed(true); }}
          style={{ marginBottom: 16, borderRadius: 8 }}
        />
      )}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {(['critical', 'warning', 'info'] as const).map((level) => {
          const count = allAlerts.filter((a) => a.alert_level === level).length;
          const isActive = levelFilter === level;
          return (
            <Tag
              key={level}
              color={isActive ? ALERT_LEVEL_COLORS[level] : undefined}
              style={{
                cursor: 'pointer',
                padding: '4px 12px',
                borderRadius: 16,
                border: isActive ? undefined : `1px solid ${THEME.border}`,
                backgroundColor: isActive ? undefined : THEME.bgContainer,
              }}
              onClick={() => setLevelFilter(isActive ? undefined : level)}
            >
              <Space size={4}>
                <span>{ALERT_LEVEL_LABELS[level]}</span>
                <Badge
                  count={count}
                  size="small"
                  style={{
                    backgroundColor: isActive ? '#fff' : ALERT_LEVEL_COLORS[level],
                    color: isActive ? ALERT_LEVEL_COLORS[level] : '#fff',
                    boxShadow: 'none',
                  }}
                />
              </Space>
            </Tag>
          );
        })}
      </div>

      <Card bordered={false} style={{ borderRadius: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', marginBottom: 16 }}>
          <Select
            allowClear
            placeholder="按状态筛选"
            value={statusFilter}
            onChange={(value) => setStatusFilter(value)}
            style={{ width: '100%', maxWidth: 180 }}
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
          scroll={{ x: true }}
          pagination={{ pageSize: 10 }}
          rowClassName={(record) =>
            record.alert_level === 'critical' ? 'alert-row alert-row-critical' : 'alert-row'
          }
          expandable={{
            expandedRowRender,
            expandRowByClick: true,
            expandedRowClassName: () => 'alert-expanded-row',
            expandIcon: ({ expanded, onExpand, record }) =>
              expanded ? (
                <CaretDownOutlined
                  onClick={(e) => onExpand(record, e)}
                  style={{ color: THEME.primary, fontSize: 14 }}
                />
              ) : (
                <CaretRightOutlined
                  onClick={(e) => onExpand(record, e)}
                  style={{ color: THEME.textSecondary, fontSize: 14 }}
                />
              ),
          }}
          locale={{
            emptyText: (
              <Empty
                image={<AlertOutlined style={{ fontSize: 48, color: THEME.textSecondary }} />}
                description={
                  <Space direction="vertical" size={4}>
                    <Text type="secondary">暂无告警</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>审计任务完成后自动生成风险告警</Text>
                  </Space>
                }
              />
            ),
          }}
          onRow={(record) => ({
            style: { cursor: 'pointer' },
          })}
        />
      </Card>

      {/* Inject custom styles for table rows */}
      <style>{`
        .alert-row:hover > td {
          background-color: ${THEME.bgSelected} !important;
        }
        .alert-row-critical > td:first-child {
          border-left: 3px solid ${SEMANTIC_COLORS.danger};
        }
        .alert-expanded-row > td {
          background-color: ${THEME.bgWarm};
        }
      `}</style>
    </div>
  );
};

export default AlertsPage;
