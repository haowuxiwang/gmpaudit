import React from 'react';
import { render, screen } from '@testing-library/react';
import AgentFlowChart from '../AgentFlowChart';

// Mock echarts-for-react
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

describe('AgentFlowChart - branch coverage', () => {
  // --- getNodeColor branches ---

  test('renders with pending stage (default color)', () => {
    render(<AgentFlowChart currentStage="pending" completedStages={[]} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with parsing stage as current', () => {
    render(<AgentFlowChart currentStage="parsing" completedStages={[]} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with regulation stage as current', () => {
    render(<AgentFlowChart currentStage="regulation" completedStages={['parsing']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with risk stage as current', () => {
    render(<AgentFlowChart currentStage="risk" completedStages={['parsing', 'regulation']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with report stage as current', () => {
    render(<AgentFlowChart currentStage="report" completedStages={['parsing', 'regulation', 'risk']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with completed stage', () => {
    render(<AgentFlowChart currentStage="completed" completedStages={['parsing', 'regulation', 'risk', 'report']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  // --- failedStage branch ---

  test('renders with failed stage at parsing', () => {
    render(<AgentFlowChart currentStage="parsing" completedStages={[]} failedStage="parsing" />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with failed stage at regulation', () => {
    render(<AgentFlowChart currentStage="regulation" completedStages={['parsing']} failedStage="regulation" />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with failed stage at risk', () => {
    render(<AgentFlowChart currentStage="risk" completedStages={['parsing', 'regulation']} failedStage="risk" />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with failed stage at report', () => {
    render(<AgentFlowChart currentStage="report" completedStages={['parsing', 'regulation', 'risk']} failedStage="report" />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  // --- isStartActive branches ---

  test('renders with queued stage (start active)', () => {
    render(<AgentFlowChart currentStage="queued" completedStages={[]} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with routing stage (start active)', () => {
    render(<AgentFlowChart currentStage="routing" completedStages={[]} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  // --- onNodeClick branches ---

  test('configures click events when onNodeClick provided', () => {
    const handleClick = jest.fn();
    render(<AgentFlowChart currentStage="pending" completedStages={[]} onNodeClick={handleClick} />);
    expect(screen.getByTestId('echarts-events')).toBeInTheDocument();
  });

  test('does not configure click events when onNodeClick not provided', () => {
    render(<AgentFlowChart currentStage="pending" completedStages={[]} />);
    expect(screen.queryByTestId('echarts-events')).not.toBeInTheDocument();
  });

  // --- Style prop ---

  test('renders with custom style', () => {
    const { container } = render(
      <AgentFlowChart currentStage="pending" completedStages={[]} style={{ backgroundColor: 'red' }} />
    );
    expect(container.firstChild).toBeTruthy();
  });

  test('renders with empty style', () => {
    const { container } = render(
      <AgentFlowChart currentStage="pending" completedStages={[]} style={{}} />
    );
    expect(container.firstChild).toBeTruthy();
  });

  // --- completedStages variations ---

  test('renders with single completed stage', () => {
    render(<AgentFlowChart currentStage="regulation" completedStages={['parsing']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with two completed stages', () => {
    render(<AgentFlowChart currentStage="risk" completedStages={['parsing', 'regulation']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with three completed stages', () => {
    render(<AgentFlowChart currentStage="report" completedStages={['parsing', 'regulation', 'risk']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  test('renders with all stages completed', () => {
    render(<AgentFlowChart currentStage="completed" completedStages={['parsing', 'regulation', 'risk', 'report']} />);
    expect(screen.getByTestId('echarts')).toBeInTheDocument();
  });

  // --- Option structure ---

  test('generates correct option structure', () => {
    render(<AgentFlowChart currentStage="pending" completedStages={[]} />);
    const optionEl = screen.getByTestId('echarts-option');
    const option = JSON.parse(optionEl.textContent || '{}');

    expect(option.tooltip).toEqual({ show: false });
    expect(option.series).toHaveLength(1);
    expect(option.series[0].type).toBe('graph');
    expect(option.series[0].layout).toBe('none');
  });

  test('generates nodes with correct names', () => {
    render(<AgentFlowChart currentStage="pending" completedStages={[]} />);
    const optionEl = screen.getByTestId('echarts-option');
    const option = JSON.parse(optionEl.textContent || '{}');
    const nodeNames = option.series[0].data.map((n: any) => n.name);

    expect(nodeNames).toContain('start');
    expect(nodeNames).toContain('end');
    expect(nodeNames).toContain('文档解析');
    expect(nodeNames).toContain('法规匹配');
    expect(nodeNames).toContain('风险评估');
    expect(nodeNames).toContain('报告生成');
  });

  test('generates edges between nodes', () => {
    render(<AgentFlowChart currentStage="pending" completedStages={[]} />);
    const optionEl = screen.getByTestId('echarts-option');
    const option = JSON.parse(optionEl.textContent || '{}');
    const links = option.series[0].links;

    expect(links.length).toBe(5); // start->parsing, parsing->regulation, regulation->risk, risk->report, report->end
  });

  test('applies running color to current stage node', () => {
    render(<AgentFlowChart currentStage="parsing" completedStages={[]} />);
    const optionEl = screen.getByTestId('echarts-option');
    const option = JSON.parse(optionEl.textContent || '{}');
    const parsingNode = option.series[0].data.find((n: any) => n.name === '文档解析');

    expect(parsingNode.itemStyle.shadowBlur).toBe(12);
  });

  test('applies completed color to completed stage nodes', () => {
    render(<AgentFlowChart currentStage="risk" completedStages={['parsing', 'regulation']} />);
    const optionEl = screen.getByTestId('echarts-option');
    const option = JSON.parse(optionEl.textContent || '{}');
    const parsingNode = option.series[0].data.find((n: any) => n.name === '文档解析');

    expect(parsingNode.itemStyle.color).toBe('#10B981');
  });

  test('applies failed color to failed stage node', () => {
    render(<AgentFlowChart currentStage="regulation" completedStages={['parsing']} failedStage="regulation" />);
    const optionEl = screen.getByTestId('echarts-option');
    const option = JSON.parse(optionEl.textContent || '{}');
    const regulationNode = option.series[0].data.find((n: any) => n.name === '法规匹配');

    expect(regulationNode.itemStyle.color).toBe('#DC2626');
  });

  test('applies pending color to pending stage nodes', () => {
    render(<AgentFlowChart currentStage="parsing" completedStages={[]} />);
    const optionEl = screen.getByTestId('echarts-option');
    const option = JSON.parse(optionEl.textContent || '{}');
    const riskNode = option.series[0].data.find((n: any) => n.name === '风险评估');

    expect(riskNode.itemStyle.color).toBe('#D1D5DB');
  });

  test('applies larger symbol size to current stage node', () => {
    render(<AgentFlowChart currentStage="regulation" completedStages={['parsing']} />);
    const optionEl = screen.getByTestId('echarts-option');
    const option = JSON.parse(optionEl.textContent || '{}');
    const regulationNode = option.series[0].data.find((n: any) => n.name === '法规匹配');
    const parsingNode = option.series[0].data.find((n: any) => n.name === '文档解析');

    expect(regulationNode.symbolSize).toBe(50);
    expect(parsingNode.symbolSize).toBe(40);
  });

  test('applies completed edge style for completed stages', () => {
    render(<AgentFlowChart currentStage="regulation" completedStages={['parsing']} />);
    const optionEl = screen.getByTestId('echarts-option');
    const option = JSON.parse(optionEl.textContent || '{}');
    const startEdge = option.series[0].links[0];

    expect(startEdge.lineStyle.color).toBe('#10B981');
    expect(startEdge.lineStyle.width).toBe(3);
  });

  test('applies pending edge style for uncompleted stages', () => {
    render(<AgentFlowChart currentStage="parsing" completedStages={[]} />);
    const optionEl = screen.getByTestId('echarts-option');
    const option = JSON.parse(optionEl.textContent || '{}');
    const regulationEdge = option.series[0].links[1];

    expect(regulationEdge.lineStyle.color).toBe('#D1D5DB');
    expect(regulationEdge.lineStyle.width).toBe(2);
  });
});
