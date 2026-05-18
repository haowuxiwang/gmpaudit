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
import { STATUS_COLORS, STAGE_LABELS, TASK_TYPE_LABELS } from '../constants/audit';

const { Title, Paragraph, Text } = Typography;

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
      message.error('加载工作台数据失败');
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
      title: '任务',
      dataIndex: 'task_name',
      key: 'task_name',
      render: (value: string, record: AuditTask) => (
        <Space direction="vertical" size={0}>
          <Text strong>{value}</Text>
          <Text type="secondary">{TASK_TYPE_LABELS[record.task_type] || record.task_type}</Text>
        </Space>
      ),
    },
    {
      title: '阶段',
      dataIndex: 'stage',
      key: 'stage',
      width: 150,
      render: (stage?: string, record?: AuditTask) => (
        <Tag color={STATUS_COLORS[record?.status || 'pending'] || 'default'}>
          {STAGE_LABELS[stage || 'pending'] || stage || '待处理'}
        </Tag>
      ),
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 180,
      render: (value: number, record: AuditTask) => (
        <Progress
          percent={value || 0}
          size="small"
          status={record.status === 'completed' ? 'success' : record.status === 'failed' ? 'exception' : 'active'}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 130,
      render: (_: unknown, record: AuditTask) => (
        <Button type="link" onClick={() => navigate(`/audit?task_id=${record.id}`)}>
          进入工作台
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
        styles={{ body: { padding: 28 } }}
      >
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} lg={16}>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Tag color="rgba(255,255,255,0.18)" style={{ alignSelf: 'flex-start', borderRadius: 999 }}>
                审计工作台
              </Tag>
              <Title level={2} style={{ color: '#fff', margin: 0 }}>
                AuditBee
              </Title>
              <Paragraph style={{ color: 'rgba(255,255,255,0.82)', fontSize: 16, marginBottom: 0 }}>
                多智能体协作完成 GMP 合规审计，自动生成结构化报告。
              </Paragraph>
              <Space wrap>
                <Button type="primary" size="large" icon={<RobotOutlined />} onClick={() => navigate('/audit')}>
                  进入审计
                </Button>
                <Button size="large" onClick={() => navigate('/documents')}>
                  上传文档
                </Button>
                <Button size="large" onClick={() => navigate('/kg')} icon={<BranchesOutlined />}>
                  知识图谱
                </Button>
              </Space>
            </Space>
          </Col>
          <Col xs={24} lg={8}>
            <Card
              bordered={false}
              style={{ borderRadius: 20, background: 'rgba(255,255,255,0.1)', color: '#fff' }}
              styles={{ body: { padding: 20 } }}
            >
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                <Text style={{ color: 'rgba(255,255,255,0.75)' }}>当前焦点</Text>
                {activeTask ? (
                  <>
                    <Title level={4} style={{ color: '#fff', margin: 0 }}>
                      {activeTask.task_name}
                    </Title>
                    <Text style={{ color: 'rgba(255,255,255,0.82)' }}>
                      {STAGE_LABELS[activeTask.stage || 'pending'] || activeTask.stage || '待处理'}
                    </Text>
                    <Progress percent={activeTask.progress || 0} strokeColor="#f8fafc" trailColor="rgba(255,255,255,0.15)" />
                    <Button
                      block
                      icon={<RightCircleOutlined />}
                      onClick={() => navigate(`/audit?task_id=${activeTask.id}`)}
                    >
                      继续此任务
                    </Button>
                  </>
                ) : (
                  <Empty
                    description={<span style={{ color: 'rgba(255,255,255,0.75)' }}>暂无任务记录</span>}
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
            <Statistic title="文档总数" value={stats.totalDocuments} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card loading={loading} bordered={false} style={{ borderRadius: 20 }}>
            <Statistic title="审计任务" value={stats.totalTasks} prefix={<RobotOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card loading={loading} bordered={false} style={{ borderRadius: 20 }}>
            <Statistic title="已完成报告" value={stats.completedTasks} prefix={<FileSearchOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card loading={loading} bordered={false} style={{ borderRadius: 20 }}>
            <Statistic
              title="高风险发现"
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
          message={`${dashboard.task_counts.running} 个审计任务正在执行`}
          description="可在工作台监控阶段进度、查看发现项，任务完成后可直接查看报告。"
        />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card
            bordered={false}
            style={{ borderRadius: 20 }}
            title="最近任务"
            extra={<Button type="link" onClick={() => navigate('/audit')}>查看全部</Button>}
          >
            <Table
              columns={columns}
              dataSource={recentTasks}
              rowKey="id"
              pagination={false}
              loading={loading}
              locale={{ emptyText: <Empty description="暂无任务记录" /> }}
            />
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card bordered={false} style={{ borderRadius: 20 }} title="系统概览">
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Card size="small" style={{ borderRadius: 16, background: '#f8fafc' }}>
                <Text strong>审计流程</Text>
                <Paragraph style={{ margin: '8px 0 0' }}>
                  智能体依次完成法规检索、风险评估和报告撰写。可在工作台查看任务执行状态。
                </Paragraph>
              </Card>
              <Card size="small" style={{ borderRadius: 16, background: '#fff7ed' }}>
                <Text strong>数据链路</Text>
                <Paragraph style={{ margin: '8px 0 0' }}>
                  结合知识图谱验证引用的法规依据，确保报告准确性。
                </Paragraph>
                <Button type="link" icon={<BranchesOutlined />} onClick={() => navigate('/kg')}>
                  查看知识图谱
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
