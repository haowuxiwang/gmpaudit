import React from 'react';
import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import KnowledgeGraphPage from '../KnowledgeGraphPage';
import { kgApi } from '../../services/api';

jest.setTimeout(15000);

jest.mock('../../services/api', () => ({
  kgApi: {
    getStatus: jest.fn().mockResolvedValue({ built: false, input_file_count: 0, file_count: 0, building: false }),
    build: jest.fn(),
    query: jest.fn(),
    getDocuments: jest.fn().mockResolvedValue({ documents: [] }),
    getBuildStatus: jest.fn().mockResolvedValue({ building: false }),
    getGraphData: jest.fn().mockResolvedValue({ nodes: [], edges: [] }),
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

describe('KnowledgeGraphPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (mockKgApi.getStatus as jest.Mock).mockResolvedValue({ built: false, input_file_count: 0, file_count: 0, building: false });
    (mockKgApi.getDocuments as jest.Mock).mockResolvedValue({ documents: [] });
    (mockKgApi.getBuildStatus as jest.Mock).mockResolvedValue({ building: false });
    (mockKgApi.getGraphData as jest.Mock).mockResolvedValue({ nodes: [], edges: [] });
  });

  test('renders without crashing', async () => {
    const { container } = renderWithRouter(<KnowledgeGraphPage />);
    expect(container).toBeTruthy();
  });
});
