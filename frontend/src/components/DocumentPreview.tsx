import React, { useState, useEffect } from 'react';
import { Modal, Input, Spin, message } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { documentApi } from '../services/api';

interface DocumentPreviewProps {
  documentId: number;
  highlightText?: string;
  visible: boolean;
  onClose: () => void;
}

const DocumentPreview: React.FC<DocumentPreviewProps> = ({ documentId, highlightText, visible, onClose }) => {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState(highlightText || '');

  useEffect(() => {
    if (!visible) return;

    const loadDocument = async () => {
      setLoading(true);
      try {
        const doc = await documentApi.getById(documentId);
        setContent(doc.content_text || '文档内容为空');
      } catch (err) {
        message.error('加载文档失败');
        setContent('加载失败');
      } finally {
        setLoading(false);
      }
    };

    loadDocument();
  }, [documentId, visible]);

  useEffect(() => {
    if (highlightText) {
      setSearchText(highlightText);
    }
  }, [highlightText]);

  const highlightContent = (text: string, highlight: string) => {
    if (!highlight || !text) return text;

    const parts = text.split(new RegExp(`(${highlight.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'));
    return parts.map((part, index) =>
      part.toLowerCase() === highlight.toLowerCase() ? (
        <mark key={index} style={{ backgroundColor: '#fff3b0', padding: '0 2px', borderRadius: 2 }}>
          {part}
        </mark>
      ) : part
    );
  };

  return (
    <Modal
      title="文档预览"
      open={visible}
      onCancel={onClose}
      footer={null}
      width={800}
      styles={{ body: { maxHeight: '70vh', overflow: 'auto' } }}
    >
      <Input
        placeholder="搜索文本..."
        prefix={<SearchOutlined />}
        value={searchText}
        onChange={(e) => setSearchText(e.target.value)}
        style={{ marginBottom: 16 }}
        allowClear
      />

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : (
        <pre
          style={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontSize: 13,
            lineHeight: 1.6,
            maxHeight: '50vh',
            overflow: 'auto',
            padding: 16,
            background: '#fafafa',
            borderRadius: 8,
            border: '1px solid #f0f0f0',
          }}
        >
          {highlightContent(content, searchText)}
        </pre>
      )}
    </Modal>
  );
};

export default DocumentPreview;
