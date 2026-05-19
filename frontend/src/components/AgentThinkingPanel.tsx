import React, { useEffect, useRef, useState } from 'react';
import { Card, Collapse, Tag, Typography } from 'antd';
import type { AgentThinkingEvent } from '../types/api';

const { Text } = Typography;

const NODE_LABELS: Record<string, string> = {
  parse_doc: '解析',
  regulation_expert: '法规',
  risk_assessor: '风险',
  report_writer: '报告',
  supervisor: '监管',
};

const NODE_COLORS: Record<string, string> = {
  parse_doc: '#1890ff',
  regulation_expert: '#52c41a',
  risk_assessor: '#faad14',
  report_writer: '#722ed1',
  supervisor: '#13c2c2',
};

interface AgentThinkingPanelProps {
  thinkingEvents: AgentThinkingEvent[];
  currentStage: string;
  isRunning?: boolean;
}

const AgentThinkingPanel: React.FC<AgentThinkingPanelProps> = ({
  thinkingEvents,
  currentStage,
  isRunning = false,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [collapsed, setCollapsed] = useState(false);

  // Auto-collapse when task finishes
  useEffect(() => {
    if (!isRunning && thinkingEvents.length > 0) {
      setCollapsed(true);
    }
  }, [isRunning, thinkingEvents.length]);

  useEffect(() => {
    if (scrollRef.current && !collapsed) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thinkingEvents, collapsed]);

  if (thinkingEvents.length === 0) {
    return (
      <Card
        size="small"
        title="Agent 思考过程"
        style={{ marginTop: 16 }}
        styles={{ body: { padding: '12px 16px' } }}
      >
        <Text type="secondary">
          {currentStage === 'pending' ? '等待开始...' : `当前阶段: ${NODE_LABELS[currentStage] || currentStage}`}
        </Text>
      </Card>
    );
  }

  return (
    <>
      <style>{`
        @keyframes thinking-fade-in {
          from { opacity: 0; transform: translateX(-4px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
      <Collapse
        activeKey={collapsed ? [] : ['thinking']}
        onChange={(keys) => setCollapsed(!keys.includes('thinking'))}
        style={{ marginTop: 16 }}
        items={[{
          key: 'thinking',
          label: (
            <span>
              Agent 思考过程
              <Tag style={{ marginLeft: 8 }}>{thinkingEvents.length}</Tag>
            </span>
          ),
          children: (
            <div
              ref={scrollRef}
              style={{
                maxHeight: 300,
                overflowY: 'auto',
                fontFamily: 'monospace',
                fontSize: 12,
                lineHeight: 1.6,
              }}
            >
              {thinkingEvents.map((event, index) => {
                const nodeLabel = NODE_LABELS[event.node] || event.node;
                const nodeColor = NODE_COLORS[event.node] || '#666';
                const isStarted = event.status === 'started';
                const isLast = index === thinkingEvents.length - 1;

                return (
                  <div
                    key={index}
                    style={{
                      marginBottom: 4,
                      display: 'flex',
                      gap: 8,
                      alignItems: 'flex-start',
                      animation: isLast ? 'thinking-fade-in 0.3s ease-out' : undefined,
                    }}
                  >
                    <Tag color={nodeColor} style={{ margin: 0, flexShrink: 0 }}>
                      {nodeLabel}
                    </Tag>
                    <Text
                      type={isStarted ? 'secondary' : undefined}
                      style={{ fontSize: 12, wordBreak: 'break-word' }}
                    >
                      {isStarted ? '...' : event.message}
                    </Text>
                  </div>
                );
              })}
            </div>
          ),
        }]}
      />
    </>
  );
};

export default AgentThinkingPanel;
