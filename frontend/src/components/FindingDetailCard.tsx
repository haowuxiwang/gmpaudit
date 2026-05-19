import React, { useState } from 'react';
import { Card, Tag, Space, Typography, Button, Collapse } from 'antd';
import { BranchesOutlined, FileSearchOutlined, BulbOutlined, BookOutlined } from '@ant-design/icons';
import { Finding } from '../types/api';
import { SEVERITY_COLORS } from '../constants/audit';
import DocumentPreview from './DocumentPreview';

const { Text, Paragraph } = Typography;

interface FindingDetailCardProps {
  finding: Finding;
  onGraphTrace?: (title: string, taskId?: number) => void;
  taskId?: number;
  style?: React.CSSProperties;
}

const FindingDetailCard: React.FC<FindingDetailCardProps> = ({ finding, onGraphTrace, taskId, style }) => {
  const [docPreviewVisible, setDocPreviewVisible] = useState(false);

  return (
    <Card
      size="small"
      style={{ marginBottom: 8, borderRadius: 8, ...style }}
      styles={{ body: { padding: '12px 16px' } }}
    >
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        {/* Header */}
        <Space wrap size={8}>
          <Tag color={SEVERITY_COLORS[finding.severity] || 'default'} style={{ margin: 0, borderRadius: 4 }}>
            {finding.severity}
          </Tag>
          <Text strong style={{ fontSize: 14 }}>{finding.title}</Text>
          {finding.finding_type && (
            <Tag style={{ margin: 0, borderRadius: 4 }}>{finding.finding_type}</Tag>
          )}
        </Space>

        {/* Description */}
        <Paragraph style={{ margin: 0, fontSize: 13, color: '#666' }}>
          {finding.description || '暂无描述'}
        </Paragraph>

        {/* Evidence */}
        {finding.evidence && (
          <div style={{ borderLeft: '3px solid #d9d9d9', paddingLeft: 12, marginLeft: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>证据原文</Text>
            <Paragraph style={{ margin: '4px 0 0', fontSize: 13, fontStyle: 'italic' }}>
              {finding.evidence}
            </Paragraph>
          </div>
        )}

        {/* Location */}
        {finding.location && (
          <Space size={4}>
            <Text type="secondary" style={{ fontSize: 12 }}>位置：</Text>
            <Text style={{ fontSize: 12 }}>{finding.location}</Text>
          </Space>
        )}

        {/* Regulation Reference */}
        {finding.regulation_ref && (
          <Space size={4}>
            <BookOutlined style={{ color: '#1890ff' }} />
            <Text type="secondary" style={{ fontSize: 12 }}>法规引用：</Text>
            <Text style={{ fontSize: 12, color: '#1890ff' }}>{finding.regulation_ref}</Text>
          </Space>
        )}

        {/* Suggestion */}
        {finding.suggestion && (
          <Collapse
            size="small"
            items={[{
              key: 'suggestion',
              label: (
                <Space size={4}>
                  <BulbOutlined style={{ color: '#faad14' }} />
                  <Text style={{ fontSize: 12 }}>改进建议</Text>
                </Space>
              ),
              children: <Paragraph style={{ margin: 0, fontSize: 13 }}>{finding.suggestion}</Paragraph>
            }]}
          />
        )}

        {/* Actions */}
        <Space wrap size={8}>
          {finding.document_id && (
            <Button
              type="link"
              size="small"
              icon={<FileSearchOutlined />}
              onClick={() => setDocPreviewVisible(true)}
            >
              查看原文
            </Button>
          )}
          {onGraphTrace && (
            <Button
              type="link"
              size="small"
              icon={<BranchesOutlined />}
              onClick={() => onGraphTrace(finding.title, taskId)}
            >
              图谱溯源
            </Button>
          )}
        </Space>
      </Space>

      {/* Document Preview Modal */}
      {finding.document_id && (
        <DocumentPreview
          documentId={finding.document_id}
          highlightText={finding.evidence || finding.location}
          visible={docPreviewVisible}
          onClose={() => setDocPreviewVisible(false)}
        />
      )}
    </Card>
  );
};

export default FindingDetailCard;
