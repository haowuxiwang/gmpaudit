import React, { useEffect, useState } from 'react';
import { Button, Card, Empty, Modal, Space, Spin, Table, Tag, Typography, message } from 'antd';
import { DownloadOutlined, FileTextOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { useSearchParams } from 'react-router-dom';

import { reportApi } from '../services/api';
import type { Report } from '../types/api';

const { Title, Paragraph, Text } = Typography;

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
      message.error('加载报告失败');
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
      message.error('加载报告详情失败');
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
    anchor.download = `${detailContent.title || '审计报告'}.md`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
    message.success('导出成功');
  };

  const columns = [
    {
      title: '报告',
      dataIndex: 'title',
      key: 'title',
      render: (value: string, record: Report) => (
        <Space direction="vertical" size={0}>
          <Text strong>{value}</Text>
          <Text type="secondary">{record.report_metadata?.report_source || '未知来源'}</Text>
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'report_type',
      key: 'report_type',
      width: 140,
      render: (type: string) => <Tag color="blue">{REPORT_TYPE_LABELS[type] || type}</Tag>,
    },
    {
      title: '模式',
      key: 'mode',
      width: 180,
      render: (_: unknown, record: Report) => record.report_metadata?.report_mode || '未知',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
      render: (value: string) => (value ? new Date(value).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: Report) => (
        <Button type="link" icon={<FileTextOutlined />} onClick={() => void handleView(record)}>
          查看
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
          borderRadius: 12,
          background: '#FFFFFF',
          borderLeft: '4px solid #D97757',
        }}
        styles={{ body: { padding: 28 } }}
      >
        <Title level={2} style={{ color: '#1A1A1A', marginTop: 0 }}>
          审计报告
        </Title>
        <Paragraph style={{ color: '#6B7280', fontSize: 16, marginBottom: 0 }}>
          查看审计报告，追溯报告来源和生成方式
        </Paragraph>
      </Card>

      <Card bordered={false} style={{ borderRadius: 12 }}>
        <Title level={4}>报告列表</Title>
        <Table
          columns={columns}
          dataSource={reports}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="暂无报告" /> }}
        />
      </Card>

      <Modal
        title={detailContent?.title || '报告详情'}
        open={detailOpen}
        onCancel={() => {
          setDetailOpen(false);
          setDetailContent(null);
        }}
        width={900}
        footer={
          <Space>
            <Button onClick={() => setDetailOpen(false)}>关闭</Button>
            <Button type="primary" icon={<DownloadOutlined />} onClick={handleExport} disabled={!detailContent?.content}>
              导出
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
              <Tag>{detailContent.report_metadata?.report_source || '未知来源'}</Tag>
              <Tag>{detailContent.report_metadata?.report_mode || '未知模式'}</Tag>
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
