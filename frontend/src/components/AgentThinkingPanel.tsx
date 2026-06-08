import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Card, Collapse, Typography } from 'antd';
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  CloseCircleFilled,
  LoadingOutlined,
} from '@ant-design/icons';
import type { AgentThinkingEvent } from '../types/api';

const { Text } = Typography;

interface StepDef {
  key: string;
  label: string;
  icon: string;
}

const STEPS: StepDef[] = [
  { key: 'parsing', label: '解析文档', icon: '📄' },
  { key: 'regulation', label: '检索法规', icon: '📋' },
  { key: 'risk', label: '风险评估', icon: '⚠️' },
  { key: 'report', label: '生成报告', icon: '📊' },
];

const STAGE_ORDER = STEPS.map((s) => s.key);

function getStepStatus(
  stepKey: string,
  currentStage: string,
  lastActiveStage: string,
  isRunning: boolean,
): 'pending' | 'active' | 'done' | 'failed' {
  if (!isRunning && currentStage === 'completed') return 'done';
  if (!isRunning && currentStage === 'failed') {
    // Use lastActiveStage to determine which step failed
    const failedIdx = STAGE_ORDER.indexOf(lastActiveStage);
    const stepIdx = STAGE_ORDER.indexOf(stepKey);
    if (failedIdx < 0) return 'pending'; // unknown failure point
    if (stepIdx < failedIdx) return 'done';
    if (stepIdx === failedIdx) return 'failed';
    return 'pending';
  }
  const currentIdx = STAGE_ORDER.indexOf(currentStage);
  const stepIdx = STAGE_ORDER.indexOf(stepKey);
  if (stepIdx < currentIdx) return 'done';
  if (stepIdx === currentIdx) return isRunning ? 'active' : 'done';
  return 'pending';
}

function getLatestMessage(
  stepKey: string,
  events: AgentThinkingEvent[],
): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].stage === stepKey && events[i].status === 'completed') {
      return events[i].message;
    }
  }
  return null;
}

interface AgentThinkingPanelProps {
  thinkingEvents: AgentThinkingEvent[];
  currentStage: string;
  lastActiveStage?: string;
  isRunning?: boolean;
}

const AgentThinkingPanel: React.FC<AgentThinkingPanelProps> = ({
  thinkingEvents,
  currentStage,
  lastActiveStage = 'pending',
  isRunning = false,
}) => {
  const [collapsed, setCollapsed] = useState(false);

  // Auto-collapse when task finishes
  useEffect(() => {
    if (!isRunning && thinkingEvents.length > 0) {
      setCollapsed(true);
    }
  }, [isRunning, thinkingEvents.length]);

  // Compute completed step count
  const completedCount = useMemo(() => {
    if (!isRunning && currentStage === 'completed') return STEPS.length;
    const idx = STAGE_ORDER.indexOf(currentStage);
    return idx >= 0 ? idx : 0;
  }, [currentStage, isRunning]);

  const isFailed = !isRunning && currentStage === 'failed';

  const summaryText = useMemo(() => {
    if (isRunning) {
      const activeStep = STEPS.find(
        (s) => getStepStatus(s.key, currentStage, lastActiveStage, isRunning) === 'active',
      );
      return activeStep ? `正在进行: ${activeStep.label}...` : '准备中...';
    }
    if (isFailed) return '审计任务失败';
    if (thinkingEvents.length === 0) return '等待开始';
    return `已完成 ${completedCount}/${STEPS.length} 个步骤`;
  }, [isRunning, currentStage, thinkingEvents.length, completedCount, isFailed]);

  return (
    <Collapse
      activeKey={collapsed ? [] : ['thinking']}
      onChange={(keys) => setCollapsed(!keys.includes('thinking'))}
      style={{ marginTop: 16 }}
      items={[
        {
          key: 'thinking',
          label: (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
              }}
            >
              <span style={{ fontWeight: 500 }}>审计进度</span>
              <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
                {summaryText}
              </Text>
              {/* Mini progress dots */}
              <div style={{ display: 'flex', gap: 4, marginRight: 8 }}>
                {STEPS.map((step) => {
                  const status = getStepStatus(
                    step.key,
                    currentStage,
                    lastActiveStage,
                    isRunning,
                  );
                  return (
                    <div
                      key={step.key}
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background:
                          status === 'done'
                            ? '#52c41a'
                            : status === 'active'
                              ? '#1890ff'
                              : '#d9d9d9',
                        transition: 'background 0.3s',
                      }}
                    />
                  );
                })}
              </div>
            </div>
          ),
          children: (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {STEPS.map((step, index) => {
                const status = getStepStatus(
                  step.key,
                  currentStage,
                  lastActiveStage,
                  isRunning,
                );
                const message = getLatestMessage(step.key, thinkingEvents);
                const isLast = index === STEPS.length - 1;

                return (
                  <div
                    key={step.key}
                    style={{
                      display: 'flex',
                      gap: 12,
                      alignItems: 'flex-start',
                      minHeight: isLast ? undefined : 56,
                      position: 'relative',
                    }}
                  >
                    {/* Vertical connector line */}
                    {!isLast && (
                      <div
                        style={{
                          position: 'absolute',
                          left: 11,
                          top: 24,
                          width: 2,
                          height: 32,
                          background:
                            status === 'done' ? '#52c41a' : '#f0f0f0',
                          transition: 'background 0.3s',
                        }}
                      />
                    )}
                    {/* Status icon */}
                    <div
                      style={{
                        width: 24,
                        height: 24,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        zIndex: 1,
                      }}
                    >
                      {status === 'done' ? (
                        <CheckCircleFilled
                          style={{ fontSize: 18, color: '#52c41a' }}
                        />
                      ) : status === 'failed' ? (
                        <CloseCircleFilled
                          style={{ fontSize: 18, color: '#ff4d4f' }}
                        />
                      ) : status === 'active' ? (
                        <LoadingOutlined
                          style={{ fontSize: 18, color: '#1890ff' }}
                          spin
                        />
                      ) : (
                        <ClockCircleOutlined
                          style={{ fontSize: 16, color: '#d9d9d9' }}
                        />
                      )}
                    </div>
                    {/* Content */}
                    <div style={{ flex: 1, paddingBottom: 12 }}>
                      <Text
                        strong={status === 'active'}
                        type={
                          status === 'pending'
                            ? 'secondary'
                            : status === 'done'
                              ? undefined
                              : undefined
                        }
                        style={{
                          fontSize: 13,
                          color:
                            status === 'active'
                              ? '#1890ff'
                              : status === 'done'
                                ? '#333'
                                : '#999',
                        }}
                      >
                        {step.icon} {step.label}
                      </Text>
                      {message && status === 'done' && (
                        <div>
                          <Text
                            type="secondary"
                            style={{ fontSize: 12 }}
                          >
                            {message}
                          </Text>
                        </div>
                      )}
                      {status === 'active' && (
                        <div>
                          <Text
                            type="secondary"
                            style={{ fontSize: 12 }}
                          >
                            {STEPS.find(
                              (s) =>
                                getStepStatus(
                                  s.key,
                                  currentStage,
                                  lastActiveStage,
                                  isRunning,
                                ) === 'active',
                            )?.label || ''}
                            ...
                          </Text>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ),
        },
      ]}
    />
  );
};

export default AgentThinkingPanel;
