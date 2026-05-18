import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  BranchesOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  RightCircleOutlined,
  RobotOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { auditApi, documentApi } from '../services/api';
import type { AuditTask, DashboardData } from '../types/api';

const { Title, Paragraph, Text } = Typography;

const STAGE_LABELS: Record<string, string> = {
  pending: 'Waiting',
  queued: 'Queued',
  running: 'Running',
  parsing: 'Parsing',
  risk: 'Assessing risk',
  completed: 'Completed',
  failed: 'Failed',
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
};

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalDocuments: 0,
    totalTasks: 0,
    completedTasks: 0,
    highRiskFindings: 0,
  });
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [recentTasks, setRecentTasks] = useState<AuditTask[]>([]);

  useEffect(() => {
    void loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      setLoading(true);
      const [docResult, dashResult, taskResult] = await Promise.allSettled([
        documentApi.list(1, 1),
        auditApi.getDashboard(),
        auditApi.listTasks(),
      ]);

      const docData = docResult.status === 'fulfilled' ? docResult.value : null;
      const dashData = dashResult.status === 'fulfilled' ? dashResult.value : null;
      const tasks = taskResult.status === 'fulfilled' ? taskResult.value.items || [] : [];

      setStats({
        totalDocuments: docData?.total || 0,
        totalTasks: dashData?.total_tasks || 0,
        completedTasks: dashData?.task_counts?.completed || 0,
        highRiskFindings: dashData?.severity_counts?.high || 0,
      });
      setDashboard(dashData);
      setRecentTasks(tasks.slice(0, 5));
    } catch {
      message.error('Failed to load control room data');
    } finally {
      setLoading(false);
    }
  };

  const activeTask = useMemo(
    () => recentTasks.find((task) => task.status === 'running') || recentTasks[0] || null,
    [recentTasks],
  );

  const heroTone = activeTask?.status === 'running' ? '#f59e0b' : '#0f766e';

  const columns = [
    {
      title: 'Task',
      dataIndex: 'task_name',
      key: 'task_name',
      render: (value: string, record: AuditTask) => (
        <Space direction="vertical" size={0}>
          <Text strong>{value}</Text>
          <Text type="secondary">{record.task_type}</Text>
        </Space>
      ),
    },
    {
      title: 'Stage',
      dataIndex: 'stage',
      key: 'stage',
      width: 150,
      render: (stage?: string, record?: AuditTask) => (
        <Tag color={STATUS_COLORS[record?.status || 'pending'] || 'default'}>
          {STAGE_LABELS[stage || 'pending'] || stage || 'Waiting'}
        </Tag>
      ),
    },
    {
      title: 'Progress',
      dataIndex: 'progress',
      key: 'progress',
      width: 180,
      render: (value: number) => <Progress percent={value || 0} size="small" status="active" />,
    },
    {
      title: 'Action',
      key: 'action',
      width: 130,
      render: (_: unknown, record: AuditTask) => (
        <Button type="link" onClick={() => navigate(`/audit?task_id=${record.id}`)}>
          Open workspace
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Card
        loading={loading}
        bordered={false}
        style={{
          marginBottom: 24,
          borderRadius: 24,
          background: `linear-gradient(135deg, ${heroTone} 0%, #111827 100%)`,
          color: '#fff',
          overflow: 'hidden',
        }}
        bodyStyle={{ padding: 28 }}
      >
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} lg={16}>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Tag color="rgba(255,255,255,0.18)" style={{ alignSelf: 'flex-start', borderRadius: 999 }}>
                AI agent control room
              </Tag>
              <Title level={2} style={{ color: '#fff', margin: 0 }}>
                AuditBee runs audits as a guided agent session, not a static report factory.
              </Title>
              <Paragraph style={{ color: 'rgba(255,255,255,0.82)', fontSize: 16, marginBottom: 0 }}>
                Launch an audit, watch the agent move through regulation retrieval and risk analysis,
                then inspect the evidence chain behind the final report.
              </Paragraph>
              <Space wrap>
                <Button type="primary" size="large" icon={<RobotOutlined />} onClick={() => navigate('/audit')}>
                  Open agent workspace
                </Button>
                <Button size="large" onClick={() => navigate('/documents')}>
                  Upload evidence
                </Button>
                <Button size="large" onClick={() => navigate('/kg')} icon={<BranchesOutlined />}>
                  Explore knowledge graph
                </Button>
              </Space>
            </Space>
          </Col>
          <Col xs={24} lg={8}>
            <Card
              bordered={false}
              style={{ borderRadius: 20, background: 'rgba(255,255,255,0.1)', color: '#fff' }}
              bodyStyle={{ padding: 20 }}
            >
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                <Text style={{ color: 'rgba(255,255,255,0.75)' }}>Live focus</Text>
                {activeTask ? (
                  <>
                    <Title level={4} style={{ color: '#fff', margin: 0 }}>
                      {activeTask.task_name}
                    </Title>
                    <Text style={{ color: 'rgba(255,255,255,0.82)' }}>
                      {STAGE_LABELS[activeTask.stage || 'pending'] || activeTask.stage || 'Waiting'}
                    </Text>
                    <Progress percent={activeTask.progress || 0} strokeColor="#f8fafc" trailColor="rgba(255,255,255,0.15)" />
                    <Button
                      block
                      icon={<RightCircleOutlined />}
                      onClick={() => navigate(`/audit?task_id=${activeTask.id}`)}
                    >
                      Resume this session
                    </Button>
                  </>
                ) : (
                  <Empty
                    description={<span style={{ color: 'rgba(255,255,255,0.75)' }}>No audit sessions yet</span>}
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                )}
              </Space>
            </Card>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={12} xl={6}>
          <Card loading={loading} bordered={false} style={{ borderRadius: 20 }}>
            <Statistic title="Evidence documents" value={stats.totalDocuments} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card loading={loading} bordered={false} style={{ borderRadius: 20 }}>
            <Statistic title="Audit sessions" value={stats.totalTasks} prefix={<RobotOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card loading={loading} bordered={false} style={{ borderRadius: 20 }}>
            <Statistic title="Completed reports" value={stats.completedTasks} prefix={<FileSearchOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card loading={loading} bordered={false} style={{ borderRadius: 20 }}>
            <Statistic
              title="High-risk findings"
              value={stats.highRiskFindings}
              prefix={<WarningOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
      </Row>

      {dashboard && (dashboard.task_counts.running || 0) > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 24, borderRadius: 16 }}
          message={`${dashboard.task_counts.running} audit session(s) are active`}
          description="Use the workspace to monitor stage transitions, inspect findings, and jump to the report once the agent closes the loop."
        />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card
            bordered={false}
            style={{ borderRadius: 20 }}
            title="Recent agent sessions"
            extra={<Button type="link" onClick={() => navigate('/audit')}>View all</Button>}
          >
            <Table
              columns={columns}
              dataSource={recentTasks}
              rowKey="id"
              pagination={false}
              loading={loading}
              locale={{ emptyText: <Empty description="No sessions yet" /> }}
            />
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card bordered={false} style={{ borderRadius: 20 }} title="Operational posture">
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Card size="small" style={{ borderRadius: 16, background: '#f8fafc' }}>
                <Text strong>Current loop shape</Text>
                <Paragraph style={{ margin: '8px 0 0' }}>
                  The agent currently closes one pass through regulation retrieval, risk assessment, and report writing.
                  Use the workspace to see where the session finished and whether it relied on fallback evidence.
                </Paragraph>
              </Card>
              <Card size="small" style={{ borderRadius: 16, background: '#fff7ed' }}>
                <Text strong>Evidence trace</Text>
                <Paragraph style={{ margin: '8px 0 0' }}>
                  Pair findings with the knowledge graph to validate cited regulations before you share the report.
                </Paragraph>
                <Button type="link" icon={<BranchesOutlined />} onClick={() => navigate('/kg')}>
                  Open graph evidence view
                </Button>
              </Card>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DashboardPage;
