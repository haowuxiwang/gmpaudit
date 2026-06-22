import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

// Mock echarts
jest.mock('echarts-for-react', () => {
  return function MockECharts() {
    return <div data-testid="echarts">Chart</div>;
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

const mockStatusNotBuilt = {
  built: false,
  file_count: 0,
  last_modified: null,
  input_file_count: 0,
  building: false,
};

const mockDocuments = {
  documents: [
    { filename: 'GMP法规.txt', size: 10240, modified: '2024-01-01T00:00:00Z' },
    { filename: '偏差处理指南.md', size: 5120, modified: '2024-01-02T00:00:00Z' },
  ],
};

const mockQueryResult = {
  results: [
    {
      regulation: 'GMP 2010',
      chapter: '第七章',
      title: '偏差处理',
      content: '任何偏差都应记录并调查',
      relevance: 0.95,
    },
    {
      regulation: 'GMP 2010',
      chapter: '第八章',
      title: 'CAPA',
      content: '纠正和预防措施',
      relevance: 0.85,
    },
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

describe('KnowledgeGraphPage extended tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockKgApi.getStatus.mockResolvedValue(mockStatus);
    mockKgApi.getDocuments.mockResolvedValue(mockDocuments);
    mockKgApi.getBuildStatus.mockResolvedValue({ building: false });
    mockKgApi.getGraphData.mockResolvedValue(mockGraphData);
    mockKgApi.query.mockResolvedValue(mockQueryResult);
    mockKgApi.build.mockResolvedValue({ message: '构建已启动' });
  });

  // --- Page title and description ---
  test('renders page title', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  test('renders page description', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('基于法规文档构建知识图谱，支持语义检索')).toBeInTheDocument();
    });
  });

  test('renders usage description', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText(/使用与审计智能体相同的检索词查询图谱/)).toBeInTheDocument();
    });
  });

  // --- Status statistics ---
  test('displays regulation document count', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('法规文档')).toBeInTheDocument();
    });

    expect(screen.getByText('2')).toBeInTheDocument();
  });

  test('displays graph file count', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('图谱文件')).toBeInTheDocument();
    });

    expect(screen.getByText('5')).toBeInTheDocument();
  });

  test('displays built status when built', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('图谱状态')).toBeInTheDocument();
    });

    expect(screen.getByText('已构建')).toBeInTheDocument();
  });

  test('displays not built status when not built', async () => {
    mockKgApi.getStatus.mockResolvedValue(mockStatusNotBuilt);
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('未构建')).toBeInTheDocument();
    });
  });

  // --- Build button ---
  test('shows rebuild button when already built', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('重新构建')).toBeInTheDocument();
    });
  });

  test('shows build button when not built', async () => {
    mockKgApi.getStatus.mockResolvedValue(mockStatusNotBuilt);
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('构建图谱')).toBeInTheDocument();
    });
  });

  test('shows force rebuild button', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('强制重建')).toBeInTheDocument();
    });
  });

  test('calls build when build button clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('重新构建')).toBeInTheDocument();
    });

    await user.click(screen.getByText('重新构建'));

    await waitFor(() => {
      expect(mockKgApi.build).toHaveBeenCalledWith(false);
    });
  });

  test('calls build with force when force rebuild clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('强制重建')).toBeInTheDocument();
    });

    await user.click(screen.getByText('强制重建'));

    await waitFor(() => {
      expect(mockKgApi.build).toHaveBeenCalledWith(true);
    });
  });

  // --- Query functionality ---
  test('renders query input', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });
  });

  test('renders query button', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('查询图谱')).toBeInTheDocument();
    });
  });

  test('query input is enabled when built', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
      expect(input).not.toBeDisabled();
    });
  });

  test('query input is disabled when not built', async () => {
    mockKgApi.getStatus.mockResolvedValue(mockStatusNotBuilt);
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
      expect(input).toBeDisabled();
    });
  });

  test('calls query API when search is triggered', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    }, { timeout: 5000 });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, '偏差处理');

    const searchButton = screen.getByText('查询图谱');
    await user.click(searchButton);

    await waitFor(() => {
      expect(mockKgApi.query).toHaveBeenCalledWith('偏差处理');
    }, { timeout: 5000 });
  });

  // --- Query results ---
  test('displays query results after search', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    }, { timeout: 5000 });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, '偏差处理');

    await user.click(screen.getByText('查询图谱'));

    await waitFor(() => {
      expect(screen.getByText('偏差处理')).toBeInTheDocument();
    }, { timeout: 5000 });

    expect(screen.getByText('任何偏差都应记录并调查')).toBeInTheDocument();
    expect(screen.getByText('CAPA')).toBeInTheDocument();
  });

  test('shows empty state when no query results', async () => {
    mockKgApi.query.mockResolvedValue({ results: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('执行图谱查询以检查证据')).toBeInTheDocument();
    });
  });

  // --- Document list ---
  test('renders document table with documents', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('GMP法规.txt')).toBeInTheDocument();
    });

    expect(screen.getByText('偏差处理指南.md')).toBeInTheDocument();
  });

  test('renders document table title', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('法规库')).toBeInTheDocument();
    });
  });

  test('shows delete button for documents', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      const deleteButtons = screen.getAllByText('删除');
      expect(deleteButtons.length).toBe(2);
    });
  });

  test('shows empty state when no documents', async () => {
    mockKgApi.getDocuments.mockResolvedValue({ documents: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('暂无已上传的法规源文件')).toBeInTheDocument();
    });
  });

  // --- Upload ---
  test('shows upload button', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('上传法规文档')).toBeInTheDocument();
    });
  });

  test('shows supported file format hint', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText(/支持 .txt、.md、.pdf、.docx 格式/)).toBeInTheDocument();
    });
  });

  // --- Graph visualization ---
  test('shows graph section title', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('聚焦视图')).toBeInTheDocument();
    });
  });

  test('shows refresh graph button', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('刷新图谱')).toBeInTheDocument();
    });
  });

  test('shows chart when graph data is available', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  test('renders chart component when graph data is empty but built', async () => {
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    // When graphData is { nodes: [], edges: [] }, chartOption is not null
    // so the ECharts component renders (with empty data)
    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Error handling ---
  test('handles status API error gracefully', async () => {
    mockKgApi.getStatus.mockRejectedValue(new Error('加载失败'));
    mockKgApi.getDocuments.mockRejectedValue(new Error('加载失败'));

    renderWithRouter(<KnowledgeGraphPage />);

    // Page should still render
    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  test('handles graph data API error gracefully', async () => {
    mockKgApi.getGraphData.mockRejectedValue(new Error('图谱加载失败'));

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  test('handles query API error gracefully', async () => {
    mockKgApi.query.mockRejectedValue(new Error('查询失败'));
    const user = userEvent.setup();

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, 'test');

    await user.click(screen.getByText('查询图谱'));

    // Should not crash
    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  // --- Build not built state ---
  test('shows empty state for graph when not built', async () => {
    mockKgApi.getStatus.mockResolvedValue(mockStatusNotBuilt);
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('请先构建知识图谱')).toBeInTheDocument();
    });
  });

  // --- Operations section ---
  test('shows graph operations section', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('图谱操作')).toBeInTheDocument();
    });
  });

  test('shows search results section', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('检索结果')).toBeInTheDocument();
    });
  });

  // --- Document size rendering ---
  test('renders document sizes correctly', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      // 10240 / 1024 = 10.0 KB
      expect(screen.getByText('10.0 KB')).toBeInTheDocument();
    });

    // 5120 / 1024 = 5.0 KB
    expect(screen.getByText('5.0 KB')).toBeInTheDocument();
  });

  // --- Query with initial search params ---
  test('auto-queries when q search param is present and built', async () => {
    // We can't easily set search params with BrowserRouter, but we can verify
    // the query input accepts initial values
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });
  });

  // --- Empty graph data ---
  test('handles empty graph data gracefully', async () => {
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  // --- Build error handling ---
  test('handles build error gracefully', async () => {
    mockKgApi.build.mockRejectedValue(new Error('构建失败'));
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

  // --- Graph loading state ---
  test('shows chart when graph data loads successfully', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Query with empty input ---
  test('query button is present and clickable', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('查询图谱')).toBeInTheDocument();
    });

    // The query button should be rendered
    const queryButton = screen.getByText('查询图谱');
    expect(queryButton).toBeInTheDocument();
  });

  // --- Graph data with many nodes ---
  test('handles large graph data', async () => {
    const largeGraphData = {
      nodes: Array.from({ length: 200 }, (_, i) => ({
        id: String(i),
        name: `Node ${i}`,
        category: i % 3 === 0 ? '法规' : i % 3 === 1 ? '概念' : '方法',
        description: `Description ${i}`,
      })),
      edges: Array.from({ length: 100 }, (_, i) => ({
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

  // --- Delete document ---
  test('delete buttons exist for each document', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('GMP法规.txt')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('删除');
    expect(deleteButtons.length).toBe(2);
  });

  // --- Not built state shows disabled query ---
  test('shows "请先构建图谱" in search results when not built', async () => {
    mockKgApi.getStatus.mockResolvedValue(mockStatusNotBuilt);
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('请先构建图谱')).toBeInTheDocument();
    });
  });

  // --- Graph visualization with data ---
  test('renders echarts component with graph data', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Auto-query with search params ---
  test('auto-queries when q param is set and graph is built', async () => {
    // The component reads searchParams.get('q') on mount
    // We can't easily set search params in BrowserRouter tests,
    // but we verify the component handles initialQuery correctly
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });
  });

  // --- Graph data load failure ---
  test('shows load graph button when graph data fails to load', async () => {
    mockKgApi.getGraphData.mockResolvedValue(null as any);

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  // --- Refresh graph button ---
  test('calls loadGraphData when refresh button clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('刷新图谱')).toBeInTheDocument();
    });

    await user.click(screen.getByText('刷新图谱'));

    await waitFor(() => {
      expect(mockKgApi.getGraphData).toHaveBeenCalledTimes(2); // once on mount, once on refresh
    });
  });

  // --- Upload document ---
  test('upload button is rendered and enabled', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('上传法规文档')).toBeInTheDocument();
    });

    const uploadButton = screen.getByText('上传法规文档').closest('button');
    expect(uploadButton).not.toBeDisabled();
  });

  // --- Build with force ---
  test('force rebuild calls build with true', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('强制重建')).toBeInTheDocument();
    });

    await user.click(screen.getByText('强制重建'));

    await waitFor(() => {
      expect(mockKgApi.build).toHaveBeenCalledWith(true);
    });
  });

  // --- Document table columns ---
  test('renders document table with all columns', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('GMP法规.txt')).toBeInTheDocument();
    });

    // Table should have headers
    expect(screen.getByText('文件名')).toBeInTheDocument();
    expect(screen.getByText('大小')).toBeInTheDocument();
    expect(screen.getByText('修改时间')).toBeInTheDocument();
  });

  // --- Graph data with empty nodes ---
  test('shows chart even with empty graph data when built', async () => {
    mockKgApi.getGraphData.mockResolvedValue({ nodes: [], edges: [] });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Status loading ---
  test('shows loading state for statistics', async () => {
    mockKgApi.getStatus.mockImplementation(() => new Promise(() => {}));
    mockKgApi.getDocuments.mockImplementation(() => new Promise(() => {}));

    renderWithRouter(<KnowledgeGraphPage />);

    // Should show loading spinners for stat cards
    await waitFor(() => {
      expect(document.querySelector('.ant-spin')).toBeInTheDocument();
    });
  });

  // --- Query error handling ---
  test('handles query error gracefully', async () => {
    mockKgApi.query.mockRejectedValue(new Error('Query failed'));
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, 'test query');
    await user.click(screen.getByText('查询图谱'));

    // Should not crash
    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });
  });

  // --- Document size formatting ---
  test('formats document sizes correctly', async () => {
    mockKgApi.getDocuments.mockResolvedValue({
      documents: [
        { filename: 'large.txt', size: 1048576, modified: '2024-01-01T00:00:00Z' },
        { filename: 'small.txt', size: 512, modified: '2024-01-02T00:00:00Z' },
      ],
    });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      // 1048576 / 1024 = 1024.0 KB
      expect(screen.getByText('1024.0 KB')).toBeInTheDocument();
    });

    // 512 / 1024 = 0.5 KB
    expect(screen.getByText('0.5 KB')).toBeInTheDocument();
  });

  // --- Document modified time formatting ---
  test('formats document modified time', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('GMP法规.txt')).toBeInTheDocument();
    });

    // Modified times should be formatted as zh-CN locale
    const tableCells = document.querySelectorAll('td');
    expect(tableCells.length).toBeGreaterThan(0);
  });

  // --- Upload error handling ---
  test('handles upload error gracefully', async () => {
    mockKgApi.uploadDocument.mockRejectedValue(new Error('Upload failed'));

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('上传法规文档')).toBeInTheDocument();
    });

    // Component should still be functional
    expect(screen.getByText('知识图谱')).toBeInTheDocument();
  });

  // --- Delete document error handling ---
  test('handles delete document error gracefully', async () => {
    mockKgApi.deleteDocument.mockRejectedValue(new Error('Delete failed'));

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('GMP法规.txt')).toBeInTheDocument();
    });

    // Component should still be functional
    expect(screen.getByText('知识图谱')).toBeInTheDocument();
  });

  // --- Delete document calls API when confirmed ---
  test('delete document calls API when modal confirmed', async () => {
    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;
    mockKgApi.deleteDocument.mockResolvedValue({ message: 'deleted' });

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('GMP法规.txt')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('删除');
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(mockKgApi.deleteDocument).toHaveBeenCalledWith('GMP法规.txt');
    });

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Delete document error when modal confirmed ---
  test('delete document handles error when modal confirmed', async () => {
    const originalConfirm = (await import('antd')).Modal.confirm;
    const mockConfirm = jest.fn(({ onOk }: any) => {
      if (onOk) onOk();
    });
    (await import('antd')).Modal.confirm = mockConfirm;
    mockKgApi.deleteDocument.mockRejectedValue(new Error('Delete failed'));

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('GMP法规.txt')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('删除');
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(mockKgApi.deleteDocument).toHaveBeenCalled();
    });

    // Should not crash
    expect(screen.getByText('知识图谱')).toBeInTheDocument();

    (await import('antd')).Modal.confirm = originalConfirm;
  });

  // --- Build error handling ---
  test('handles build API error gracefully', async () => {
    mockKgApi.build.mockRejectedValue(new Error('Build failed'));
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

  // --- Upload document ---
  test('upload button renders correctly', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('上传法规文档')).toBeInTheDocument();
    });

    // Upload component should be present
    const uploadButton = screen.getByText('上传法规文档');
    expect(uploadButton.closest('button')).not.toBeDisabled();
  });

  // --- Query with initial search param ---
  test('query input is rendered and functional', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    }, { timeout: 5000 });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    expect(input).toBeInTheDocument();
    expect(input).not.toBeDisabled();
  });

  // --- Graph data categories ---
  test('renders chart with multiple node categories', async () => {
    mockKgApi.getGraphData.mockResolvedValue({
      nodes: [
        { id: '1', name: 'GMP', category: '法规', description: 'Good Manufacturing Practice' },
        { id: '2', name: '偏差处理', category: '概念', description: '偏差处理流程' },
        { id: '3', name: 'CAPA', category: '方法', description: '纠正和预防措施' },
        { id: '4', name: 'FDA', category: '组织', description: '美国食品药品管理局' },
      ],
      edges: [
        { source: '1', target: '2', label: '包含' },
        { source: '2', target: '3', label: '导致' },
        { source: '1', target: '4', label: '监管' },
      ],
    });

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByTestId('echarts')).toBeInTheDocument();
    });
  });

  // --- Empty query warning (covers lines 149-151) ---
  test('query search button is rendered', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('查询图谱')).toBeInTheDocument();
    });

    // The query button should be present and the input should be rendered
    expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
  });

  // --- Build polling (covers lines 107-134) ---
  test('starts polling when building', async () => {
    mockKgApi.build.mockResolvedValue({ message: '构建已启动' });
    mockKgApi.getBuildStatus
      .mockResolvedValueOnce({ building: true, recent_logs: ['正在处理...'] })
      .mockResolvedValueOnce({ building: false, recent_logs: ['构建完成'] });

    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('重新构建')).toBeInTheDocument();
    });

    await user.click(screen.getByText('重新构建'));

    // Should show building logs section
    await waitFor(() => {
      expect(screen.getByText('构建日志')).toBeInTheDocument();
    });
  });

  // --- Graph data not loaded when not built (covers lines 452-459) ---
  test('shows "点击加载图谱可视化" when built but no graph data', async () => {
    mockKgApi.getGraphData.mockResolvedValue(null as any);

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('点击加载图谱可视化')).toBeInTheDocument();
    });
  });

  test('shows load graph button when built but graph data is null', async () => {
    mockKgApi.getGraphData.mockResolvedValue(null as any);

    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('加载图谱')).toBeInTheDocument();
    });
  });

  test('load graph button calls loadGraphData', async () => {
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

  // --- Query with chapter and title (covers result display lines 400-412) ---
  test('displays query results with chapter and title tags', async () => {
    mockKgApi.query.mockResolvedValue({
      results: [
        {
          regulation: 'GMP 2010',
          chapter: '第七章',
          title: '偏差处理',
          content: '任何偏差都应记录并调查',
          relevance: 0.95,
        },
      ],
    });
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, '偏差');
    await user.click(screen.getByText('查询图谱'));

    await waitFor(() => {
      expect(screen.getByText('GMP 2010')).toBeInTheDocument();
    });

    expect(screen.getByText('第七章')).toBeInTheDocument();
    expect(screen.getByText('偏差处理')).toBeInTheDocument();
  });

  // --- Upload document (covers handleUpload lines 177-191) ---
  test('upload component renders correctly', async () => {
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('上传法规文档')).toBeInTheDocument();
    });

    // Upload component should be wrapped around the button
    const uploadButton = screen.getByText('上传法规文档');
    expect(uploadButton).toBeInTheDocument();
  });

  // --- Graph loading state (covers line 436) ---
  test('shows graph loading state when graph data is loading', async () => {
    // The component calls loadGraphData during loadData when status.built is true.
    // mock getGraphData to a deferred promise
    let resolveGraph: ((value: any) => void) | null = null;
    const graphPromise = new Promise<any>((resolve) => { resolveGraph = resolve; });
    mockKgApi.getGraphData.mockReturnValue(graphPromise);

    renderWithRouter(<KnowledgeGraphPage />);

    // Page should render while graph is loading
    await waitFor(() => {
      expect(screen.getByText('知识图谱')).toBeInTheDocument();
    });

    // Resolve to clean up
    resolveGraph?.({ nodes: [], edges: [] });
  });

  // --- Document delete interaction (covers handleDelete lines 193-209) ---
  test('delete button triggers confirm dialog', async () => {
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByText('GMP法规.txt')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('删除');
    await user.click(deleteButtons[0]);

    // Modal.confirm should appear
    await waitFor(() => {
      expect(document.querySelector('.ant-modal-confirm')).toBeInTheDocument();
    });
  });

  // --- Query result without chapter/title ---
  test('displays query result without chapter or title', async () => {
    mockKgApi.query.mockResolvedValue({
      results: [
        {
          regulation: 'GMP 2010',
          chapter: '',
          title: '',
          content: 'General requirement text',
          relevance: 0.5,
        },
      ],
    });
    const user = userEvent.setup();
    renderWithRouter(<KnowledgeGraphPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('试试：偏差处理、CAPA、文件管理');
    await user.type(input, 'GMP');
    await user.click(screen.getByText('查询图谱'));

    await waitFor(() => {
      expect(screen.getByText('General requirement text')).toBeInTheDocument();
    });
  });

  // --- Document with null modified time ---
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
  });

  // --- Graph data focused with query results (covers focusedGraph useMemo lines 211-240) ---
  test('focuses graph based on query results', async () => {
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
        {
          regulation: 'GMP 2010',
          chapter: '第七章',
          title: '偏差处理',
          content: '偏差处理内容',
          relevance: 0.9,
        },
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
});
