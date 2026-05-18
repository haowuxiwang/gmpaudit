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
import {
  STATUS_COLORS,
  STATUS_LABELS,
  STAGE_LABELS,
  TASK_TYPE_LABELS,
  SEVERITY_COLORS,
  DOC_STATUS_LABELS,
} from '../constants/audit';

const { Title, Paragraph, Text } = Typography;

const TASK_TYPE_OPTIONS = Object.entries(TASK_TYPE_LABELS).map(([value, label]) => ({ value, label }));

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
        message.error('加载审计任务失败');
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
      message.error('加载已处理文档失败');
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
      message.error('加载任务详情失败');
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
      message.success('审计任务已创建');
      await loadTasks(true, result.id);
    } catch {
      message.error('创建审计任务失败');
    } finally {
      setCreating(false);
    }
  };

  const handleRun = async (taskId: number) => {
    try {
      await auditApi.runTask(taskId);
      message.success('审计任务已提交');
      await loadTasks(true, taskId);
      await loadTaskDetails(taskId);
    } catch {
      message.error('提交审计任务失败');
    }
  };

  const runningCount = tasks.filter((task) => task.status === 'running').length;
  const completedCount = tasks.filter((task) => task.status === 'completed').length;
  const failedCount = tasks.filter((task) => task.status === 'failed').length;
  const selectedQuery = encodeURIComponent(
    findings[0]?.title || selectedTask?.task_name || 'GMP 偏差处理',
  );

  const evidenceDocuments = useMemo(
    () => selectedTask?.documents || [],
    [selectedTask],
  );

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
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (status: string) => <Tag color={STATUS_COLORS[status] || 'default'}>{STATUS_LABELS[status] || status}</Tag>,
    },
    {
      title: '阶段',
      dataIndex: 'stage',
      key: 'stage',
      width: 200,
      render: (stage?: string) => (
        <Tag>{STAGE_LABELS[stage || 'pending'] || stage || '等待执行'}</Tag>
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
      width: 220,
      render: (_: unknown, record: AuditTask) => (
        <Space>
          {record.status === 'pending' && (
            <Button type="link" icon={<PlayCircleOutlined />} onClick={() => void handleRun(record.id)}>
              运行
            </Button>
          )}
          <Button type="link" onClick={() => void loadTaskDetails(record.id)}>
            查看
          </Button>
          {record.report_id && (
            <Button type="link" icon={<FileSearchOutlined />} onClick={() => navigate(`/reports?task_id=${record.id}`)}>
              报告
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
        styles={{ body: { padding: 28 } }}
      >
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} xl={16}>
            <Space direction="vertical" size={12}>
              <Tag color="rgba(255,255,255,0.18)" style={{ borderRadius: 999, alignSelf: 'flex-start' }}>
                审计任务
              </Tag>
              <Title level={2} style={{ color: '#fff', margin: 0 }}>
                创建审计任务，多智能体协作完成合规分析
              </Title>
              <Paragraph style={{ color: 'rgba(255,255,255,0.82)', fontSize: 16, marginBottom: 0 }}>
                实时查看任务进度、文档解析状态、审计发现和知识图谱溯源
              </Paragraph>
              <Space wrap>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowModal(true)}>
                  新建任务
                </Button>
                <Button onClick={() => navigate('/documents')}>上传文档</Button>
                {selectedTask && (
                  <Button
                    icon={<BranchesOutlined />}
                    onClick={() => navigate(`/kg?q=${selectedQuery}&task_id=${selectedTask.id}`)}
                  >
                    知识图谱
                  </Button>
                )}
              </Space>
            </Space>
          </Col>
          <Col xs={24} xl={8}>
            <Card bordered={false} style={{ borderRadius: 20, background: 'rgba(255,255,255,0.08)' }}>
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Text style={{ color: 'rgba(255,255,255,0.75)' }}>当前任务</Text>
                <Title level={4} style={{ color: '#fff', margin: 0 }}>
                  {selectedTask?.task_name || '未选择任务'}
                </Title>
                <Text style={{ color: 'rgba(255,255,255,0.82)' }}>
                  {selectedTask ? STAGE_LABELS[selectedTask.stage || 'pending'] || selectedTask.stage : '请选择任务'}
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
            <Statistic title="进行中" value={runningCount} prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} style={{ borderRadius: 20 }}>
            <Statistic title="已完成" value={completedCount} prefix={<FileSearchOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} style={{ borderRadius: 20 }}>
            <Statistic title="失败" value={failedCount} prefix={<RobotOutlined />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={13}>
          <Card
            bordered={false}
            style={{ borderRadius: 20 }}
            title="任务列表"
            extra={<Button type="link" onClick={() => void loadTasks(true, selectedTaskId)}>刷新</Button>}
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
              locale={{ emptyText: <Empty description="暂无审计任务" /> }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={11}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card
              bordered={false}
              style={{ borderRadius: 20 }}
              title="执行时间线"
              extra={
                selectedTask?.report_id ? (
                  <Button type="link" onClick={() => navigate(`/reports?task_id=${selectedTask.id}`)}>
                    查看报告
                  </Button>
                ) : null
              }
            >
              {selectedTask ? (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag color={STATUS_COLORS[selectedTask.status] || 'default'}>{STATUS_LABELS[selectedTask.status] || selectedTask.status}</Tag>
                    <Tag>{TASK_TYPE_LABELS[selectedTask.task_type] || selectedTask.task_type}</Tag>
                    {selectedTask.stage && <Tag>{STAGE_LABELS[selectedTask.stage] || selectedTask.stage}</Tag>}
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
                      <Text strong>错误</Text>
                      <Paragraph style={{ margin: '8px 0 0' }}>{selectedTask.error_message}</Paragraph>
                    </Card>
                  )}
                </Space>
              ) : (
                <Empty description="请选择一个审计任务查看详情" />
              )}
            </Card>

            <Card bordered={false} style={{ borderRadius: 20 }} title="审计发现">
              {selectedTask ? (
                <Space direction="vertical" size={16} style={{ width: '100%' }}>
                  <div>
                    <Text strong>任务文档</Text>
                    <List
                      style={{ marginTop: 8 }}
                      dataSource={evidenceDocuments}
                      locale={{ emptyText: '暂无文档记录' }}
                      renderItem={(item) => (
                        <List.Item>
                          <Space direction="vertical" size={0} style={{ width: '100%' }}>
                            <Text strong>{item.filename}</Text>
                            <Space wrap>
                              <Tag>{DOC_STATUS_LABELS[item.status] || item.status}</Tag>
                              <Tag color="blue">{item.risk_level || '未知风险'}</Tag>
                              <Text type="secondary">{item.findings_count} 项发现</Text>
                            </Space>
                          </Space>
                        </List.Item>
                      )}
                    />
                  </div>
                  <div>
                    <Text strong>审计发现</Text>
                    <List
                      style={{ marginTop: 8 }}
                      dataSource={findings}
                      locale={{ emptyText: '暂无审计发现' }}
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
                              图谱溯源
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
                            description={item.description || '暂无描述'}
                          />
                        </List.Item>
                      )}
                    />
                  </div>
                </Space>
              ) : (
                <Empty description="请选择任务查看审计发现" />
              )}
            </Card>
          </Space>
        </Col>
      </Row>

      <Modal
        title="创建审计任务"
        open={showModal}
        confirmLoading={creating}
        onCancel={() => setShowModal(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={(values) => void handleCreate(values)}>
          <Form.Item
            name="task_name"
            label="任务名称"
            rules={[{ required: true, message: '请输入任务名称' }]}
          >
            <Input placeholder="例如：批号 A-17 偏差调查" />
          </Form.Item>
          <Form.Item
            name="task_type"
            label="审计类型"
            rules={[{ required: true, message: '请选择审计类型' }]}
            initialValue="deviation_analysis"
          >
            <Select options={TASK_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item
            name="document_ids"
            label="选择文档"
            rules={[{ required: true, message: '请选择至少一个已处理的文档' }]}
          >
            <Select
              mode="multiple"
              optionFilterProp="label"
              options={documents.map((doc) => ({ value: doc.id, label: doc.filename }))}
              placeholder="请选择已处理的文档"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AuditTasksPage;
