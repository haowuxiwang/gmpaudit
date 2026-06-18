// Mock axios before any imports
export {};

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockDelete = jest.fn();
const mockPut = jest.fn();
let responseInterceptor: ((response: any) => any) | undefined;
let errorInterceptor: ((error: any) => any) | undefined;

jest.mock('axios', () => ({
  __esModule: true,
  default: {
    create: jest.fn(() => ({
      interceptors: {
        request: { use: jest.fn() },
        response: {
          use: jest.fn((success: any, error: any) => {
            responseInterceptor = success;
            errorInterceptor = error;
          }),
        },
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

describe('reportApi', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('list calls GET /reports/ with task_id param', () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });
    api.reportApi.list(5);

    expect(mockGet).toHaveBeenCalledWith('/reports/', {
      params: { task_id: 5 },
    });
  });

  test('list calls GET /reports/ without task_id', () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });
    api.reportApi.list();

    expect(mockGet).toHaveBeenCalledWith('/reports/', {
      params: { task_id: undefined },
    });
  });

  test('get calls GET /reports/:id', () => {
    mockGet.mockResolvedValue({ id: 1, title: 'Test Report' });
    api.reportApi.get(1);

    expect(mockGet).toHaveBeenCalledWith('/reports/1');
  });

  test('exportPdf calls GET /reports/:id/export/pdf with blob responseType', () => {
    mockGet.mockResolvedValue(new Blob());
    api.reportApi.exportPdf(3);

    expect(mockGet).toHaveBeenCalledWith('/reports/3/export/pdf', {
      responseType: 'blob',
    });
  });
});

describe('agentAuditApi', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('run calls POST /agent-audit/run with request data', () => {
    mockPost.mockResolvedValue({ task_id: 1, status: 'pending', message: 'ok' });
    const data = { document_id: 10, audit_type: 'deviation' as const, focus: 'test focus' };
    api.agentAuditApi.run(data);

    expect(mockPost).toHaveBeenCalledWith('/agent-audit/run', data);
  });

  test('run works with minimal request data', () => {
    mockPost.mockResolvedValue({ task_id: 2, status: 'pending', message: 'ok' });
    const data = { document_id: 5, audit_type: 'sop' as const };
    api.agentAuditApi.run(data);

    expect(mockPost).toHaveBeenCalledWith('/agent-audit/run', data);
  });
});

describe('kgApi', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('getStatus calls GET /kg/status', () => {
    mockGet.mockResolvedValue({ built: true, file_count: 5 });
    api.kgApi.getStatus();

    expect(mockGet).toHaveBeenCalledWith('/kg/status');
  });

  test('build calls POST /kg/build with force=false by default', () => {
    mockPost.mockResolvedValue({ message: 'started' });
    api.kgApi.build();

    expect(mockPost).toHaveBeenCalledWith('/kg/build', null, {
      params: { force: false },
    });
  });

  test('build calls POST /kg/build with force=true', () => {
    mockPost.mockResolvedValue({ message: 'started' });
    api.kgApi.build(true);

    expect(mockPost).toHaveBeenCalledWith('/kg/build', null, {
      params: { force: true },
    });
  });

  test('getBuildStatus calls GET /kg/build-status', () => {
    mockGet.mockResolvedValue({ building: false });
    api.kgApi.getBuildStatus();

    expect(mockGet).toHaveBeenCalledWith('/kg/build-status');
  });

  test('query calls POST /kg/query with default method', () => {
    mockPost.mockResolvedValue({ results: [] });
    api.kgApi.query('what is GMP?');

    expect(mockPost).toHaveBeenCalledWith(
      '/kg/query',
      { query: 'what is GMP?', method: 'local' },
      { timeout: 120000 },
    );
  });

  test('query calls POST /kg/query with custom method', () => {
    mockPost.mockResolvedValue({ results: [] });
    api.kgApi.query('test query', 'global');

    expect(mockPost).toHaveBeenCalledWith(
      '/kg/query',
      { query: 'test query', method: 'global' },
      { timeout: 120000 },
    );
  });

  test('getDocuments calls GET /kg/documents', () => {
    mockGet.mockResolvedValue({ documents: [] });
    api.kgApi.getDocuments();

    expect(mockGet).toHaveBeenCalledWith('/kg/documents');
  });

  test('getGraphData calls GET /kg/graph', () => {
    mockGet.mockResolvedValue({ nodes: [], edges: [] });
    api.kgApi.getGraphData();

    expect(mockGet).toHaveBeenCalledWith('/kg/graph');
  });

  test('uploadDocument calls POST /kg/documents/upload with FormData', () => {
    mockPost.mockResolvedValue({ message: 'ok', filename: 'test.txt' });
    const file = new File(['content'], 'test.txt', { type: 'text/plain' });
    api.kgApi.uploadDocument(file);

    expect(mockPost).toHaveBeenCalledWith('/kg/documents/upload', expect.any(FormData));
  });

  test('deleteDocument calls DELETE /kg/documents/:filename', () => {
    mockDelete.mockResolvedValue({ message: 'deleted' });
    api.kgApi.deleteDocument('regulation.txt');

    expect(mockDelete).toHaveBeenCalledWith('/kg/documents/regulation.txt');
  });
});

