import React from 'react';
import { render, screen } from '@testing-library/react';
import AgentFlowChart from '../AgentFlowChart';

// Mock echarts
jest.mock('echarts-for-react', () => {
  return function MockECharts({ option, onEvents }: any) {
    return (
      <div data-testid="echarts">
        <div data-testid="echarts-option">{JSON.stringify(option)}</div>
        {onEvents && <div data-testid="echarts-events">events-configured</div>}
      </div>
    );
  };
});

describe('AgentFlowChart', () => {
  test('renders chart component', () => {
    render(<AgentFlowChart currentStage="pending" completedStages={[]} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with completed stages', () => {
    render(<AgentFlowChart currentStage="risk" completedStages={['parsing', 'regulation']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with failed stage', () => {
    render(<AgentFlowChart currentStage="risk" completedStages={['parsing']} failedStage="regulation" />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with all stages completed', () => {
    render(<AgentFlowChart currentStage="completed" completedStages={['parsing', 'regulation', 'risk', 'report']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with custom style', () => {
    const { container } = render(
      <AgentFlowChart currentStage="pending" completedStages={[]} style={{ backgroundColor: 'red' }} />
    );
    expect(container.firstChild).toBeTruthy();
  });

  test('configures click events when onNodeClick provided', () => {
    const handleClick = jest.fn();
    render(<AgentFlowChart currentStage="pending" completedStages={[]} onNodeClick={handleClick} />);
    expect(screen.getByTestId('echarts-events')).toBeInTheDocument();
  });

  test('does not configure click events when onNodeClick not provided', () => {
    render(<AgentFlowChart currentStage="pending" completedStages={[]} />);
    expect(screen.queryByTestId('echarts-events')).not.toBeInTheDocument();
  });

  test('renders with pending stage', () => {
    render(<AgentFlowChart currentStage="pending" completedStages={[]} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with queued stage', () => {
    render(<AgentFlowChart currentStage="queued" completedStages={[]} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with routing stage', () => {
    render(<AgentFlowChart currentStage="routing" completedStages={[]} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with parsing stage', () => {
    render(<AgentFlowChart currentStage="parsing" completedStages={[]} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with regulation stage', () => {
    render(<AgentFlowChart currentStage="regulation" completedStages={['parsing']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with report stage', () => {
    render(<AgentFlowChart currentStage="report" completedStages={['parsing', 'regulation', 'risk']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });
});
