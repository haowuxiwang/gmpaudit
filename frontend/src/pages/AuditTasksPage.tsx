import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Divider,
  Drawer,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Progress,
  Select,
  Space,
  Tag,
  Timeline,
  Typography,
  Upload,
  message,
} from 'antd';
import {
  BranchesOutlined,
  FileSearchOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  StopOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { auditApi, documentApi } from '../services/api';
import type { AuditTask, Document, Finding } from '../types/api';
import { useTaskSSE } from '../hooks/useTaskSSE';
import AgentFlowChart from '../components/AgentFlowChart';
import AgentThinkingPanel from '../components/AgentThinkingPanel';
import FindingDetailCard from '../components/FindingDetailCard';
import {
  STATUS_COLORS,
  STATUS_LABELS,
  STAGE_LABELS,
  TASK_TYPE_LABELS,
  DOC_STATUS_LABELS,
} from '../constants/audit';
import { THEME } from '../constants/theme';

const { Paragraph, Text } = Typography;

const TASK_TYPE_OPTIONS = Object.entries(TASK_TYPE_LABELS).map(([value, label]) => ({ value, label }));

const STATUS_FILTER_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待处理' },
  { value: 'running', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
];

const TYPE_FILTER_OPTIONS = [
  { value: '', label: '全部类型' },
  ...TASK_TYPE_OPTIONS,
];

const STATUS_DOT_COLORS: Record<string, string> = {
  pending: THEME.pending,
  running: THEME.primary,
  awaiting_review: '#faad14',
  rejected: '#ff4d4f',
  completed: THEME.success,
  failed: THEME.error,
  cancelled: '#9CA3AF',
};

const AuditTasksPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();

  const [tasks, setTasks] = useState<AuditTask[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [selectedTask, setSelectedTask] = useState<AuditTask | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [elapsed, setElapsed] = useState('');

  const taskIdParam = searchParams.get('task_id');

  const hasRunning = useMemo(
    () => tasks.some((task) => task.status === 'running' || task.stage === 'queued'),
    [tasks],
  );

  const selectedTaskIsRunning = selectedTask?.status === 'running' || selectedTask?.stage === 'queued';
  const { events: sseEvents, thinkingEvents, currentStage, status: sseStatus } = useTaskSSE(
    selectedTaskId,
    selectedTaskIsRunning,
  );

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
  }, [loadTasks, taskIdParam]);

  useEffect(() => {
    if (!selectedTaskId) {
      setFindings([]);
      return;
    }
    void loadTaskDetails(selectedTaskId);
  }, [loadTaskDetails, selectedTaskId]);

  // Merge SSE events into selectedTask display
  useEffect(() => {
    setSelectedTask(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        stage: currentStage || prev.stage,
        events: sseEvents.length > 0 ? sseEvents : prev.events,
      };
    });
  }, [sseEvents, currentStage, selectedTask?.id]);

  // On SSE "done", do one final refresh
  useEffect(() => {
    if (sseStatus === 'completed' || sseStatus === 'failed' || sseStatus === 'awaiting_review') {
      void loadTasks(false, selectedTaskId);
      if (selectedTaskId) void loadTaskDetails(selectedTaskId);
    }
  }, [sseStatus, selectedTaskId, loadTasks, loadTaskDetails]);

  // Lightweight list poll (30s) to catch tasks from other entry points
  useEffect(() => {
    if (!hasRunning) return;

    const interval = setInterval(() => {
      void loadTasks(false, selectedTaskId);
    }, 30000);

    return () => clearInterval(interval);
  }, [hasRunning, loadTasks, selectedTaskId]);

  // Elapsed time timer
  useEffect(() => {
    if (!selectedTask || selectedTask.status !== 'running' || !selectedTask.started_at) {
      setElapsed('');
      return;
    }
    const updateElapsed = () => {
      const start = new Date(selectedTask.started_at!).getTime();
      const diff = Math.floor((Date.now() - start) / 1000);
      setElapsed(`已运行 ${Math.floor(diff / 60)}m ${diff % 60}s`);
    };
    updateElapsed();
    const interval = setInterval(updateElapsed, 1000);
    return () => clearInterval(interval);
  }, [selectedTask]);

  // Completion notification
  useEffect(() => {
    if (sseStatus === 'completed' || sseStatus === 'failed' || sseStatus === 'awaiting_review') {
      if ('Notification' in window && Notification.permission === 'default') {
        void Notification.requestPermission();
      }
      if ('Notification' in window && Notification.permission === 'granted') {
        const statusText = sseStatus === 'completed' ? '已完成'
          : sseStatus === 'failed' ? '失败' : '待审核';
        new Notification('AuditBee 任务完成', {
          body: `${selectedTask?.task_name || '审计任务'} - ${statusText}`,
        });
      }
    }
  }, [sseStatus, selectedTask?.task_name]);

  // Pre-request notification permission when tasks are running
  useEffect(() => {
    if (hasRunning && 'Notification' in window && Notification.permission === 'default') {
      void Notification.requestPermission();
    }
  }, [hasRunning]);

  const handleCreate = async (values: { task_name: string; task_type: string; document_ids: number[] }) => {
    try {
      setCreating(true);
      const result = await auditApi.createTask(values);
      setShowModal(false);
      form.resetFields();
      message.success('审计任务已创建');
      setDrawerOpen(true);
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

  const handleCancel = async (taskId: number) => {
    try {
      await auditApi.cancelTask(taskId);
      message.success('任务已取消');
      await loadTasks(false, selectedTaskId);
      if (selectedTaskId) await loadTaskDetails(selectedTaskId);
    } catch {
      message.error('取消任务失败');
    }
  };

  const handleSelectTask = (task: AuditTask) => {
    setSelectedTaskId(task.id);
    setSearchParams({ task_id: String(task.id) }, { replace: true });
    setDrawerOpen(true);
  };

  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      if (statusFilter && task.status !== statusFilter) return false;
      if (typeFilter && task.task_type !== typeFilter) return false;
      return true;
    });
  }, [tasks, statusFilter, typeFilter]);

  const selectedQuery = encodeURIComponent(
    findings[0]?.title || selectedTask?.task_name || 'GMP 偏差处理',
  );

  const evidenceDocuments = useMemo(
    () => selectedTask?.documents || [],
    [selectedTask],
  );

  return (
    <div>
      {/* Toolbar */}
      <Card
        bordered={false}
        style={{ marginBottom: 16, borderRadius: 12 }}
        styles={{ body: { padding: '12px 20px' } }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setShowModal(true); void loadDocuments(); }}>
            新建任务
          </Button>
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            options={STATUS_FILTER_OPTIONS}
            style={{ width: 130 }}
          />
          <Select
            value={typeFilter}
            onChange={setTypeFilter}
            options={TYPE_FILTER_OPTIONS}
            style={{ width: 160 }}
          />
          <div style={{ flex: 1 }} />
          <Text type="secondary">共 {filteredTasks.length} 个任务</Text>
        </div>
      </Card>

      {/* Task List */}
      <Card bordered={false} style={{ borderRadius: 12 }} styles={{ body: { padding: 0 } }}>
        {loading && tasks.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center' }}>加载中...</div>
        ) : filteredTasks.length === 0 ? (
          <Empty description="暂无审计任务" style={{ padding: 60 }} />
        ) : (
          <List
            dataSource={filteredTasks}
            rowKey="id"
            renderItem={(task) => {
              const isSelected = task.id === selectedTaskId;
              const dotColor = STATUS_DOT_COLORS[task.status] || STATUS_DOT_COLORS.pending;
              const isRunning = task.status === 'running';

              return (
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSelectTask(task)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleSelectTask(task); }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 16,
                    padding: '14px 20px',
                    cursor: 'pointer',
                    borderBottom: `1px solid ${THEME.border}`,
                    background: isSelected ? THEME.bgSelected : 'transparent',
                    borderLeft: isSelected ? `3px solid ${THEME.primary}` : '3px solid transparent',
                    transition: 'background 0.15s, border-color 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) (e.currentTarget.style.background = THEME.bgLayout);
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) (e.currentTarget.style.background = 'transparent');
                  }}
                >
                  {/* Status dot */}
                  <div
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      background: dotColor,
                      flexShrink: 0,
                      boxShadow: isRunning ? `0 0 0 3px ${dotColor}33` : 'none',
                      animation: isRunning ? 'pulse-dot 2s infinite' : 'none',
                    }}
                  />

                  {/* Task info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Text strong style={{ fontSize: 14 }}>{task.task_name}</Text>
                    <div style={{ marginTop: 2 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {TASK_TYPE_LABELS[task.task_type] || task.task_type}
                      </Text>
                    </div>
                  </div>

                  {/* Stage tag */}
                  <Tag style={{ borderRadius: 999, margin: 0 }}>
                    {STAGE_LABELS[task.stage || 'pending'] || task.stage || '等待执行'}
                  </Tag>

                  {/* Status tag */}
                  <Tag color={STATUS_COLORS[task.status] || 'default'} style={{ borderRadius: 999, margin: 0 }}>
                    {STATUS_LABELS[task.status] || task.status}
                  </Tag>

                  {/* Progress */}
                  <div style={{ width: 100, flexShrink: 0 }}>
                    <Progress
                      percent={task.progress || 0}
                      size="small"
                      strokeColor={THEME.primary}
                      trailColor={THEME.border}
                      status={task.status === 'failed' ? 'exception' : undefined}
                    />
                  </div>

                  {/* Actions */}
                  <Space size={0} onClick={(e) => e.stopPropagation()}>
                    {task.status === 'pending' && (
                      <Button
                        type="link"
                        size="small"
                        icon={<PlayCircleOutlined />}
                        onClick={() => void handleRun(task.id)}
                      >
                        运行
                      </Button>
                    )}
                    {task.report_id && (
                      <Button
                        type="link"
                        size="small"
                        icon={<FileSearchOutlined />}
                        onClick={() => navigate(`/reports?task_id=${task.id}`)}
                      >
                        报告
                      </Button>
                    )}
                    {task.status === 'running' && (
                      <Button
                        type="link"
                        size="small"
                        danger
                        icon={<StopOutlined />}
                        onClick={() => void handleCancel(task.id)}
                      >
                        取消
                      </Button>
                    )}
                  </Space>
                </div>
              );
            }}
          />
        )}
      </Card>

      {/* Pulse animation for running status dot */}
      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>

      {/* Detail Drawer */}
      <Drawer
        title={selectedTask?.task_name || '任务详情'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={480}
        styles={{ body: { padding: '16px 24px' } }}
      >
        {selectedTask ? (
          <Space direction="vertical" size={20} style={{ width: '100%' }}>
            {/* Header info */}
            <div>
              <Space wrap style={{ marginBottom: 12 }}>
                <Tag color={STATUS_COLORS[selectedTask.status] || 'default'} style={{ borderRadius: 999 }}>
                  {STATUS_LABELS[selectedTask.status] || selectedTask.status}
                </Tag>
                <Tag style={{ borderRadius: 999 }}>
                  {TASK_TYPE_LABELS[selectedTask.task_type] || selectedTask.task_type}
                </Tag>
                {selectedTask.stage && (
                  <Tag style={{ borderRadius: 999 }}>
                    {STAGE_LABELS[selectedTask.stage] || selectedTask.stage}
                  </Tag>
                )}
                {elapsed && <Text type="secondary" style={{ fontSize: 12 }}>{elapsed}</Text>}
              </Space>
              <Progress
                percent={selectedTask.progress || 0}
                strokeColor={THEME.primary}
                trailColor={THEME.border}
                status={selectedTask.status === 'failed' ? 'exception' : selectedTask.status === 'completed' ? 'success' : 'active'}
              />
            </div>

            {/* Agent Flow Chart */}
            {selectedTask.status === 'running' || selectedTask.status === 'completed' || selectedTask.status === 'failed' ? (() => {
              const STAGE_ORDER = ['parsing', 'regulation', 'risk', 'report'];
              const currentIdx = STAGE_ORDER.indexOf(selectedTask.stage || '');
              const completedStages = selectedTask.status === 'completed'
                ? STAGE_ORDER
                : currentIdx > 0
                  ? STAGE_ORDER.slice(0, currentIdx)
                  : [];
              return (
                <AgentFlowChart
                  currentStage={selectedTask.stage || 'pending'}
                  completedStages={completedStages}
                  failedStage={selectedTask.status === 'failed' ? selectedTask.stage : undefined}
                  onNodeClick={(stage) => {
                    const el = document.getElementById('task-timeline');
                    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }}
                />
              );
            })() : null}

            {/* Agent Thinking Panel */}
            {selectedTask.status === 'running' && (
              <AgentThinkingPanel
                thinkingEvents={thinkingEvents}
                currentStage={currentStage}
                isRunning={selectedTask.status === 'running'}
              />
            )}

            {/* Timeline */}
            {selectedTask.events && selectedTask.events.length > 0 && (
              <div id="task-timeline">
                <Text strong style={{ fontSize: 13, color: THEME.textSecondary }}>执行时间线</Text>
                <div style={{ marginTop: 12 }}>
                  <Timeline
                    items={selectedTask.events.map((event) => ({
                      color: event.level === 'error' ? 'red' : event.level === 'warning' ? 'orange' : THEME.primary,
                      children: (
                        <div>
                          <Text>{event.message}</Text>
                          <br />
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {STAGE_LABELS[event.stage] || event.stage} · {new Date(event.time).toLocaleString('zh-CN')}
                          </Text>
                        </div>
                      ),
                    }))}
                  />
                </div>
              </div>
            )}

            {/* Error message */}
            {selectedTask.error_message && (
              <div style={{ borderRadius: 8, background: THEME.bgError, padding: '10px 14px' }}>
                <Text strong style={{ color: THEME.error }}>错误</Text>
                <Paragraph style={{ margin: '6px 0 0', fontSize: 13 }}>{selectedTask.error_message}</Paragraph>
              </div>
            )}

            {/* Findings */}
            <div>
              <Text strong style={{ fontSize: 13, color: THEME.textSecondary }}>
                审计发现 {findings.length > 0 && `(${findings.length} 项)`}
              </Text>
              {findings.length > 0 ? (
                <div style={{ marginTop: 8 }}>
                  {findings.map((item) => (
                    <FindingDetailCard
                      key={item.id}
                      finding={item}
                      taskId={selectedTask.id}
                      onGraphTrace={(title, taskId) => {
                        setDrawerOpen(false);
                        navigate(`/kg?q=${encodeURIComponent(title)}&task_id=${taskId}`);
                      }}
                    />
                  ))}
                </div>
              ) : (
                <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 13 }}>
                  暂无审计发现
                </Text>
              )}
            </div>

            {/* Documents */}
            <div>
              <Text strong style={{ fontSize: 13, color: THEME.textSecondary }}>
                任务文档 {evidenceDocuments.length > 0 && `(${evidenceDocuments.length} 个)`}
              </Text>
              {evidenceDocuments.length > 0 ? (
                <List
                  style={{ marginTop: 8 }}
                  dataSource={evidenceDocuments}
                  size="small"
                  renderItem={(item) => (
                    <List.Item style={{ padding: '8px 0' }}>
                      <Space direction="vertical" size={2} style={{ width: '100%' }}>
                        <Text strong style={{ fontSize: 13 }}>{item.filename}</Text>
                        <Space wrap size={6}>
                          <Tag style={{ margin: 0, borderRadius: 4 }}>{DOC_STATUS_LABELS[item.status] || item.status}</Tag>
                          <Tag color="blue" style={{ margin: 0, borderRadius: 4 }}>{item.risk_level || '未知风险'}</Tag>
                          <Text type="secondary" style={{ fontSize: 12 }}>{item.findings_count} 项发现</Text>
                        </Space>
                      </Space>
                    </List.Item>
                  )}
                />
              ) : (
                <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 13 }}>
                  暂无文档记录
                </Text>
              )}
            </div>

            {/* Actions */}
            <div style={{ borderTop: `1px solid ${THEME.border}`, paddingTop: 16 }}>
              <Space>
                {selectedTask.status === 'pending' && (
                  <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => void handleRun(selectedTask.id)}>
                    运行
                  </Button>
                )}
                {selectedTask.status === 'awaiting_review' && (
                  <>
                    <Button
                      type="primary"
                      onClick={() => {
                        let comment = '';
                        Modal.confirm({
                          title: '批准任务',
                          content: (
                            <div>
                              <p>确定要批准此任务吗？批准后将继续执行。</p>
                              <Input.TextArea
                                placeholder="审核意见（可选）"
                                rows={3}
                                onChange={(e) => { comment = e.target.value; }}
                              />
                            </div>
                          ),
                          onOk: async () => {
                            try {
                              await auditApi.approveTask(selectedTask.id, comment);
                              message.success('任务已批准');
                              void loadTasks(false, selectedTaskId);
                            } catch (err) {
                              message.error('批准失败，请重试');
                            }
                          },
                        });
                      }}
                    >
                      批准
                    </Button>
                    <Button
                      danger
                      onClick={() => {
                        let comment = '';
                        Modal.confirm({
                          title: '驳回任务',
                          content: (
                            <div>
                              <p>确定要驳回此任务吗？</p>
                              <Input.TextArea
                                placeholder="驳回原因（必填）"
                                rows={3}
                                onChange={(e) => { comment = e.target.value; }}
                              />
                            </div>
                          ),
                          onOk: async () => {
                            if (!comment.trim()) {
                              message.warning('请填写驳回原因');
                              throw new Error('Missing comment');
                            }
                            try {
                              await auditApi.rejectTask(selectedTask.id, comment);
                              message.success('任务已驳回');
                              void loadTasks(false, selectedTaskId);
                            } catch (err) {
                              message.error('驳回失败，请重试');
                            }
                          },
                        });
                      }}
                    >
                      驳回
                    </Button>
                  </>
                )}
                {selectedTask.report_id && (
                  <Button icon={<FileSearchOutlined />} onClick={() => navigate(`/reports?task_id=${selectedTask.id}`)}>
                    查看报告
                  </Button>
                )}
                {selectedTask.status === 'running' && (
                  <Button
                    danger
                    icon={<StopOutlined />}
                    onClick={() => {
                      Modal.confirm({
                        title: '取消任务',
                        content: '确定要取消正在运行的任务吗？',
                        okText: '确定取消',
                        okButtonProps: { danger: true },
                        onOk: async () => {
                          try {
                            await auditApi.cancelTask(selectedTask.id);
                            message.success('任务已取消');
                            void loadTasks(false, selectedTaskId);
                          } catch {
                            message.error('取消任务失败');
                          }
                        },
                      });
                    }}
                  >
                    取消任务
                  </Button>
                )}
                <Button
                  icon={<BranchesOutlined />}
                  onClick={() => {
                    setDrawerOpen(false);
                    navigate(`/kg?q=${selectedQuery}&task_id=${selectedTask.id}`);
                  }}
                >
                  知识图谱
                </Button>
              </Space>
            </div>
          </Space>
        ) : (
          <Empty description="请选择一个审计任务查看详情" />
        )}
      </Drawer>

      {/* Create Task Modal */}
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
              dropdownRender={(menu) => (
                <>
                  {menu}
                  <Divider style={{ margin: '8px 0' }} />
                  <Upload
                    customRequest={async (options) => {
                      const { file, onSuccess, onError } = options;
                      try {
                        await documentApi.uploadBatch([file as File]);
                        onSuccess?.({});
                        message.success('上传成功，正在处理中');
                        void loadDocuments();
                      } catch (error) {
                        onError?.(error as Error);
                        message.error('上传失败');
                      }
                    }}
                    showUploadList={false}
                    accept=".pdf,.docx,.doc,.txt,.jpg,.jpeg,.png"
                  >
                    <Button type="link" icon={<UploadOutlined />} block>
                      上传新文档
                    </Button>
                  </Upload>
                </>
              )}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AuditTasksPage;
