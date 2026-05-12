import React, { useEffect, useState } from 'react';
import { Typography, Table, Button, Tag, message, Modal, Spin, Empty, Space } from 'antd';
import { FileTextOutlined, DownloadOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { useSearchParams } from 'react-router-dom';
import { reportApi } from '../services/api';
import type { Report } from '../types/api';

const { Title } = Typography;

const REPORT_TYPE_LABELS: Record<string, string> = {
  full_report: '完整报告',
  summary: '摘要',
  audit_report: '审计报告',
};

const ReportsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const taskId = searchParams.get('task_id') ? Number(searchParams.get('task_id')) : undefined;
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailContent, setDetailContent] = useState<{ title: string; content: string } | null>(null);

  useEffect(() => { void loadReports(); }, [taskId]);

  const loadReports = async () => {
    try {
      setLoading(true);
      const result = await reportApi.list(taskId);
      setReports(result?.items || []);
    } catch {
      message.error('加载报告列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleView = async (record: Report) => {
    try {
      setDetailLoading(true);
      setDetailOpen(true);
      const result = await reportApi.get(record.id);
      setDetailContent({ title: result.title, content: result.content });
    } catch {
      message.error('加载报告详情失败');
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleExport = () => {
    if (!detailContent) return;
    const blob = new Blob([detailContent.content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${detailContent.title || 'report'}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    message.success('报告已导出');
  };

  const columns = [
    { title: '报告标题', dataIndex: 'title', key: 'title' },
    {
      title: '类型', dataIndex: 'report_type', key: 'report_type', width: 120,
      render: (type: string) => <Tag color="blue">{REPORT_TYPE_LABELS[type] || type}</Tag>,
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180,
      render: (time: string) => time ? new Date(time).toLocaleString() : '-',
    },
    {
      title: '操作', key: 'action', width: 100,
      render: (_: unknown, record: Report) => (
        <Button type="link" icon={<FileTextOutlined />} onClick={() => void handleView(record)}>查看</Button>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}>审计报告</Title>
      <Table
        columns={columns}
        dataSource={reports}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: <Empty description="暂无报告，完成审计任务后将自动生成" /> }}
      />
      <Modal
        title={detailContent?.title || '报告详情'}
        open={detailOpen}
        onCancel={() => { setDetailOpen(false); setDetailContent(null); }}
        width={800}
        footer={
          <Space>
            <Button onClick={() => { setDetailOpen(false); setDetailContent(null); }}>关闭</Button>
            <Button type="primary" icon={<DownloadOutlined />} onClick={handleExport}>导出 Markdown</Button>
          </Space>
        }
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : detailContent ? (
          <div style={{ maxHeight: '60vh', overflow: 'auto' }}>
            <ReactMarkdown>{detailContent.content}</ReactMarkdown>
          </div>
        ) : null}
      </Modal>
    </div>
  );
};

export default ReportsPage;
