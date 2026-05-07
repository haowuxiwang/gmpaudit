import React, { useState, useEffect } from 'react';
import { Typography, Button, Table, Tag, Space, Modal, Form, Input, Select, message } from 'antd';
import { PlayCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { auditApi, documentApi } from '../services/api';

const { Title } = Typography;

const AuditTasksPage: React.FC = () => {
  const [tasks, setTasks] = useState<any[]>([]);
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => { loadTasks(); loadDocuments(); }, []);

  const loadTasks = async () => {
    try {
      setLoading(true);
      const result: any = await auditApi.listTasks();
      setTasks(result || []);
    } catch (error) {
      message.error('加载任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadDocuments = async () => {
    try {
      const result: any = await documentApi.list();
      setDocuments(result || []);
    } catch (error) {
      console.error('加载文档列表失败');
    }
  };

  const handleCreate = async (values: any) => {
    try {
      await auditApi.createTask(values);
      message.success('任务创建成功');
      setShowModal(false);
      form.resetFields();
      loadTasks();
    } catch (error) {
      message.error('任务创建失败');
    }
  };

  const handleRun = async (id: number) => {
    try {
      await auditApi.runTask(id);
      message.success('任务开始运行');
      loadTasks();
    } catch (error) {
      message.error('任务运行失败');
    }
  };

  const columns = [
    { title: '任务名称', dataIndex: 'task_name', key: 'task_name' },
    { title: '类型', dataIndex: 'task_type', key: 'task_type', width: 120, render: (type: string) => {
      const typeMap: Record<string, string> = { deviation_analysis: '偏差分析', sop_compliance: 'SOP合规', consistency_check: '一致性检查', risk_assessment: '风险评估' };
      return typeMap[type] || type;
    }},
    { title: '状态', dataIndex: 'status', key: 'status', width: 100, render: (status: string) => (
      <Tag color={status === 'completed' ? 'success' : status === 'running' ? 'processing' : status === 'failed' ? 'error' : 'default'}>{status}</Tag>
    )},
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180, render: (time: string) => new Date(time).toLocaleString() },
    { title: '操作', key: 'action', width: 150, render: (_: any, record: any) => (
      <Space>
        {record.status === 'pending' && <Button type="link" icon={<PlayCircleOutlined />} onClick={() => handleRun(record.id)}>运行</Button>}
      </Space>
    )},
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4}>审计任务</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowModal(true)}>创建任务</Button>
      </div>
      <Modal title="创建审计任务" open={showModal} onCancel={() => setShowModal(false)} onOk={() => form.submit()} width={600}>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="task_name" label="任务名称" rules={[{ required: true, message: '请输入任务名称' }]}>
            <Input placeholder="请输入任务名称" />
          </Form.Item>
          <Form.Item name="task_type" label="任务类型" rules={[{ required: true, message: '请选择任务类型' }]}>
            <Select placeholder="请选择任务类型" options={[
              { value: 'deviation_analysis', label: '偏差分析' },
              { value: 'sop_compliance', label: 'SOP合规检查' },
              { value: 'consistency_check', label: '一致性检查' },
              { value: 'risk_assessment', label: '风险评估' },
            ]} />
          </Form.Item>
          <Form.Item name="document_ids" label="选择文档" rules={[{ required: true, message: '请选择至少一个文档' }]}>
            <Select mode="multiple" placeholder="请选择文档" options={documents.map((d: any) => ({ value: d.id, label: d.filename }))} />
          </Form.Item>
        </Form>
      </Modal>
      <Table columns={columns} dataSource={tasks} loading={loading} rowKey="id" pagination={{ pageSize: 10 }} />
    </div>
  );
};

export default AuditTasksPage;