describe('documentApi extended', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('uploadBatch calls POST /documents/upload/batch with FormData', () => {
    mockPost.mockResolvedValue([]);
    const files = [
      new File(['content1'], 'file1.pdf', { type: 'application/pdf' }),
      new File(['content2'], 'file2.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }),
    ];
    api.documentApi.uploadBatch(files);

    expect(mockPost).toHaveBeenCalledWith('/documents/upload/batch', expect.any(FormData));
  });

  test('getById calls GET /documents/:id', () => {
    mockGet.mockResolvedValue({ id: 1, filename: 'test.pdf' });
    api.documentApi.getById(1);

    expect(mockGet).toHaveBeenCalledWith('/documents/1');
  });

  test('retryProcess calls POST /documents/:id/process', () => {
    mockPost.mockResolvedValue({ status: 'processing' });
    api.documentApi.retryProcess(5);

    expect(mockPost).toHaveBeenCalledWith('/documents/5/process');
  });
});

describe('auditApi extended', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('getTask calls GET /audit/tasks/:id', () => {
    mockGet.mockResolvedValue({ id: 1, task_name: 'test' });
    api.auditApi.getTask(1);

    expect(mockGet).toHaveBeenCalledWith('/audit/tasks/1');
  });

  test('getFindings calls GET /audit/tasks/:id/findings', () => {
    mockGet.mockResolvedValue([]);
    api.auditApi.getFindings(3);

    expect(mockGet).toHaveBeenCalledWith('/audit/tasks/3/findings');
  });

  test('approveTask calls POST with comment', () => {
    mockPost.mockResolvedValue({ status: 'approved' });
    api.auditApi.approveTask(1, 'looks good');

    expect(mockPost).toHaveBeenCalledWith('/audit/tasks/1/approve', {
      comment: 'looks good',
    });
  });

  test('rejectTask calls POST with comment', () => {
    mockPost.mockResolvedValue({ status: 'rejected' });
    api.auditApi.rejectTask(2, 'needs revision');

    expect(mockPost).toHaveBeenCalledWith('/audit/tasks/2/reject', {
      comment: 'needs revision',
    });
  });

  test('cancelTask calls POST /audit/tasks/:id/cancel', () => {
    mockPost.mockResolvedValue({ status: 'cancelled' });
    api.auditApi.cancelTask(4);

    expect(mockPost).toHaveBeenCalledWith('/audit/tasks/4/cancel');
  });

  test('approveFinding calls POST with optional comment', () => {
    mockPost.mockResolvedValue({ status: 'approved', finding_id: 10 });
    api.auditApi.approveFinding(10, 'valid finding');

    expect(mockPost).toHaveBeenCalledWith('/audit/findings/10/approve', {
      comment: 'valid finding',
    });
  });

  test('approveFinding calls POST without comment', () => {
    mockPost.mockResolvedValue({ status: 'approved', finding_id: 10 });
    api.auditApi.approveFinding(10);

    expect(mockPost).toHaveBeenCalledWith('/audit/findings/10/approve', {
      comment: undefined,
    });
  });

  test('rejectFinding calls POST with optional comment', () => {
    mockPost.mockResolvedValue({ status: 'rejected', finding_id: 11 });
    api.auditApi.rejectFinding(11, 'not valid');

    expect(mockPost).toHaveBeenCalledWith('/audit/findings/11/reject', {
      comment: 'not valid',
    });
  });

  test('estimateAudit calls POST /audit/estimate', () => {
    mockPost.mockResolvedValue({
      document_count: 2,
      estimated_llm_calls: 4,
      estimated_input_tokens: 8000,
      estimated_output_tokens: 4000,
      estimated_duration_seconds: 120,
    });
    api.auditApi.estimateAudit([1, 2, 3]);

    expect(mockPost).toHaveBeenCalledWith('/audit/estimate', {
      document_ids: [1, 2, 3],
    });
  });
});

