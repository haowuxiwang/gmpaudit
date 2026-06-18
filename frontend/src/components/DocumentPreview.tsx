import React, { useState, useEffect, useRef } from 'react';
import { Modal, Input, Spin, message, Typography } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { documentApi } from '../services/api';
import { THEME } from '../constants/theme';

const { Text } = Typography;

interface DocumentPreviewProps {
  documentId: number;
  highlightText?: string;
  location?: string;
  visible: boolean;
  onClose: () => void;
}

const CONTEXT_WINDOW = 500; // chars before/after highlight

/**
 * Normalize text for fuzzy matching: remove whitespace, punctuation, newlines.
 */
function normalizeForMatch(text: string): string {
  return text.replace(/[\s\n\r\t.,;:!?，。；：！？、\-()[]{}「」『』""''"]+/g, '');
}

/**
 * Extract a window of text around the highlighted portion.
 * Tries exact match first, then fuzzy match (ignoring whitespace/punctuation).
 */
function getWindowAroundHighlight(
  text: string,
  highlight: string,
): { before: string; match: string; after: string } | null {
  if (!highlight || !text) return null;

  // Try exact match
  let idx = text.toLowerCase().indexOf(highlight.toLowerCase());
  if (idx >= 0) {
    const start = Math.max(0, idx - CONTEXT_WINDOW);
    const end = Math.min(text.length, idx + highlight.length + CONTEXT_WINDOW);
    return {
      before: start > 0 ? '...' + text.slice(start, idx) : text.slice(0, idx),
      match: text.slice(idx, idx + highlight.length),
      after: text.slice(idx + highlight.length, end) + (end < text.length ? '...' : ''),
    };
  }

  // Try fuzzy match: normalize both and find position
  const normalizedHighlight = normalizeForMatch(highlight);
  if (normalizedHighlight.length < 5) return null; // too short for fuzzy

  // Sliding window: find where the normalized highlight appears in normalized text
  const normalizedText = normalizeForMatch(text);
  const fuzzyIdx = normalizedText.indexOf(normalizedHighlight);
  if (fuzzyIdx < 0) {
    // Try partial match with decreasing lengths for better Chinese text matching
    const tryLengths = [
      Math.ceil(normalizedHighlight.length * 0.7),
      Math.ceil(normalizedHighlight.length * 0.5),
      Math.min(20, normalizedHighlight.length),
    ];
    let partialIdx = -1;
    for (const len of tryLengths) {
      const partial = normalizedHighlight.slice(0, len);
      partialIdx = normalizedText.indexOf(partial);
      if (partialIdx >= 0) break;
    }
    if (partialIdx < 0) return null;

    // Map back to original text position (approximate)
    // Count non-whitespace chars up to partialIdx in normalized text
    let charCount = 0;
    let origIdx = 0;
    for (let i = 0; i < text.length && charCount < partialIdx; i++) {
      if (!/[\s\n\r\t.,;:!?，。；：！？、\-()[]{}「」『』""''"]/.test(text[i])) {
        charCount++;
      }
      origIdx = i;
    }

    const start = Math.max(0, origIdx - CONTEXT_WINDOW);
    const end = Math.min(text.length, origIdx + highlight.length + CONTEXT_WINDOW);
    return {
      before: start > 0 ? '...' + text.slice(start, origIdx) : text.slice(0, origIdx),
      match: text.slice(origIdx, Math.min(origIdx + highlight.length, text.length)),
      after: text.slice(Math.min(origIdx + highlight.length, text.length), end) + (end < text.length ? '...' : ''),
    };
  }

  // Map fuzzy index back to original text position
  let charCount = 0;
  let origIdx = 0;
  for (let i = 0; i < text.length && charCount < fuzzyIdx; i++) {
    if (!/[\s\n\r\t.,;:!?，。；：！？、\-()[]{}「」『』""''"]/.test(text[i])) {
      charCount++;
    }
    origIdx = i;
  }

  const start = Math.max(0, origIdx - CONTEXT_WINDOW);
  const end = Math.min(text.length, origIdx + highlight.length + CONTEXT_WINDOW);
  return {
    before: start > 0 ? '...' + text.slice(start, origIdx) : text.slice(0, origIdx),
    match: text.slice(origIdx, Math.min(origIdx + highlight.length, text.length)),
    after: text.slice(Math.min(origIdx + highlight.length, text.length), end) + (end < text.length ? '...' : ''),
  };
}

const DocumentPreview: React.FC<DocumentPreviewProps> = ({ documentId, highlightText, location, visible, onClose }) => {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState(highlightText || '');
  const [showFull, setShowFull] = useState(false);
  const highlightRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!visible) return;
    setShowFull(false); // Reset to focused view on open

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

  // Auto-scroll to highlight when content loads
  useEffect(() => {
    if (!loading && highlightRef.current) {
      setTimeout(() => {
        highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    }
  }, [loading, content, searchText]);

  const highlightContent = (text: string, highlight: string) => {
    if (!highlight || !text) return text;

    const parts = text.split(new RegExp(`(${highlight.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'));
    return parts.map((part, index) =>
      part.toLowerCase() === highlight.toLowerCase() ? (
        <mark key={index} ref={highlightRef} style={{ backgroundColor: THEME.bgWarning, padding: '0 2px', borderRadius: 2 }}>
          {part}
        </mark>
      ) : part
    );
  };

  // Check if we should show focused view
  // Try highlightText first, then fall back to location (section path)
  const hasHighlightText = Boolean(searchText?.trim());
  let windowData = hasHighlightText ? getWindowAroundHighlight(content, searchText) : null;
  let usedLocation = false;
  if (!windowData && location?.trim()) {
    // Try to find the section in the document
    windowData = getWindowAroundHighlight(content, location);
    if (windowData) usedLocation = true;
  }
  const hasHighlight = Boolean(windowData);

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
      ) : hasHighlight && !showFull && windowData ? (
        <>
          {/* Focused view: only the relevant section */}
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {usedLocation ? `定位到章节: ${location}` : '显示相关段落'}
            </Text>
            <Typography.Link onClick={() => setShowFull(true)} style={{ fontSize: 12 }}>
              查看完整文档
            </Typography.Link>
          </div>
          <div
            style={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontSize: 13,
              lineHeight: 1.8,
              maxHeight: '50vh',
              overflow: 'auto',
              padding: 16,
              background: THEME.bgLayout,
              borderRadius: 8,
              border: `1px solid ${THEME.borderLight}`,
            }}
          >
            {windowData.before}
            <mark style={{ backgroundColor: THEME.bgWarning, padding: '2px 4px', borderRadius: 2, fontWeight: 500 }}>
              {windowData.match}
            </mark>
            {windowData.after}
          </div>
        </>
      ) : (
        <>
          {/* Full document view (or no highlight) */}
          {hasHighlightText && !hasHighlight && (
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                未在文档中找到匹配文本，显示完整文档
              </Text>
            </div>
          )}
          <pre
            style={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontSize: 13,
              lineHeight: 1.6,
              maxHeight: '50vh',
              overflow: 'auto',
              padding: 16,
              background: THEME.bgLayout,
              borderRadius: 8,
              border: `1px solid ${THEME.borderLight}`,
            }}
          >
            {highlightContent(content, searchText)}
          </pre>
        </>
      )}
    </Modal>
  );
};

export default DocumentPreview;
