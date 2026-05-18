import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Button,
  Card,
  Modal,
  Radio,
  Space,
  Steps,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import { DeleteOutlined, InboxOutlined, RobotOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { useNavigate } from 'react-router-dom';

import { agentAuditApi, documentApi } from '../services/api';
import type { Document } from '../types/api';

const { Title, Paragraph, Text } = Typography;

const STATUS_COLORS: Record<string, string> = {
  uploaded: 'default',
  processing: 'processing',
  processed: 'success',
  failed: 'error',
};

const STATUS_LABELS: Record<string, string> = {
  uploaded: '已上传',
  processing: '处理中',
  processed: '已处理',
  failed: '处理失败',
};

const AUDIT_TYPE_OPTIONS = [
  { label: '偏差分析', value: 'deviation' },
  { label: 'SOP 合规', value: 'sop' },
  { label: '变更控制', value: 'change_control' },
];

const DocumentsPage: React.FC = () => {
  const navigate = useNavigate();
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [auditModalOpen, setAuditModalOpen] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [auditType, setAuditType] = useState<'deviation' | 'sop' | 'change_control'>('deviation');

  const loadDocuments = useCallback(async (nextPage = page) => {
    try {
      const result = await documentApi.list(nextPage, 10);
      setDocuments(result?.items || []);
      setTotal(result?.total || 0);
    } catch {
      message.error('加载文档失败');
    }
  }, [page]);

  useEffect(() => {
    setLoading(true);
    loadDocuments().finally(() => setLoading(false));
  }, [loadDocuments]);

  useEffect(() => {
    const hasPending = documents.some((doc) => ['uploaded', 'processing'].includes(doc.process_status));
    if (hasPending && !pollRef.current) {
      pollRef.current = setInterval(() => {
        void loadDocuments();
      }, 3000);
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

  const customRequest: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;
    setUploading(true);
    try {
      const result = await documentApi.uploadBatch([file as File]);
      onSuccess?.(result);
      message.success('上传成功，正在处理中');
      void loadDocuments();
    } catch (error) {
      onError?.(error as Error);
      message.error('上传失败');
    } finally {
      setUploading(false);
    }
  };

  const openAuditModal = (id: number) => {
    setSelectedDocId(id);
    setAuditType('deviation');
    setAuditModalOpen(true);
  };

  const handleAgentAuditConfirm = async () => {
    if (!selectedDocId) return;
    try {
      const result = await agentAuditApi.run({
        document_id: selectedDocId,
        audit_type: auditType,
      });
      message.success(`审计任务已创建：#${result.task_id}`);
      setAuditModalOpen(false);
      navigate(`/audit?task_id=${result.task_id}`);
    } catch {
      message.error('创建审计任务失败');
    }
  };

  const handleDelete = (id: number) => {
    Modal.confirm({
      title: '删除文档',
      content: '删除后将从工作区移除该文档。',
      okText: '删除',
      okType: 'danger',
      onOk: async () => {
        try {
          await documentApi.delete(id);
          message.success('文档已删除');
          void loadDocuments();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const processedCount = documents.filter((doc) => doc.process_status === 'processed').length;
  const pendingCount = documents.filter((doc) => ['uploaded', 'processing'].includes(doc.process_status)).length;

  const columns = [
    {
      title: '文档',
      dataIndex: 'filename',
      key: 'filename',
      render: (value: string, record: Document) => (
        <Space direction="vertical" size={0}>
          <Text strong>{value}</Text>
          <Text type="secondary">{record.file_type.toUpperCase()}</Text>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'process_status',
      key: 'process_status',
      width: 140,
      render: (status: string) => <Tag color={STATUS_COLORS[status] || 'default'}>{STATUS_LABELS[status] || status}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      render: (_: unknown, record: Document) => (
        <Space>
          {record.process_status === 'processed' && (
            <Button type="primary" size="small" icon={<RobotOutlined />} onClick={() => openAuditModal(record.id)}>
              开始审计
            </Button>
          )}
          <Button type="link" danger size="small" icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>
            删除
          </Button>
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
          background: '#FFFFFF',
          borderLeft: '4px solid #D97757',
        }}
        styles={{ body: { padding: 28 } }}
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Tag color="#D97757" style={{ borderRadius: 999, alignSelf: 'flex-start' }}>
            文档管理
          </Tag>
          <Title level={2} style={{ color: '#1A1A1A', margin: 0 }}>
            上传文档，系统自动解析后用于审计分析
          </Title>
          <Paragraph style={{ color: '#6B7280', fontSize: 16, marginBottom: 0 }}>
            上传原始文档，等待解析完成后即可提交审计
          </Paragraph>
        </Space>
      </Card>

      {documents.length > 0 && (
        <Card bordered={false} style={{ marginBottom: 16, borderRadius: 12 }}>
          <Steps
            current={processedCount > 0 ? 2 : pendingCount > 0 ? 1 : 0}
            items={[
              { title: '上传文档' },
              { title: '处理中' },
              { title: '待审计' },
            ]}
          />
        </Card>
      )}

      <Upload.Dragger
        multiple
        customRequest={customRequest}
        showUploadList={false}
        accept=".pdf,.docx,.doc,.txt,.jpg,.jpeg,.png"
        disabled={uploading}
        style={{ marginBottom: 16, borderRadius: 12, overflow: 'hidden' }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">{uploading ? '上传中...' : '点击或拖拽文件到此处'}</p>
        <p className="ant-upload-hint">支持 PDF、Word、纯文本和图片格式</p>
      </Upload.Dragger>

      {pendingCount > 0 && (
        <Card size="small" style={{ marginBottom: 16, borderRadius: 8, background: '#FFFBEB' }}>
          <Text>{pendingCount} 个文档正在处理中</Text>
        </Card>
      )}

      <Card bordered={false} style={{ borderRadius: 12 }}>
        <Title level={4}>文档列表</Title>
        <Table
          columns={columns}
          dataSource={documents}
          loading={loading}
          rowKey="id"
          pagination={{
            current: page,
            pageSize: 10,
            total,
            onChange: (nextPage) => {
              setPage(nextPage);
              void loadDocuments(nextPage);
            },
          }}
        />
      </Card>

      <Modal
        title="启动审计"
        open={auditModalOpen}
        onCancel={() => setAuditModalOpen(false)}
        onOk={() => void handleAgentAuditConfirm()}
        okText="提交"
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Paragraph style={{ marginBottom: 0 }}>
            选择审计类型，系统将根据类型匹配相应的法规和风险评估流程
          </Paragraph>
          <Radio.Group
            value={auditType}
            onChange={(event) => setAuditType(event.target.value)}
            style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
          >
            {AUDIT_TYPE_OPTIONS.map((option) => (
              <Radio key={option.value} value={option.value}>
                {option.label}
              </Radio>
            ))}
          </Radio.Group>
        </Space>
      </Modal>
    </div>
  );
};

export default DocumentsPage;
