import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Modal, Radio, Space, Steps, Table, Tag, Typography, Upload, message } from 'antd';
import { DeleteOutlined, InboxOutlined, RobotOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { useNavigate } from 'react-router-dom';

import { agentAuditApi, documentApi } from '../services/api';
import type { Document } from '../types/api';

const { Title, Text } = Typography;

const STATUS_COLORS: Record<string, string> = {
  uploaded: 'default',
  processing: 'processing',
  processed: 'success',
  failed: 'error',
};

const STATUS_LABELS: Record<string, string> = {
  uploaded: '等待处理',
  processing: '处理中...',
  processed: '已就绪',
  failed: '处理失败',
};

const AUDIT_TYPE_OPTIONS = [
  { label: '偏差分析', value: 'deviation' },
  { label: 'SOP 合规', value: 'sop' },
  { label: '变更控制', value: 'change_control' },
];

const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [auditModalOpen, setAuditModalOpen] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [auditType, setAuditType] = useState<string>('deviation');
  const navigate = useNavigate();
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadDocuments = useCallback(async (p = page) => {
    try {
      const result = await documentApi.list(p, 10);
      setDocuments(result?.items || []);
      setTotal(result?.total || 0);
    } catch {
      // silent on poll
    }
  }, [page]);

  // Initial load
  useEffect(() => {
    setLoading(true);
    loadDocuments().finally(() => setLoading(false));
  }, [loadDocuments]);

  // Poll when there are uploading/processing/uploaded documents
  useEffect(() => {
    const hasPending = documents.some((d) =>
      d.process_status === 'uploaded' || d.process_status === 'processing'
    );
    if (hasPending && !pollRef.current) {
      pollRef.current = setInterval(() => { void loadDocuments(); }, 3000);
    } else if (!hasPending && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [documents, loadDocuments]);

  // Auto-upload on file drop/select
  const customRequest: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;
    setUploading(true);
    try {
      const result = await documentApi.uploadBatch([file as File]);
      onSuccess?.(result);
      message.success('上传成功，正在自动处理...');
      void loadDocuments();
    } catch (err) {
      onError?.(err as Error);
      message.error('上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleAgentAuditClick = (id: number) => {
    setSelectedDocId(id);
    setAuditType('deviation');
    setAuditModalOpen(true);
  };

  const handleAgentAuditConfirm = async () => {
    if (!selectedDocId) return;
    try {
      const result = await agentAuditApi.run({
        document_id: selectedDocId,
        audit_type: auditType as 'deviation' | 'sop' | 'change_control',
      });
      message.success(`Agent 审计已启动，任务 ID: ${result.task_id}`);
      setAuditModalOpen(false);
      navigate('/audit');
    } catch {
      message.error('启动 Agent 审计失败');
    }
  };

  const handleDelete = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，确定要删除该文档吗？',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await documentApi.delete(id);
          message.success('删除成功');
          void loadDocuments();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  // Workflow step: 0=upload, 1=processing, 2=ready
  const getStep = (status: string) => {
    if (status === 'processed') return 2;
    if (status === 'processing' || status === 'uploaded') return 1;
    return 0;
  };

  const columns = [
    { title: '文件名', dataIndex: 'filename', key: 'filename', ellipsis: true },
    {
      title: '类型',
      dataIndex: 'file_type',
      key: 'file_type',
      width: 80,
      render: (type: string) => <Tag color={type === 'pdf' ? 'red' : type === 'word' ? 'blue' : 'green'}>{type.toUpperCase()}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'process_status',
      key: 'process_status',
      width: 140,
      render: (status: string) => (
        <Space>
          {(status === 'processing' || status === 'uploaded') && <span className="ant-spin-dot ant-spin-dot-spin" style={{ fontSize: 12 }} />}
          <Tag color={STATUS_COLORS[status] || 'default'}>{STATUS_LABELS[status] || status}</Tag>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: Document) => (
        <Space>
          {record.process_status === 'processed' && (
            <Button type="primary" size="small" icon={<RobotOutlined />} onClick={() => handleAgentAuditClick(record.id)}>
              运行审计
            </Button>
          )}
          <Button type="link" danger size="small" icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  const processedCount = documents.filter((d) => d.process_status === 'processed').length;
  const pendingCount = documents.filter((d) => d.process_status === 'uploaded' || d.process_status === 'processing').length;

  return (
    <div>
      <Title level={4}>文档管理</Title>

      {/* Workflow indicator */}
      {documents.length > 0 && (
        <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f6ffed', borderRadius: 8, border: '1px solid #b7eb8f' }}>
          <Steps
            size="small"
            current={processedCount > 0 ? 2 : pendingCount > 0 ? 1 : 0}
            items={[
              { title: '上传文档' },
              { title: '自动处理中' },
              { title: '就绪，可运行审计' },
            ]}
          />
        </div>
      )}

      {/* Upload area */}
      <Upload.Dragger
        multiple
        customRequest={customRequest}
        showUploadList={false}
        accept=".pdf,.docx,.doc,.txt,.jpg,.jpeg,.png"
        disabled={uploading}
        style={{ marginBottom: 16 }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">{uploading ? '上传中...' : '点击或拖拽文档到此区域'}</p>
        <p className="ant-upload-hint">支持 PDF、Word、TXT 和图片格式，上传后自动处理</p>
      </Upload.Dragger>

      {/* Pending notice */}
      {pendingCount > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Text type="warning">有 {pendingCount} 个文档正在自动处理中，完成后即可运行审计...</Text>
        </div>
      )}

      <Table
        columns={columns}
        dataSource={documents}
        loading={loading}
        rowKey="id"
        pagination={{
          current: page,
          pageSize: 10,
          total,
          onChange: (p) => { setPage(p); void loadDocuments(p); },
          showTotal: (t) => `共 ${t} 个文档`,
        }}
      />

      {/* Audit type selection modal */}
      <Modal
        title="选择审计类型"
        open={auditModalOpen}
        onCancel={() => setAuditModalOpen(false)}
        onOk={() => void handleAgentAuditConfirm()}
        okText="开始审计"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <Text>请选择审计类型：</Text>
        </div>
        <Radio.Group
          value={auditType}
          onChange={(e) => setAuditType(e.target.value)}
          style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          {AUDIT_TYPE_OPTIONS.map((opt) => (
            <Radio key={opt.value} value={opt.value}>
              <div>
                <div style={{ fontWeight: 500 }}>{opt.label}</div>
                <div style={{ fontSize: 12, color: '#888' }}>
                  {opt.value === 'deviation' && '分析生产偏差，识别根本原因和纠正措施'}
                  {opt.value === 'sop' && '检查 SOP 文件的合规性和一致性'}
                  {opt.value === 'change_control' && '评估变更控制流程的完整性和合规性'}
                </div>
              </div>
            </Radio>
          ))}
        </Radio.Group>
      </Modal>
    </div>
  );
};

export default DocumentsPage;
