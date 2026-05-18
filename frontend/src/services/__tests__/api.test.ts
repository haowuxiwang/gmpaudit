// Mock axios before any imports
export {};

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockDelete = jest.fn();
const mockPut = jest.fn();

jest.mock('axios', () => ({
  __esModule: true,
  default: {
    create: jest.fn(() => ({
      interceptors: {
        request: { use: jest.fn() },
        response: { use: jest.fn() },
      },
      get: mockGet,
      post: mockPost,
      put: mockPut,
      delete: mockDelete,
    })),
  },
}));

// Import the module after mock setup
const api = require('../api');

describe('documentApi', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('list calls GET with default pagination', () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });
    api.documentApi.list();

    expect(mockGet).toHaveBeenCalledWith('/documents/', {
      params: { page: 1, page_size: 20 },
    });
  });

  test('list calls GET with custom pagination', () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });
    api.documentApi.list(3, 50);

    expect(mockGet).toHaveBeenCalledWith('/documents/', {
      params: { page: 3, page_size: 50 },
    });
  });

  test('delete calls DELETE with id', () => {
    mockDelete.mockResolvedValue({ message: 'ok' });
    api.documentApi.delete(42);

    expect(mockDelete).toHaveBeenCalledWith('/documents/42');
  });
});

describe('auditApi', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('createTask calls POST with data', () => {
    mockPost.mockResolvedValue({});
    const data = { task_name: 'Test Task', task_type: 'deviation', document_ids: [1, 2] };
    api.auditApi.createTask(data);

    expect(mockPost).toHaveBeenCalledWith('/audit/tasks', data);
  });

  test('listTasks calls GET with optional status', () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });
    api.auditApi.listTasks('running');

    expect(mockGet).toHaveBeenCalledWith('/audit/tasks', {
      params: { status: 'running' },
    });
  });

  test('listTasks calls GET without status', () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });
    api.auditApi.listTasks();

    expect(mockGet).toHaveBeenCalledWith('/audit/tasks', {
      params: { status: undefined },
    });
  });

  test('runTask calls POST', () => {
    mockPost.mockResolvedValue({ message: 'ok' });
    api.auditApi.runTask(5);

    expect(mockPost).toHaveBeenCalledWith('/audit/tasks/5/run');
  });

  test('getDashboard calls GET', () => {
    mockGet.mockResolvedValue({});
    api.auditApi.getDashboard();

    expect(mockGet).toHaveBeenCalledWith('/audit/dashboard');
  });
});

describe('configApi', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('getAll calls GET /config/', () => {
    mockGet.mockResolvedValue([]);
    api.configApi.getAll();

    expect(mockGet).toHaveBeenCalledWith('/config/');
  });

  test('testWebhook calls POST', () => {
    mockPost.mockResolvedValue({ message: 'ok' });
    api.configApi.testWebhook();

    expect(mockPost).toHaveBeenCalledWith('/config/test-webhook');
  });
});

describe('alertsApi', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('list calls GET with optional status', () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });
    api.alertsApi.list('active');

    expect(mockGet).toHaveBeenCalledWith('/alerts/', {
      params: { status: 'active' },
    });
  });

  test('acknowledge calls PUT', () => {
    mockPut.mockResolvedValue({});
    api.alertsApi.acknowledge(1);

    expect(mockPut).toHaveBeenCalledWith('/alerts/1/acknowledge');
  });

  test('resolve calls PUT', () => {
    mockPut.mockResolvedValue({});
    api.alertsApi.resolve(2);

    expect(mockPut).toHaveBeenCalledWith('/alerts/2/resolve');
  });
});
