import React, { useState, useEffect } from 'react';
import { Typography, Table, Button, Tag, message, Modal, Spin } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { reportApi } from '../services/api';

const { Title } = Typography;

const ReportsPage: React.FC = () => {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailContent, setDetailContent] = useState<{ title: string; content: string } | null>(null);

  useEffect(() => { loadReports(); }, []);

  const loadReports = async () => {
    try {
      setLoading(true);
      const result: any = await reportApi.list();
      setReports(result || []);
    } catch (error) {
      message.error('加载报告列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleView = async (record: any) => {
    try {
      setDetailLoading(true);
      setDetailOpen(true);
      const result: any = await reportApi.get(record.id);
      setDetailContent({ title: result.title, content: result.content });
    } catch (error) {
      message.error('加载报告详情失败');
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const columns = [
    { title: '报告标题', dataIndex: 'title', key: 'title' },
    { title: '类型', dataIndex: 'report_type', key: 'report_type', width: 120, render: (type: string) => <Tag color="blue">{type}</Tag> },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180, render: (time: string) => new Date(time).toLocaleString() },
    { title: '操作', key: 'action', width: 100, render: (_: any, record: any) => (
      <Button type="link" icon={<FileTextOutlined />} onClick={() => handleView(record)}>查看</Button>
    )},
  ];

  return (
    <div>
      <Title level={4}>审计报告</Title>
      <Table columns={columns} dataSource={reports} loading={loading} rowKey="id" pagination={{ pageSize: 10 }} />
      <Modal
        title={detailContent?.title || '报告详情'}
        open={detailOpen}
        onCancel={() => { setDetailOpen(false); setDetailContent(null); }}
        footer={null}
        width={800}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : detailContent ? (
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', maxHeight: '60vh', overflow: 'auto' }}>
            {detailContent.content}
          </pre>
        ) : null}
      </Modal>
    </div>
  );
};

export default ReportsPage;
