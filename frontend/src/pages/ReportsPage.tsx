import React, { useEffect, useState } from 'react';
import { Button, Card, Empty, Modal, Space, Spin, Table, Tag, Typography, message } from 'antd';
import { DownloadOutlined, FileTextOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { useSearchParams } from 'react-router-dom';

import { reportApi } from '../services/api';
import type { Report } from '../types/api';

const { Title, Paragraph, Text } = Typography;

const REPORT_TYPE_LABELS: Record<string, string> = {
  full_report: 'Full report',
  summary: 'Summary',
  audit_report: 'Audit report',
};

const ReportsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const taskId = searchParams.get('task_id') ? Number(searchParams.get('task_id')) : undefined;
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailContent, setDetailContent] = useState<Report | null>(null);

  useEffect(() => {
    void loadReports();
  }, [taskId]);

  const loadReports = async () => {
    try {
      setLoading(true);
      const result = await reportApi.list(taskId);
      setReports(result?.items || []);
    } catch {
      message.error('Failed to load reports');
    } finally {
      setLoading(false);
    }
  };

  const handleView = async (record: Report) => {
    try {
      setDetailLoading(true);
      setDetailOpen(true);
      const result = await reportApi.get(record.id);
      setDetailContent(result);
    } catch {
      message.error('Failed to load report details');
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleExport = () => {
    if (!detailContent?.content) return;
    const blob = new Blob([detailContent.content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${detailContent.title || 'report'}.md`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
    message.success('Markdown exported');
  };

  const columns = [
    {
      title: 'Report',
      dataIndex: 'title',
      key: 'title',
      render: (value: string, record: Report) => (
        <Space direction="vertical" size={0}>
          <Text strong>{value}</Text>
          <Text type="secondary">{record.report_metadata?.report_source || 'unknown source'}</Text>
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'report_type',
      key: 'report_type',
      width: 140,
      render: (type: string) => <Tag color="blue">{REPORT_TYPE_LABELS[type] || type}</Tag>,
    },
    {
      title: 'Mode',
      key: 'mode',
      width: 180,
      render: (_: unknown, record: Report) => record.report_metadata?.report_mode || 'n/a',
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
      render: (value: string) => (value ? new Date(value).toLocaleString() : '-'),
    },
    {
      title: 'Action',
      key: 'action',
      width: 120,
      render: (_: unknown, record: Report) => (
        <Button type="link" icon={<FileTextOutlined />} onClick={() => void handleView(record)}>
          Open
        </Button>
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
          background: 'linear-gradient(135deg, #1f2937 0%, #7c3aed 100%)',
          color: '#fff',
        }}
        bodyStyle={{ padding: 28 }}
      >
        <Title level={2} style={{ color: '#fff', marginTop: 0 }}>
          Reports with provenance
        </Title>
        <Paragraph style={{ color: 'rgba(255,255,255,0.82)', fontSize: 16, marginBottom: 0 }}>
          Review not only the report content, but also whether it came from the agent report writer or a backend regeneration path.
        </Paragraph>
      </Card>

      <Card bordered={false} style={{ borderRadius: 20 }}>
        <Title level={4}>Report library</Title>
        <Table
          columns={columns}
          dataSource={reports}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="No reports yet" /> }}
        />
      </Card>

      <Modal
        title={detailContent?.title || 'Report details'}
        open={detailOpen}
        onCancel={() => {
          setDetailOpen(false);
          setDetailContent(null);
        }}
        width={900}
        footer={
          <Space>
            <Button onClick={() => setDetailOpen(false)}>Close</Button>
            <Button type="primary" icon={<DownloadOutlined />} onClick={handleExport} disabled={!detailContent?.content}>
              Export Markdown
            </Button>
          </Space>
        }
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin />
          </div>
        ) : detailContent ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Space wrap>
              <Tag color="blue">{detailContent.report_type}</Tag>
              <Tag>{detailContent.report_metadata?.report_source || 'unknown source'}</Tag>
              <Tag>{detailContent.report_metadata?.report_mode || 'unknown mode'}</Tag>
            </Space>
            <div style={{ maxHeight: '60vh', overflow: 'auto' }}>
              <ReactMarkdown>{detailContent.content || ''}</ReactMarkdown>
            </div>
          </Space>
        ) : null}
      </Modal>
    </div>
  );
};

export default ReportsPage;
