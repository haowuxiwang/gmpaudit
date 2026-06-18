import React from 'react';
import { render, screen } from '@testing-library/react';

import AgentThinkingPanel from '../AgentThinkingPanel';

describe('AgentThinkingPanel', () => {
  const mockEvents = [
    { node: 'parse_doc', stage: 'parsing', status: 'started', message: 'Parsing...' },
    { node: 'parse_doc', stage: 'parsing', status: 'completed', message: '文档解析完成' },
    { node: 'regulation_expert', stage: 'regulation', status: 'started', message: 'Searching...' },
    { node: 'regulation_expert', stage: 'regulation', status: 'completed', message: '找到10条法规' },
  ];

  test('shows completed steps when awaiting_review', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={mockEvents}
        currentStage="awaiting_review"
        lastActiveStage="report"
        isRunning={false}
      />,
    );

    // Should show 4/4 completed
    expect(screen.getByText(/已完成 4\/4 个步骤/)).toBeInTheDocument();
    expect(screen.getByText(/等待审批/)).toBeInTheDocument();
  });

  test('shows completed steps when completed', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={mockEvents}
        currentStage="completed"
        lastActiveStage="report"
        isRunning={false}
      />,
    );

    expect(screen.getByText(/已完成 4\/4 个步骤/)).toBeInTheDocument();
  });

  test('shows active step when running', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={mockEvents}
        currentStage="risk"
        lastActiveStage="risk"
        isRunning={true}
      />,
    );

    expect(screen.getByText(/正在进行.*风险评估/)).toBeInTheDocument();
  });

  test('shows 0/4 when currentStage is pending', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={[]}
        currentStage="pending"
        lastActiveStage="pending"
        isRunning={false}
      />,
    );

    expect(screen.getByText('等待开始')).toBeInTheDocument();
  });

  test('shows correct count for intermediate stage', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={mockEvents}
        currentStage="risk"
        lastActiveStage="risk"
        isRunning={false}
      />,
    );

    expect(screen.getByText(/已完成 2\/4 个步骤/)).toBeInTheDocument();
  });
});
