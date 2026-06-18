import React, { useState } from 'react';
import { Card, Tag, Space, Typography, Button, Collapse, message } from 'antd';
import { BranchesOutlined, FileSearchOutlined, BulbOutlined, BookOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { Finding } from '../types/api';
import { SEVERITY_COLORS } from '../constants/audit';
import { THEME } from '../constants/theme';
import { auditApi } from '../services/api';
import DocumentPreview from './DocumentPreview';

const { Text, Paragraph } = Typography;

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  pending: { color: 'default', label: '待审' },
  approved: { color: 'success', label: '已通过' },
  rejected: { color: 'error', label: '已驳回' },
};

interface FindingDetailCardProps {
  finding: Finding;
  onGraphTrace?: (title: string, taskId?: number) => void;
  taskId?: number;
  style?: React.CSSProperties;
  onStatusChange?: () => void;
}

const FindingDetailCard: React.FC<FindingDetailCardProps> = ({ finding, onGraphTrace, taskId, style, onStatusChange }) => {
  const [docPreviewVisible, setDocPreviewVisible] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  const handleApprove = async () => {
    setReviewing(true);
    try {
      await auditApi.approveFinding(finding.id);
      message.success('已通过');
      onStatusChange?.();
    } catch {
      message.error('操作失败');
    } finally {
      setReviewing(false);
    }
  };

  const handleReject = async () => {
    setReviewing(true);
    try {
      await auditApi.rejectFinding(finding.id);
      message.success('已驳回');
      onStatusChange?.();
    } catch {
      message.error('操作失败');
    } finally {
      setReviewing(false);
    }
  };

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
          {finding.status && finding.status !== 'pending' && (
            <Tag color={STATUS_MAP[finding.status]?.color || 'default'} style={{ margin: 0, borderRadius: 4 }}>
              {STATUS_MAP[finding.status]?.label || finding.status}
            </Tag>
          )}
        </Space>

        {/* Description */}
        <Paragraph style={{ margin: 0, fontSize: 13, color: THEME.textSecondary }}>
          {finding.description || '暂无描述'}
        </Paragraph>

        {/* Evidence */}
        {finding.evidence && (
          <div style={{ borderLeft: `3px solid ${THEME.border}`, paddingLeft: 12, marginLeft: 4 }}>
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
            <BookOutlined style={{ color: THEME.info }} />
            <Text type="secondary" style={{ fontSize: 12 }}>法规引用：</Text>
            <Text style={{ fontSize: 12, color: THEME.info }}>{finding.regulation_ref}</Text>
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
                  <BulbOutlined style={{ color: THEME.warning }} />
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
          {finding.status !== 'approved' && finding.status !== 'rejected' && (
            <>
              <Button
                type="link"
                size="small"
                icon={<CheckOutlined />}
                loading={reviewing}
                onClick={handleApprove}
                style={{ color: THEME.success }}
              >
                通过
              </Button>
              <Button
                type="link"
                size="small"
                icon={<CloseOutlined />}
                loading={reviewing}
                onClick={handleReject}
                style={{ color: THEME.error }}
              >
                驳回
              </Button>
            </>
          )}
        </Space>
      </Space>

      {/* Document Preview Modal */}
      {finding.document_id && (
        <DocumentPreview
          documentId={finding.document_id}
          highlightText={finding.evidence || finding.title}
          location={finding.location}
          visible={docPreviewVisible}
          onClose={() => setDocPreviewVisible(false)}
        />
      )}
    </Card>
  );
};

export default FindingDetailCard;
