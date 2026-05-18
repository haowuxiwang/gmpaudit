import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Timeline,
  Typography,
  message,
} from 'antd';
import {
  BranchesOutlined,
  FileSearchOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  RobotOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { auditApi, documentApi } from '../services/api';
import type { AuditTask, Document, Finding } from '../types/api';

const { Title, Paragraph, Text } = Typography;

const TASK_TYPE_OPTIONS = [
  { value: 'deviation_analysis', label: 'Deviation analysis' },
  { value: 'sop_compliance', label: 'SOP compliance' },
  { value: 'consistency_check', label: 'Change control consistency' },
  { value: 'risk_assessment', label: 'Risk assessment' },
];

const STATUS_COLORS: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
};

const STAGE_LABELS: Record<string, string> = {
  pending: 'Waiting for dispatch',
  queued: 'Queued for agent execution',
  running: 'Agent is running',
  parsing: 'Parsing evidence',
  risk: 'Assessing risk',
  completed: 'Report finalized',
  failed: 'Execution failed',
};

const SEVERITY_COLORS: Record<string, string> = {
  high: 'red',
  critical: 'red',
  medium: 'orange',
  low: 'green',
  info: 'blue',
};

const AuditTasksPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [tasks, setTasks] = useState<AuditTask[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [selectedTask, setSelectedTask] = useState<AuditTask | null>(null);
  const taskIdParam = searchParams.get('task_id');

  const syncSelectedTask = useCallback((items: AuditTask[], preferredId?: number | null) => {
    const preferred = preferredId ?? selectedTaskId;
    const nextTask =
      (preferred ? items.find((task) => task.id === preferred) : undefined) ||
      items[0] ||
      null;
    setSelectedTask(nextTask);
    setSelectedTaskId(nextTask?.id || null);
    if (nextTask && taskIdParam !== String(nextTask.id)) {
      setSearchParams({ task_id: String(nextTask.id) }, { replace: true });
    }
  }, [selectedTaskId, setSearchParams, taskIdParam]);

  const loadTasks = useCallback(async (showSpinner = false, preferredId?: number | null) => {
    try {
      if (showSpinner) setLoading(true);
      const result = await auditApi.listTasks();
      const items = result?.items || [];
      setTasks(items);
      syncSelectedTask(items, preferredId);
    } catch {
      if (showSpinner) {
        message.error('Failed to load audit sessions');
      }
    } finally {
      if (showSpinner) setLoading(false);
    }
  }, [syncSelectedTask]);

  const loadDocuments = useCallback(async () => {
    try {
      const result = await documentApi.list(1, 100);
      setDocuments((result?.items || []).filter((doc) => doc.process_status === 'processed'));
    } catch {
      message.error('Failed to load processed documents');
    }
  }, []);

  const loadTaskDetails = useCallback(async (taskId: number) => {
    try {
      const [task, taskFindings] = await Promise.all([
        auditApi.getTask(taskId),
        auditApi.getFindings(taskId).catch(() => []),
      ]);

      setSelectedTask(task);
      setSelectedTaskId(task.id);
      setFindings(taskFindings);
    } catch {
      message.error('Failed to load task details');
    }
  }, []);

  useEffect(() => {
    const taskId = Number(taskIdParam);
    void loadTasks(true, Number.isFinite(taskId) && taskId > 0 ? taskId : null);
    void loadDocuments();
  }, [loadDocuments, loadTasks, taskIdParam]);

  useEffect(() => {
    if (!selectedTaskId) {
      setFindings([]);
      return;
    }
    void loadTaskDetails(selectedTaskId);
  }, [loadTaskDetails, selectedTaskId]);

  useEffect(() => {
    const hasRunning = tasks.some((task) => task.status === 'running' || task.stage === 'queued');
    if (!hasRunning) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    if (!pollRef.current) {
      pollRef.current = setInterval(() => {
        void loadTasks(false, selectedTaskId);
        if (selectedTaskId) {
          void loadTaskDetails(selectedTaskId);
        }
      }, 4000);
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [loadTaskDetails, loadTasks, selectedTaskId, tasks]);

  const handleCreate = async (values: { task_name: string; task_type: string; document_ids: number[] }) => {
    try {
      setCreating(true);
      const result = await auditApi.createTask(values);
      setShowModal(false);
      form.resetFields();
      message.success('Audit session created');
      await loadTasks(true, result.id);
    } catch {
      message.error('Failed to create audit session');
    } finally {
      setCreating(false);
    }
  };

  const handleRun = async (taskId: number) => {
    try {
      await auditApi.runTask(taskId);
      message.success('Agent session queued');
      await loadTasks(true, taskId);
      await loadTaskDetails(taskId);
    } catch {
      message.error('Failed to queue agent session');
    }
  };

  const runningCount = tasks.filter((task) => task.status === 'running').length;
  const completedCount = tasks.filter((task) => task.status === 'completed').length;
  const failedCount = tasks.filter((task) => task.status === 'failed').length;
  const selectedQuery = encodeURIComponent(
    findings[0]?.title || selectedTask?.task_name || 'GMP deviation handling',
  );

  const evidenceDocuments = useMemo(
    () => selectedTask?.documents || [],
    [selectedTask],
  );

  const columns = [
    {
      title: 'Session',
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
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (status: string) => <Tag color={STATUS_COLORS[status] || 'default'}>{status}</Tag>,
    },
    {
      title: 'Stage',
      dataIndex: 'stage',
      key: 'stage',
      width: 200,
      render: (stage?: string) => STAGE_LABELS[stage || 'pending'] || stage || 'Waiting for dispatch',
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
      width: 220,
      render: (_: unknown, record: AuditTask) => (
        <Space>
          {record.status === 'pending' && (
            <Button type="link" icon={<PlayCircleOutlined />} onClick={() => void handleRun(record.id)}>
              Run
            </Button>
          )}
          <Button type="link" onClick={() => void loadTaskDetails(record.id)}>
            Inspect
          </Button>
          {record.report_id && (
            <Button type="link" icon={<FileSearchOutlined />} onClick={() => navigate(`/reports?task_id=${record.id}`)}>
              Report
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
          background: 'linear-gradient(135deg, #111827 0%, #1d4ed8 100%)',
          color: '#fff',
        }}
        bodyStyle={{ padding: 28 }}
      >
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} xl={16}>
            <Space direction="vertical" size={12}>
              <Tag color="rgba(255,255,255,0.18)" style={{ borderRadius: 999, alignSelf: 'flex-start' }}>
                multi-agent workspace
              </Tag>
              <Title level={2} style={{ color: '#fff', margin: 0 }}>
                Watch the audit agent close the loop from evidence to report.
              </Title>
              <Paragraph style={{ color: 'rgba(255,255,255,0.82)', fontSize: 16, marginBottom: 0 }}>
                This workspace surfaces stage transitions, document-level progress, findings, and the graph evidence
                you need before sharing the report.
              </Paragraph>
              <Space wrap>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowModal(true)}>
                  New audit session
                </Button>
                <Button onClick={() => navigate('/documents')}>Upload more evidence</Button>
                {selectedTask && (
                  <Button
                    icon={<BranchesOutlined />}
                    onClick={() => navigate(`/kg?q=${selectedQuery}&task_id=${selectedTask.id}`)}
                  >
                    Open graph evidence
                  </Button>
                )}
              </Space>
            </Space>
          </Col>
          <Col xs={24} xl={8}>
            <Card bordered={false} style={{ borderRadius: 20, background: 'rgba(255,255,255,0.08)' }}>
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Text style={{ color: 'rgba(255,255,255,0.75)' }}>Current focus</Text>
                <Title level={4} style={{ color: '#fff', margin: 0 }}>
                  {selectedTask?.task_name || 'No session selected'}
                </Title>
                <Text style={{ color: 'rgba(255,255,255,0.82)' }}>
                  {selectedTask ? STAGE_LABELS[selectedTask.stage || 'pending'] || selectedTask.stage : 'Select a session'}
                </Text>
                <Progress
                  percent={selectedTask?.progress || 0}
                  strokeColor="#f8fafc"
                  trailColor="rgba(255,255,255,0.14)"
                />
              </Space>
            </Card>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={8}>
          <Card bordered={false} style={{ borderRadius: 20 }}>
            <Statistic title="Running sessions" value={runningCount} prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} style={{ borderRadius: 20 }}>
            <Statistic title="Completed sessions" value={completedCount} prefix={<FileSearchOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} style={{ borderRadius: 20 }}>
            <Statistic title="Failed sessions" value={failedCount} prefix={<RobotOutlined />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={13}>
          <Card
            bordered={false}
            style={{ borderRadius: 20 }}
            title="Audit sessions"
            extra={<Button type="link" onClick={() => void loadTasks(true, selectedTaskId)}>Refresh</Button>}
          >
            <Table
              columns={columns}
              dataSource={tasks}
              rowKey="id"
              loading={loading}
              pagination={{ pageSize: 8 }}
              onRow={(record) => ({
                onClick: () => {
                  setSelectedTaskId(record.id);
                  setSearchParams({ task_id: String(record.id) }, { replace: true });
                },
              })}
              rowClassName={(record) => (record.id === selectedTaskId ? 'ant-table-row-selected' : '')}
              locale={{ emptyText: <Empty description="No audit sessions yet" /> }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={11}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card
              bordered={false}
              style={{ borderRadius: 20 }}
              title="Agent timeline"
              extra={
                selectedTask?.report_id ? (
                  <Button type="link" onClick={() => navigate(`/reports?task_id=${selectedTask.id}`)}>
                    Open report
                  </Button>
                ) : null
              }
            >
              {selectedTask ? (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag color={STATUS_COLORS[selectedTask.status] || 'default'}>{selectedTask.status}</Tag>
                    <Tag>{selectedTask.task_type}</Tag>
                    {selectedTask.stage && <Tag color="blue">{selectedTask.stage}</Tag>}
                  </Space>
                  <Progress percent={selectedTask.progress || 0} status={selectedTask.status === 'failed' ? 'exception' : 'active'} />
                  <Timeline
                    items={(selectedTask.events || []).map((event) => ({
                      color: event.level === 'error' ? 'red' : event.level === 'warning' ? 'orange' : 'blue',
                      children: (
                        <Space direction="vertical" size={0}>
                          <Text strong>{event.message}</Text>
                          <Text type="secondary">
                            {event.stage} · {new Date(event.time).toLocaleString()}
                          </Text>
                        </Space>
                      ),
                    }))}
                  />
                  {selectedTask.error_message && (
                    <Card size="small" style={{ borderRadius: 16, background: '#fff1f0' }}>
                      <Text strong>Error</Text>
                      <Paragraph style={{ margin: '8px 0 0' }}>{selectedTask.error_message}</Paragraph>
                    </Card>
                  )}
                </Space>
              ) : (
                <Empty description="Select an audit session to inspect its loop" />
              )}
            </Card>

            <Card bordered={false} style={{ borderRadius: 20 }} title="Evidence and findings">
              {selectedTask ? (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <div>
                    <Text strong>Documents in session</Text>
                    <List
                      style={{ marginTop: 8 }}
                      dataSource={evidenceDocuments}
                      locale={{ emptyText: 'No document progress recorded yet' }}
                      renderItem={(item) => (
                        <List.Item>
                          <Space direction="vertical" size={0} style={{ width: '100%' }}>
                            <Text strong>{item.filename}</Text>
                            <Space wrap>
                              <Tag>{item.status}</Tag>
                              <Tag color="blue">{item.risk_level || 'unknown risk'}</Tag>
                              <Text type="secondary">{item.findings_count} finding(s)</Text>
                            </Space>
                          </Space>
                        </List.Item>
                      )}
                    />
                  </div>
                  <div>
                    <Text strong>Findings</Text>
                    <List
                      style={{ marginTop: 8 }}
                      dataSource={findings}
                      locale={{ emptyText: 'No findings saved yet' }}
                      renderItem={(item) => (
                        <List.Item
                          actions={[
                            <Button
                              key="graph"
                              type="link"
                              onClick={() =>
                                navigate(`/kg?q=${encodeURIComponent(item.title)}&task_id=${selectedTask.id}`)
                              }
                            >
                              Trace in graph
                            </Button>,
                          ]}
                        >
                          <List.Item.Meta
                            title={
                              <Space wrap>
                                <Tag color={SEVERITY_COLORS[item.severity] || 'default'}>{item.severity}</Tag>
                                <span>{item.title}</span>
                              </Space>
                            }
                            description={item.description || 'No description'}
                          />
                        </List.Item>
                      )}
                    />
                  </div>
                </Space>
              ) : (
                <Empty description="Select a task to view evidence and findings" />
              )}
            </Card>
          </Space>
        </Col>
      </Row>

      <Modal
        title="Create audit session"
        open={showModal}
        confirmLoading={creating}
        onCancel={() => setShowModal(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={(values) => void handleCreate(values)}>
          <Form.Item
            name="task_name"
            label="Session name"
            rules={[{ required: true, message: 'Enter a session name' }]}
          >
            <Input placeholder="Deviation investigation for batch A-17" />
          </Form.Item>
          <Form.Item
            name="task_type"
            label="Audit type"
            rules={[{ required: true, message: 'Select an audit type' }]}
            initialValue="deviation_analysis"
          >
            <Select options={TASK_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item
            name="document_ids"
            label="Documents"
            rules={[{ required: true, message: 'Select at least one processed document' }]}
          >
            <Select
              mode="multiple"
              optionFilterProp="label"
              options={documents.map((doc) => ({ value: doc.id, label: doc.filename }))}
              placeholder="Attach processed evidence documents"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AuditTasksPage;
