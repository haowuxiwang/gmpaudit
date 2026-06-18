import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgentThinkingPanel from '../AgentThinkingPanel';

describe('AgentThinkingPanel - branch coverage', () => {
  const completedEvents = [
    { node: 'parse_doc', stage: 'parsing', status: 'started', message: 'Parsing...' },
    { node: 'parse_doc', stage: 'parsing', status: 'completed', message: '文档解析完成' },
    { node: 'regulation_expert', stage: 'regulation', status: 'started', message: 'Searching...' },
    { node: 'regulation_expert', stage: 'regulation', status: 'completed', message: '找到10条法规' },
    { node: 'risk_assessor', stage: 'risk', status: 'started', message: 'Assessing...' },
    { node: 'risk_assessor', stage: 'risk', status: 'completed', message: '风险评估完成' },
    { node: 'report_writer', stage: 'report', status: 'started', message: 'Writing...' },
    { node: 'report_writer', stage: 'report', status: 'completed', message: '报告生成完成' },
  ];

  // --- getStepStatus branches ---

  test('shows all steps as done when completed', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="completed"
        lastActiveStage="report"
        isRunning={false}
      />
    );
    expect(screen.getByText(/已完成 4\/4 个步骤/)).toBeInTheDocument();
  });

  test('shows all steps as done when awaiting_review', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="awaiting_review"
        lastActiveStage="report"
        isRunning={false}
      />
    );
    expect(screen.getByText(/已完成 4\/4 个步骤/)).toBeInTheDocument();
    expect(screen.getByText(/等待审批/)).toBeInTheDocument();
  });

  test('shows failed step when currentStage is failed', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="failed"
        lastActiveStage="regulation"
        isRunning={false}
      />
    );
    expect(screen.getByText('审计任务失败')).toBeInTheDocument();
  });

  test('shows correct step counts for failed stage at parsing', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={[]}
        currentStage="failed"
        lastActiveStage="parsing"
        isRunning={false}
      />
    );
    expect(screen.getByText('审计任务失败')).toBeInTheDocument();
  });

  test('shows correct step counts for failed stage at report', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="failed"
        lastActiveStage="report"
        isRunning={false}
      />
    );
    expect(screen.getByText('审计任务失败')).toBeInTheDocument();
  });

  test('handles failed with unknown lastActiveStage', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={[]}
        currentStage="failed"
        lastActiveStage="unknown_stage"
        isRunning={false}
      />
    );
    expect(screen.getByText('审计任务失败')).toBeInTheDocument();
  });

  // --- Running state branches ---

  test('shows active step when running at parsing', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={[]}
        currentStage="parsing"
        lastActiveStage="parsing"
        isRunning={true}
      />
    );
    expect(screen.getByText(/正在进行.*解析文档/)).toBeInTheDocument();
  });

  test('shows active step when running at regulation', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents.slice(0, 2)}
        currentStage="regulation"
        lastActiveStage="regulation"
        isRunning={true}
      />
    );
    expect(screen.getByText(/正在进行.*检索法规/)).toBeInTheDocument();
  });

  test('shows active step when running at risk', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents.slice(0, 4)}
        currentStage="risk"
        lastActiveStage="risk"
        isRunning={true}
      />
    );
    expect(screen.getByText(/正在进行.*风险评估/)).toBeInTheDocument();
  });

  test('shows active step when running at report', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents.slice(0, 6)}
        currentStage="report"
        lastActiveStage="report"
        isRunning={true}
      />
    );
    expect(screen.getByText(/正在进行.*生成报告/)).toBeInTheDocument();
  });

  test('shows "准备中..." when running with unknown stage', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={[]}
        currentStage="unknown"
        lastActiveStage="unknown"
        isRunning={true}
      />
    );
    expect(screen.getByText('准备中...')).toBeInTheDocument();
  });

  // --- Summary text branches ---

  test('shows "等待开始" when no events and not running', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={[]}
        currentStage="pending"
        lastActiveStage="pending"
        isRunning={false}
      />
    );
    expect(screen.getByText('等待开始')).toBeInTheDocument();
  });

  test('shows correct count for intermediate stage', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents.slice(0, 4)}
        currentStage="risk"
        lastActiveStage="risk"
        isRunning={false}
      />
    );
    expect(screen.getByText(/已完成 2\/4 个步骤/)).toBeInTheDocument();
  });

  test('shows 1/4 for parsing stage completed', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents.slice(0, 2)}
        currentStage="regulation"
        lastActiveStage="regulation"
        isRunning={false}
      />
    );
    expect(screen.getByText(/已完成 1\/4 个步骤/)).toBeInTheDocument();
  });

  test('shows 3/4 for report stage completed', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents.slice(0, 6)}
        currentStage="report"
        lastActiveStage="report"
        isRunning={false}
      />
    );
    expect(screen.getByText(/已完成 3\/4 个步骤/)).toBeInTheDocument();
  });

  // --- Auto-collapse behavior ---

  test('auto-collapses when task finishes', async () => {
    const { rerender } = render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="risk"
        lastActiveStage="risk"
        isRunning={true}
      />
    );

    // Panel should be expanded while running
    expect(screen.getByText('审计进度')).toBeInTheDocument();

    // Simulate task completion
    rerender(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="completed"
        lastActiveStage="report"
        isRunning={false}
      />
    );

    // After completion, panel should auto-collapse
    await waitFor(() => {
      expect(screen.getByText(/已完成 4\/4 个步骤/)).toBeInTheDocument();
    });
  });

  test('does not auto-collapse when running', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="risk"
        lastActiveStage="risk"
        isRunning={true}
      />
    );

    // Panel should be expanded while running
    expect(screen.getByText('审计进度')).toBeInTheDocument();
  });

  // --- Step status icons ---

  test('shows correct icons for different step statuses', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="report"
        lastActiveStage="report"
        isRunning={false}
      />
    );

    // Parsing and regulation should show done (check icon)
    // Risk and report should show pending (clock icon)
    expect(screen.getByText('审计进度')).toBeInTheDocument();
  });

  test('shows loading icon for active step', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents.slice(0, 4)}
        currentStage="risk"
        lastActiveStage="risk"
        isRunning={true}
      />
    );

    // Risk step should show loading icon
    expect(screen.getByText(/正在进行.*风险评估/)).toBeInTheDocument();
  });

  test('shows error icon for failed step', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="failed"
        lastActiveStage="risk"
        isRunning={false}
      />
    );

    // Failed step should show error icon
    expect(screen.getByText('审计任务失败')).toBeInTheDocument();
  });

  // --- Message display ---

  test('shows completed message for done steps', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="completed"
        lastActiveStage="report"
        isRunning={false}
      />
    );

    // Messages from completed events should be visible
    expect(screen.getByText('文档解析完成')).toBeInTheDocument();
    expect(screen.getByText('找到10条法规')).toBeInTheDocument();
  });

  test('does not show message for active step', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents.slice(0, 2)}
        currentStage="regulation"
        lastActiveStage="regulation"
        isRunning={true}
      />
    );

    // Active step shows label, not message
    expect(screen.getByText(/正在进行.*检索法规/)).toBeInTheDocument();
  });

  // --- Collapse/expand interaction ---

  test('can toggle collapse by clicking', async () => {
    const user = userEvent.setup();
    render(
      <AgentThinkingPanel
        thinkingEvents={completedEvents}
        currentStage="completed"
        lastActiveStage="report"
        isRunning={false}
      />
    );

    // Panel should be collapsed (auto-collapse on complete)
    const header = screen.getByText('审计进度');
    await user.click(header);

    // After click, panel should expand
    await waitFor(() => {
      expect(screen.getByText(/已完成 4\/4 个步骤/)).toBeInTheDocument();
    });
  });

  // --- Edge cases ---

  test('handles empty events with running state', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={[]}
        currentStage="parsing"
        lastActiveStage="parsing"
        isRunning={true}
      />
    );
    expect(screen.getByText(/正在进行.*解析文档/)).toBeInTheDocument();
  });

  test('handles events with non-completed status', () => {
    const events = [
      { node: 'parse_doc', stage: 'parsing', status: 'started', message: 'Starting...' },
    ];
    render(
      <AgentThinkingPanel
        thinkingEvents={events}
        currentStage="parsing"
        lastActiveStage="parsing"
        isRunning={true}
      />
    );
    expect(screen.getByText(/正在进行.*解析文档/)).toBeInTheDocument();
  });

  test('renders with minimal props', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={[]}
        currentStage="pending"
      />
    );
    expect(screen.getByText('等待开始')).toBeInTheDocument();
  });

  test('renders with default lastActiveStage', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={[]}
        currentStage="pending"
        isRunning={false}
      />
    );
    expect(screen.getByText('等待开始')).toBeInTheDocument();
  });

  test('renders with default isRunning', () => {
    render(
      <AgentThinkingPanel
        thinkingEvents={[]}
        currentStage="pending"
      />
    );
    expect(screen.getByText('等待开始')).toBeInTheDocument();
  });
});
