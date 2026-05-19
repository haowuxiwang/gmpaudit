import React from 'react';
import ReactECharts from 'echarts-for-react';
import { STAGE_COLORS, STAGE_LABELS } from '../constants/audit';

interface AgentFlowChartProps {
  currentStage: string;
  completedStages: string[];
  failedStage?: string;
  style?: React.CSSProperties;
  onNodeClick?: (stage: string) => void;
}

const STAGE_ORDER = ['parsing', 'regulation', 'risk', 'report'];

const AgentFlowChart: React.FC<AgentFlowChartProps> = ({ currentStage, completedStages, failedStage, style, onNodeClick }) => {
  const getNodeColor = (stage: string) => {
    if (failedStage === stage) return STAGE_COLORS.failed;
    if (completedStages.includes(stage)) return STAGE_COLORS.completed;
    if (currentStage === stage) return STAGE_COLORS.running;
    return STAGE_COLORS.pending;
  };

  const getNodeSymbolSize = (stage: string) => {
    if (currentStage === stage) return 50;
    return 40;
  };

  const nodes = [
    { name: 'start', x: 50, y: 200, symbolSize: 30, itemStyle: { color: '#52c41a' } },
    ...STAGE_ORDER.map((stage, index) => ({
      name: STAGE_LABELS[stage] || stage,
      x: 150 + index * 150,
      y: 200,
      symbolSize: getNodeSymbolSize(stage),
      itemStyle: {
        color: getNodeColor(stage),
        ...(currentStage === stage ? { shadowBlur: 12, shadowColor: getNodeColor(stage) } : {}),
      },
      label: { show: true, position: 'bottom' as const, fontSize: 12 },
    })),
    { name: 'end', x: 150 + STAGE_ORDER.length * 150, y: 200, symbolSize: 30, itemStyle: { color: '#999' } },
  ];

  const edges = [
    {
      source: 'start',
      target: STAGE_LABELS[STAGE_ORDER[0]],
      lineStyle: {
        color: completedStages.includes(STAGE_ORDER[0]) ? STAGE_COLORS.completed : '#D1D5DB',
        width: completedStages.includes(STAGE_ORDER[0]) ? 3 : 2,
      },
    },
    ...STAGE_ORDER.slice(0, -1).map((stage, index) => ({
      source: STAGE_LABELS[stage],
      target: STAGE_LABELS[STAGE_ORDER[index + 1]],
      lineStyle: {
        color: completedStages.includes(stage) ? STAGE_COLORS.completed : '#D1D5DB',
        width: completedStages.includes(stage) ? 3 : 2,
      },
    })),
    {
      source: STAGE_LABELS[STAGE_ORDER[STAGE_ORDER.length - 1]],
      target: 'end',
      lineStyle: {
        color: completedStages.includes(STAGE_ORDER[STAGE_ORDER.length - 1]) ? STAGE_COLORS.completed : '#D1D5DB',
        width: completedStages.includes(STAGE_ORDER[STAGE_ORDER.length - 1]) ? 3 : 2,
      },
    },
  ];

  const option = {
    tooltip: { show: false },
    series: [
      {
        type: 'graph',
        layout: 'none',
        symbolSize: 40,
        label: { show: true },
        edgeSymbol: ['circle', 'arrow'],
        edgeSymbolSize: [4, 12],
        data: nodes,
        links: edges,
        lineStyle: { opacity: 0.9, width: 2, curveness: 0 },
        emphasis: { focus: 'adjacency' },
      },
    ],
  };

  const onEvents = onNodeClick
    ? {
        click: (params: any) => {
          if (params.dataType === 'node') {
            const stageName = STAGE_ORDER.find(s => STAGE_LABELS[s] === params.name);
            if (stageName) onNodeClick(stageName);
          }
        },
      }
    : undefined;

  return (
    <div style={{ borderRadius: 8, overflow: 'hidden', ...style }}>
      <ReactECharts option={option} style={{ height: 280 }} onEvents={onEvents} />
    </div>
  );
};

export default AgentFlowChart;
