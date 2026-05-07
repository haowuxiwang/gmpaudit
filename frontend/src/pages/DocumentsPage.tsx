import React, { useState, useEffect } from 'react';
import { Typography, Upload, Button, Table, message, Space, Tag } from 'antd';
import { UploadOutlined, InboxOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { documentApi } from '../services/api';

const { Title } = Typography;

const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [fileList, setFileList] = useState<any[]>([]);

  useEffect(() => { loadDocuments(); }, []);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const result: any = await documentApi.list();
      setDocuments(result || []);
    } catch (error) {
      message.error('加载文档列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请先选择文件');
      return;
    }
    try {
      const files = fileList.map((f: any) => f.originFileObj);
      await documentApi.uploadBatch(files);
      message.success(`成功上传 ${files.length} 个文件`);
      setFileList([]);
      loadDocuments();
    } catch (error) {
      message.error('上传失败');
    }
  };

  const handleProcess = async (id: number) => {
    try {
      await documentApi.process(id);
      message.success('处理完成');
      loadDocuments();
    } catch (error) {
      message.error('处理失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await documentApi.delete(id);
      message.success('删除成功');
      loadDocuments();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: '文件名', dataIndex: 'filename', key: 'filename', ellipsis: true },
    { title: '类型', dataIndex: 'file_type', key: 'file_type', width: 80, render: (type: string) => <Tag color={type === 'pdf' ? 'red' : type === 'word' ? 'blue' : 'green'}>{type.toUpperCase()}</Tag> },
    { title: '状态', dataIndex: 'process_status', key: 'process_status', width: 100, render: (status: string) => <Tag color={status === 'processed' ? 'success' : status === 'processing' ? 'processing' : 'default'}>{status}</Tag> },
    { title: '操作', key: 'action', width: 200, render: (_: any, record: any) => (
      <Space>
        {record.process_status === 'uploaded' && <Button type="link" icon={<PlayCircleOutlined />} onClick={() => handleProcess(record.id)}>处理</Button>}
        <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>删除</Button>
      </Space>
    )},
  ];

  return (
    <div>
      <Title level={4}>文档管理</Title>
      <div style={{ marginBottom: 16 }}>
        <Upload.Dragger
          multiple
          fileList={fileList}
          beforeUpload={(file) => { setFileList((prev) => [...prev, file]); return false; }}
          onRemove={(file) => setFileList((prev) => prev.filter((f) => f.uid !== file.uid))}
          accept=".pdf,.docx,.doc,.jpg,.jpeg,.png"
          style={{ marginBottom: 16 }}
        >
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">支持 PDF、Word、图片格式</p>
        </Upload.Dragger>
        <Button type="primary" icon={<UploadOutlined />} onClick={handleUpload} disabled={fileList.length === 0}>
          开始上传 ({fileList.length} 个文件)
        </Button>
      </div>
      <Table columns={columns} dataSource={documents} loading={loading} rowKey="id" pagination={{ pageSize: 10 }} />
    </div>
  );
};

export default DocumentsPage;
