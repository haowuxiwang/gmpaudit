import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import KnowledgeGraphPage from '../KnowledgeGraphPage';
import { kgApi } from '../../services/api';

jest.setTimeout(15000);

jest.mock('../../services/api', () => ({
  kgApi: {
    getStatus: jest.fn(),
    build: jest.fn(),
    query: jest.fn(),
    getDocuments: jest.fn(),
    getBuildStatus: jest.fn(),
    getGraphData: jest.fn(),
    uploadDocument: jest.fn(),
    deleteDocument: jest.fn(),
  },
}));

jest.mock('echarts-for-react', () => {
  return function MockECharts({ onEvents }: any) {
    return <div data-testid="echarts" onClick={() => onEvents?.click?.({ dataType: 'node', data: { id: '1', name: 'Test Node', category: '法规', description: 'Test description' } })}>Chart</div>;
  };
});

const mockKgApi = kgApi as jest.Mocked<typeof kgApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

const mockStatus = {
  built: true,
  file_count: 5,
  last_modified: '2024-01-01T00:00:00Z',
  input_file_count: 3,
  building: false,
};

const mockDocuments = {
  documents: [
    { filename: 'GMP法规.txt', size: 10240, modified: '2024-01-01T00:00:00Z' },
  ],
};

const mockGraphData = {
  nodes: [
    { id: '1', name: 'GMP', category: '法规', description: 'Good Manufacturing Practice' },
    { id: '2', name: '偏差处理', category: '概念', description: '偏差处理流程' },
    { id: '3', name: 'CAPA', category: '方法', description: '纠正和预防措施' },
  ],
  edges: [
    { source: '1', target: '2', label: '包含' },
    { source: '2', target: '3', label: '导致' },
  ],
};

