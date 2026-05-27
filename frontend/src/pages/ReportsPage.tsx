import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Empty, Modal, Select, Space, Spin, Table, Tag, Typography, message } from 'antd';
import { DownloadOutlined, FileTextOutlined, PrinterOutlined, WarningOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { useSearchParams } from 'react-router-dom';

import { reportApi } from '../services/api';
import type { Report } from '../types/api';
import { THEME } from '../constants/theme';

const { Title, Paragraph, Text } = Typography;

const REPORT_TYPE_LABELS: Record<string, string> = {
  full_report: '完整报告',
  summary: '摘要',
  audit_report: '审计报告',
};

const REPORT_SOURCE_CONFIG: Record<string, { label: string; color: string }> = {
  llm: { label: 'AI 生成', color: 'green' },
  agent_report_writer: { label: 'AI 生成', color: 'green' },
  task_runner_aggregate: { label: '汇总报告', color: 'blue' },
  fallback: { label: '降级报告', color: 'orange' },
  partial_fallback: { label: '部分降级', color: 'orange' },
};

function isFallbackSource(source?: string): boolean {
  return source === 'fallback' || source === 'partial_fallback';
}

const ReportsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const taskId = searchParams.get('task_id') ? Number(searchParams.get('task_id')) : undefined;
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailContent, setDetailContent] = useState<Report | null>(null);
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);

  const loadReports = useCallback(async () => {
    try {
      setLoading(true);
      const result = await reportApi.list(taskId);
      setReports(result?.items || []);
    } catch {
      message.error('加载报告失败');
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

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

  const filteredReports = useMemo(() => {
    if (!typeFilter) return reports;
    return reports.filter((r) => r.report_type === typeFilter);
  }, [reports, typeFilter]);

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

  const handleExportPdf = async () => {
    if (!detailContent?.id) return;
    try {
      message.loading({ content: '正在生成 PDF...', key: 'pdf' });
      const blob = await reportApi.exportPdf(detailContent.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${detailContent.title || '审计报告'}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
      message.success({ content: 'PDF 导出成功', key: 'pdf' });
    } catch {
      message.error({ content: 'PDF 导出失败', key: 'pdf' });
    }
  };

  const columns = [
    {
      title: '报告',
      dataIndex: 'title',
      key: 'title',
      render: (value: string, record: Report) => {
        const source = record.report_metadata?.report_source;
        const sourceConfig = REPORT_SOURCE_CONFIG[source || ''];
        return (
          <Space direction="vertical" size={0}>
            <Space>
              <Text strong>{value}</Text>
              {isFallbackSource(source) && <Tag color="orange" icon={<WarningOutlined />}>降级</Tag>}
            </Space>
            <Text type="secondary">{sourceConfig?.label || source || '未知来源'}</Text>
          </Space>
        );
      },
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
      render: (value: string) => (value ? new Date(value).toLocaleString('zh-CN') : '-'),
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
          borderLeft: `4px solid ${THEME.primary}`,
        }}
        styles={{ body: { padding: 28 } }}
      >
        <Title level={2} style={{ color: THEME.text, marginTop: 0 }}>
          审计报告
        </Title>
        <Paragraph style={{ color: THEME.textSecondary, fontSize: 16, marginBottom: 0 }}>
          查看审计报告，追溯报告来源和生成方式
        </Paragraph>
      </Card>

      <Card bordered={false} style={{ borderRadius: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Title level={4} style={{ margin: 0 }}>报告列表</Title>
          <Select
            allowClear
            placeholder="按类型筛选"
            value={typeFilter}
            onChange={(value) => setTypeFilter(value)}
            style={{ width: 160 }}
            options={[
              { value: 'full_report', label: '完整报告' },
              { value: 'summary', label: '摘要' },
              { value: 'audit_report', label: '审计报告' },
            ]}
          />
        </div>
        <Table
          columns={columns}
          dataSource={filteredReports}
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
            <Button icon={<DownloadOutlined />} onClick={handleExport} disabled={!detailContent?.content}>
              导出 Markdown
            </Button>
            <Button
              type="primary"
              icon={<PrinterOutlined />}
              disabled={!detailContent?.id}
              onClick={() => void handleExportPdf()}
            >
              导出 PDF
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
            {isFallbackSource(detailContent.report_metadata?.report_source) && (
              <Alert
                message="降级报告"
                description="本报告由备用逻辑生成，未经 AI 模型分析。LLM 调用失败时系统自动生成基础报告以确保流程不中断。请检查 LLM 配置后重新运行审计。"
                type="warning"
                showIcon
                icon={<WarningOutlined />}
              />
            )}
            <Space wrap>
              <Tag color="blue">{REPORT_TYPE_LABELS[detailContent.report_type] || detailContent.report_type}</Tag>
              {(() => {
                const source = detailContent.report_metadata?.report_source;
                const sourceConfig = REPORT_SOURCE_CONFIG[source || ''];
                return <Tag color={sourceConfig?.color || 'default'}>{sourceConfig?.label || source || '未知来源'}</Tag>;
              })()}
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
