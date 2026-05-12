import React, { useEffect, useRef, useState } from 'react';
import { Button, Form, Input, Modal, Select, Space, Table, Tag, Typography, message } from 'antd';
import { PlayCircleOutlined, PlusOutlined, FileSearchOutlined } from '@ant-design/icons';

import { useNavigate } from 'react-router-dom';
import { auditApi, documentApi } from '../services/api';
import type { AuditTask, Document } from '../types/api';

const { Title } = Typography;

const TASK_TYPE_LABELS: Record<string, string> = {
  deviation_analysis: '偏差分析',
  sop_compliance: 'SOP 合规',
  consistency_check: '一致性检查',
  risk_assessment: '风险评估',
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '待执行',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
};

const AuditTasksPage: React.FC = () => {
  const [tasks, setTasks] = useState<AuditTask[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    void loadTasks(true);
    void loadDocuments();
  }, []);

  // Poll only when tasks are running (use ref to avoid interval churn)
  useEffect(() => {
    const hasRunning = tasks.some((t) => t.status === 'running');
    if (hasRunning && !pollRef.current) {
      pollRef.current = setInterval(() => { void loadTasks(false); }, 5000);
    } else if (!hasRunning && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [tasks]);

  const loadTasks = async (showLoading: boolean) => {
    try {
      if (showLoading) setLoading(true);
      const result = await auditApi.listTasks();
      setTasks(result?.items || []);
    } catch {
      if (showLoading) message.error('加载审计任务失败');
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  const loadDocuments = async () => {
    try {
      const result = await documentApi.list();
      setDocuments((result?.items || []).filter((doc) => doc.process_status === 'processed'));
    } catch {
      message.error('加载文档失败');
    }
  };

  const handleCreate = async (values: { task_name: string; task_type: string; document_ids: number[] }) => {
    try {
      await auditApi.createTask(values);
      message.success('审计任务已创建');
      setShowModal(false);
      form.resetFields();
      await loadTasks(true);
    } catch {
      message.error('创建任务失败');
    }
  };

  const handleRun = async (id: number) => {
    try {
      await auditApi.runTask(id);
      message.success('审计任务已启动');
      await loadTasks(true);
    } catch {
      message.error('启动任务失败');
    }
  };

  const columns = [
    { title: '任务名称', dataIndex: 'task_name', key: 'task_name' },
    {
      title: '类型',
      dataIndex: 'task_type',
      key: 'task_type',
      width: 140,
      render: (type: string) => TASK_TYPE_LABELS[type] || type,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => <Tag color={STATUS_COLORS[status] || 'default'}>{STATUS_LABELS[status] || status}</Tag>,
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 100,
      render: (progress: number) => <span>{progress ?? 0}%</span>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => (time ? new Date(time).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: unknown, record: AuditTask) => (
        <Space>
          {record.status === 'pending' && (
            <Button type="link" icon={<PlayCircleOutlined />} onClick={() => void handleRun(record.id)}>
              运行
            </Button>
          )}
          {record.status === 'completed' && (
            <Button type="link" icon={<FileSearchOutlined />} onClick={() => navigate(`/reports?task_id=${record.id}`)}>
              查看报告
            </Button>
          )}
          {record.error_message && <Tag color="error">{record.error_message}</Tag>}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>审计任务</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowModal(true)}>
          创建任务
        </Button>
      </div>

      <Modal
        title="创建审计任务"
        open={showModal}
        onCancel={() => setShowModal(false)}
        onOk={() => form.submit()}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={(values) => void handleCreate(values)}>
          <Form.Item name="task_name" label="任务名称" rules={[{ required: true, message: '请输入任务名称' }]}>
            <Input placeholder="例如：批记录偏差审计" />
          </Form.Item>
          <Form.Item name="task_type" label="任务类型" rules={[{ required: true, message: '请选择任务类型' }]}>
            <Select
              options={[
                { value: 'deviation_analysis', label: '偏差分析' },
                { value: 'sop_compliance', label: 'SOP 合规' },
                { value: 'consistency_check', label: '一致性检查' },
                { value: 'risk_assessment', label: '风险评估' },
              ]}
            />
          </Form.Item>
          <Form.Item name="document_ids" label="关联文档" rules={[{ required: true, message: '请选择至少一个已处理文档' }]}>
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              options={documents.map((doc) => ({ value: doc.id, label: doc.filename }))}
              placeholder="选择已处理完成的文档"
            />
          </Form.Item>
        </Form>
      </Modal>

      <Table columns={columns} dataSource={tasks} loading={loading} rowKey="id" pagination={{ pageSize: 10 }} />
    </div>
  );
};

export default AuditTasksPage;