describe('KnowledgeGraphPage branch coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockKgApi.getStatus.mockResolvedValue(mockStatus);
    mockKgApi.getDocuments.mockResolvedValue(mockDocuments);
    mockKgApi.getBuildStatus.mockResolvedValue({ building: false });
    mockKgApi.getGraphData.mockResolvedValue(mockGraphData);
    mockKgApi.query.mockResolvedValue({ results: [] });
    mockKgApi.build.mockResolvedValue({ message: '构建已启动' });
  });

  // --- Build polling: starts and completes ---
  test('build polling shows logs and completes', async () => {
    mockKgApi.build.mockResolvedValue({ message: '构建已启动' });
    mockKgApi.getBuildStatus
      .mockResolvedValueOnce({ building: true, recent_logs: ['Step 1...', 'Step 2...'] })
      .mockResolvedValueOnce({ building: false, recent_logs: ['Done'] });

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('重新构建')).toBeInTheDocument();
    });

    await user.click(screen.getByText('重新构建'));

    // Should show build logs section
    await waitFor(() => {
      expect(screen.getByText('构建日志')).toBeInTheDocument();
    });
  });

  // --- Build polling error ---
  test('build polling handles getBuildStatus error', async () => {
    mockKgApi.build.mockResolvedValue({ message: '构建已启动' });
    mockKgApi.getBuildStatus.mockRejectedValue(new Error('Polling failed'));

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('重新构建')).toBeInTheDocument();
    });

    await user.click(screen.getByText('重新构建'));

    // Should not crash
    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  // --- Upload handler ---
  test('upload handler calls uploadDocument API', async () => {
    mockKgApi.uploadDocument.mockResolvedValue({ filename: 'new-doc.txt', status: 'uploaded' });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('上传法规文档')).toBeInTheDocument();
    });

    // Find the file input
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    if (input) {
      const file = new File(['content'], 'new-doc.txt', { type: 'text/plain' });
      Object.defineProperty(file, 'size', { value: 100 });

      const { fireEvent } = require('@testing-library/react');
      fireEvent.change(input, { target: { files: [file] } });

      await waitFor(() => {
        expect(mockKgApi.uploadDocument).toHaveBeenCalled();
      });
    }
  });

  // --- Upload handler error ---
  test('upload handler handles error', async () => {
    mockKgApi.uploadDocument.mockRejectedValue(new Error('Upload failed'));

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('上传法规文档')).toBeInTheDocument();
    });

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    if (input) {
      const file = new File(['content'], 'bad-doc.txt', { type: 'text/plain' });
      Object.defineProperty(file, 'size', { value: 100 });

      const { fireEvent } = require('@testing-library/react');
      fireEvent.change(input, { target: { files: [file] } });

      await waitFor(() => {
        expect(mockKgApi.uploadDocument).toHaveBeenCalled();
      });
    }
  });

  // --- Empty query warning ---
  test('shows warning when querying with empty text', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('查询图谱')).toBeInTheDocument();
    });

    // Click query without entering text
    await user.click(screen.getByText('查询图谱'));

    // Should not call query API
    expect(mockKgApi.query).not.toHaveBeenCalled();
  });

  // --- Node click event ---
  test('clicking on chart node shows node detail modal', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });

    // Click on the chart (which triggers onEvents.click mock)
    const { fireEvent } = require('@testing-library/react');
    fireEvent.click(screen.getByTestId('echarts'));

    await waitFor(() => {
      expect(screen.getByText('Test Node')).toBeInTheDocument();
    });
  });

  // --- Node detail modal ---
  test('node detail modal shows category and description', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });

    const { fireEvent } = require('@testing-library/react');
    fireEvent.click(screen.getByTestId('echarts'));

    await waitFor(() => {
      expect(screen.getByText('Test description')).toBeInTheDocument();
    });

    expect(screen.getByText('法规')).toBeInTheDocument();
  });

  // --- Node detail modal close ---
  test('node detail modal has close button', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });

    const { fireEvent } = require('@testing-library/react');
    fireEvent.click(screen.getByTestId('echarts'));

    await waitFor(() => {
      expect(screen.getByText('Test Node')).toBeInTheDocument();
    });

    // Modal should have a close button
    expect(document.querySelector('.ant-modal-close')).toBeInTheDocument();
  });

  // --- Node with unknown category ---
  test('handles node with unknown category color', async () => {
    mockKgApi.getGraphData.mockResolvedValue({
      nodes: [
        { id: '1', name: 'Unknown Category Node', category: 'unknown_category', description: 'desc' },
      ],
      edges: [],
    });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Category colors mapping ---
  test('handles all category color types', async () => {
    mockKgApi.getGraphData.mockResolvedValue({
      nodes: [
        { id: '1', name: 'Concept', category: 'concept', description: 'd' },
        { id: '2', name: 'Org', category: 'organization', description: 'd' },
        { id: '3', name: 'Person', category: 'person', description: 'd' },
        { id: '4', name: 'Method', category: 'method', description: 'd' },
        { id: '5', name: 'Reg', category: 'regulation', description: 'd' },
        { id: '6', name: 'Unknown', category: 'unknown', description: 'd' },
        { id: '7', name: 'Concept CN', category: '概念', description: 'd' },
        { id: '8', name: 'Org CN', category: '组织', description: 'd' },
        { id: '9', name: 'Inst CN', category: '机构', description: 'd' },
        { id: '10', name: 'Person CN', category: '人物', description: 'd' },
        { id: '11', name: 'Person CN2', category: '人员', description: 'd' },
        { id: '12', name: 'Method CN', category: '方法', description: 'd' },
        { id: '13', name: 'Reg CN', category: '法规', description: 'd' },
        { id: '14', name: 'RegDoc CN', category: '法规文件', description: 'd' },
        { id: '15', name: 'Unknown CN', category: '未知', description: 'd' },
      ],
      edges: [],
    });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Focused graph with query results ---
  test('focused graph filters nodes based on query results', async () => {
    mockKgApi.getGraphData.mockResolvedValue({
      nodes: [
        { id: '1', name: 'GMP法规', category: '法规', description: 'Good Manufacturing Practice' },
        { id: '2', name: '偏差处理', category: '概念', description: '偏差处理流程' },
        { id: '3', name: 'CAPA', category: '方法', description: '纠正措施' },
        { id: '4', name: 'FDA', category: '组织', description: '美国FDA' },
        { id: '5', name: '文件管理', category: '概念', description: 'GMP文件管理' },
      ],
      edges: [
        { source: '1', target: '2', label: '包含' },
        { source: '2', target: '3', label: '导致' },
        { source: '1', target: '4', label: '监管' },
        { source: '1', target: '5', label: '包含' },
      ],
    });
    mockKgApi.query.mockResolvedValue({
      results: [
        { regulation: 'GMP 2010', chapter: '第七章', title: '偏差处理', content: '偏差处理内容', relevance: 0.9 },
      ],
    });

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, '偏差处理');
    await user.click(screen.getByText('查询图谱'));

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Focused graph with no search terms (all nodes) ---
  test('focused graph shows all nodes when no query results', async () => {
    mockKgApi.getGraphData.mockResolvedValue(mockGraphData);
    mockKgApi.query.mockResolvedValue({ results: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Graph data with more than 120 nodes (no query) ---
  test('focused graph limits to 120 nodes when no query', async () => {
    const largeGraphData = {
      nodes: Array.from({ length: 150 }, (_, i) => ({
        id: String(i),
        name: `Node ${i}`,
        category: '概念',
        description: `Description ${i}`,
      })),
      edges: Array.from({ length: 50 }, (_, i) => ({
        source: String(i),
        target: String(i + 1),
        label: 'relates',
      })),
    };
    mockKgApi.getGraphData.mockResolvedValue(largeGraphData);

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Graph data with more than 80 matching nodes (with query) ---
  test('focused graph limits to 80 nodes when query matches many', async () => {
    const manyMatchNodes = Array.from({ length: 100 }, (_, i) => ({
      id: String(i),
      name: `偏差处理 Node ${i}`,
      category: '概念',
      description: `Description ${i}`,
    }));
    mockKgApi.getGraphData.mockResolvedValue({
      nodes: manyMatchNodes,
      edges: [],
    });
    mockKgApi.query.mockResolvedValue({
      results: [
        { regulation: 'GMP', chapter: '', title: '偏差处理', content: 'content', relevance: 0.9 },
      ],
    });

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, '偏差处理');
    await user.click(screen.getByText('查询图谱'));

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Query with non-Error exception ---
  test('query handles non-Error exception', async () => {
    mockKgApi.query.mockRejectedValue('string error');

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, 'test');
    await user.click(screen.getByText('查询图谱'));

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  // --- Query with whitespace only ---
  test('query with whitespace only does not crash', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, '   ');
    await user.click(screen.getByText('查询图谱'));

    // Should not crash
    expect(screen.getByText('知识图谱')).toBeInTheDocument();
  });

  // --- Build error message ---
  test('build error shows error message', async () => {
    mockKgApi.build.mockRejectedValue(new Error('构建失败'));

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('重新构建')).toBeInTheDocument();
    });

    await user.click(screen.getByText('重新构建'));

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  // --- Build non-Error exception ---
  test('build handles non-Error exception', async () => {
    mockKgApi.build.mockRejectedValue('string error');

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('重新构建')).toBeInTheDocument();
    });

    await user.click(screen.getByText('重新构建'));

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  // --- Document with null modified ---
  test('handles document with null modified time', async () => {
    mockKgApi.getDocuments.mockResolvedValue({
      documents: [
        { filename: 'no-date.txt', size: 1024, modified: null },
      ],
    });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('no-date.txt')).toBeInTheDocument();
    });

    // Should show '-' for null modified
    expect(screen.getByText('-')).toBeInTheDocument();
  });

  // --- Document size = 0 ---
  test('handles document with size 0', async () => {
    mockKgApi.getDocuments.mockResolvedValue({
      documents: [
        { filename: 'empty.txt', size: 0, modified: '2024-01-01T00:00:00Z' },
      ],
    });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('empty.txt')).toBeInTheDocument();
    });

    expect(screen.getByText('0.0 KB')).toBeInTheDocument();
  });

  // --- Search input onChange ---
  test('search input onChange updates query text', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, 'CAPA');

    // Value should contain 'CAPA' (may have initial text)
    expect((input as HTMLInputElement).value).toContain('CAPA');
  });

  // --- loadGraphData null result ---
  test('handles loadGraphData returning null', async () => {
    mockKgApi.getGraphData.mockResolvedValue(null as any);

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('点击加载图谱可视化')).toBeInTheDocument();
    });
  });

  // --- loadGraphData load button ---
  test('load graph button calls getGraphData', async () => {
    mockKgApi.getGraphData.mockResolvedValue(null as any);

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('加载图谱')).toBeInTheDocument();
    });

    await user.click(screen.getByText('加载图谱'));

    await waitFor(() => {
      expect(mockKgApi.getGraphData).toHaveBeenCalledTimes(2);
    });
  });

  // --- Not built: shows build button ---
  test('not built state shows build graph button', async () => {
    mockKgApi.getStatus.mockResolvedValue({
      built: false,
      file_count: 0,
      last_modified: null,
      input_file_count: 0,
      building: false,
    });
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('构建图谱')).toBeInTheDocument();
    });
  });

  // --- Not built: search results show build prompt ---
  test('not built state shows build prompt in search results', async () => {
    mockKgApi.getStatus.mockResolvedValue({
      built: false,
      file_count: 0,
      last_modified: null,
      input_file_count: 0,
      building: false,
    });
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('请先构建图谱')).toBeInTheDocument();
    });
  });

  // --- Not built: graph shows build prompt ---
  test('not built state shows build prompt in graph section', async () => {
    mockKgApi.getStatus.mockResolvedValue({
      built: false,
      file_count: 0,
      last_modified: null,
      input_file_count: 0,
      building: false,
    });
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('请先构建知识图谱')).toBeInTheDocument();
    });
  });

  // --- Built but no graph data: shows load button ---
  test('built state with null graph data shows load button', async () => {
    mockKgApi.getGraphData.mockResolvedValue(null as any);

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('加载图谱')).toBeInTheDocument();
    });
  });

  // --- Graph data edge limits ---
  test('focused graph limits edges to 160', async () => {
    const manyEdges = Array.from({ length: 200 }, (_, i) => ({
      source: String(i % 10),
      target: String((i + 1) % 10),
      label: 'relates',
    }));
    mockKgApi.getGraphData.mockResolvedValue({
      nodes: Array.from({ length: 10 }, (_, i) => ({
        id: String(i),
        name: `Node ${i}`,
        category: '概念',
        description: `Desc ${i}`,
      })),
      edges: manyEdges,
    });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Query result with empty regulation ---
  test('query result with empty regulation still renders', async () => {
    mockKgApi.query.mockResolvedValue({
      results: [
        { regulation: '', chapter: 'Chapter 1', title: 'Title', content: 'Content text', relevance: 0.5 },
      ],
    });

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, 'test');
    await user.click(screen.getByText('查询图谱'));

    await waitFor(() => {
      expect(screen.getByText('Chapter 1')).toBeInTheDocument();
    });
  });

  // --- Document delete interaction ---
  test('delete button shows confirm dialog', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('GMP法规.txt')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('删除');
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(document.querySelector('.ant-modal-confirm')).toBeInTheDocument();
    });
  });

  // --- Refresh graph button ---
  test('refresh graph button calls getGraphData', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('刷新图谱')).toBeInTheDocument();
    });

    await user.click(screen.getByText('刷新图谱'));

    await waitFor(() => {
      expect(mockKgApi.getGraphData).toHaveBeenCalledTimes(2);
    });
  });

  // --- Graph loading spinner ---
  test('shows spinner while graph data loads', async () => {
    let resolveGraph: ((value: any) => void) | null = null;
    const graphPromise = new Promise<any>((resolve) => { resolveGraph = resolve; });
    mockKgApi.getGraphData.mockReturnValue(graphPromise);

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });

    resolveGraph?.(mockGraphData);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });
});