describe('configApi extended', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('getModels calls GET /config/llm/models', () => {
    mockGet.mockResolvedValue([]);
    api.configApi.getModels();

    expect(mockGet).toHaveBeenCalledWith('/config/llm/models');
  });

  test('batchUpdate calls POST /config/batch with configs', () => {
    mockPost.mockResolvedValue({ status: 'ok', updated: 2 });
    const configs = { KEY1: 'value1', KEY2: 'value2' };
    api.configApi.batchUpdate(configs);

    expect(mockPost).toHaveBeenCalledWith('/config/batch', { configs });
  });

  test('testLLM calls POST /config/test-llm with data', () => {
    mockPost.mockResolvedValue({ success: true, model_used: 'gpt-4', latency_ms: 500 });
    const data = { provider: 'openai', api_key: 'sk-test', base_url: 'https://api.openai.com/v1' };
    api.configApi.testLLM(data);

    expect(mockPost).toHaveBeenCalledWith('/config/test-llm', data);
  });
});

describe('alertsApi extended', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('list calls GET /alerts/ without status', () => {
    mockGet.mockResolvedValue({ items: [], total: 0 });
    api.alertsApi.list();

    expect(mockGet).toHaveBeenCalledWith('/alerts/', {
      params: { status: undefined },
    });
  });
});

describe('axios response interceptor', () => {
  test('unwraps response.data on success', () => {
    if (!responseInterceptor) throw new Error('responseInterceptor not captured');
    const result = responseInterceptor({ data: { items: [1, 2] } });
    expect(result).toEqual({ items: [1, 2] });
  });

  test('sets timeout message on ECONNABORTED error', () => {
    if (!errorInterceptor) throw new Error('errorInterceptor not captured');
    const error = {
      code: 'ECONNABORTED',
      message: '',
      response: undefined,
    };
    expect(() => errorInterceptor(error)).rejects.toBeDefined();
    expect(error.message).toBe('请求超时，请检查网络连接');
  });

  test('sets network error message when no response', () => {
    if (!errorInterceptor) throw new Error('errorInterceptor not captured');
    const error = {
      code: 'ERR_NETWORK',
      message: '',
      response: undefined,
    };
    expect(() => errorInterceptor(error)).rejects.toBeDefined();
    expect(error.message).toBe('网络连接失败，请检查后端服务是否运行');
  });

  test('uses detail from response data when available', () => {
    if (!errorInterceptor) throw new Error('errorInterceptor not captured');
    const error = {
      response: {
        data: {
          detail: 'Custom error detail',
        },
      },
      message: '',
    };
    expect(() => errorInterceptor(error)).rejects.toBeDefined();
    expect(error.message).toBe('Custom error detail');
  });

  test('keeps original message when response has no detail', () => {
    if (!errorInterceptor) throw new Error('errorInterceptor not captured');
    const error = {
      response: {
        data: {},
      },
      message: 'Original message',
    };
    expect(() => errorInterceptor(error)).rejects.toBeDefined();
    expect(error.message).toBe('Original message');
  });
});

describe('API_BASE_URL', () => {
  test('exports API_BASE_URL', () => {
    expect(api.API_BASE_URL).toBeDefined();
  });

  test('exports default api instance', () => {
    expect(api.default).toBeDefined();
  });
});
