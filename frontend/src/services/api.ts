import axios from 'axios';
import type {
  Document,
  PaginatedResponse,
  AuditTask,
  Report,
  RiskAlert,
  Finding,
  KGStatus,
  KGDocument,
  KGBuildStatus,
  KGQueryResult,
  AgentAuditRequest,
  AgentAuditResponse,
  DashboardData,
  GraphData,
  ConfigMap,
  LLMModel,
} from '../types/api';

export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '/api';

// Session API token (fetched on first request, included in all subsequent requests)
let _apiToken = '';

export async function fetchApiToken(): Promise<string> {
  if (_apiToken) return _apiToken;
  try {
    const resp = await axios.get(`${API_BASE_URL}/auth/token`, { timeout: 5000 });
    _apiToken = resp.data?.token || '';
  } catch {
    // Token endpoint may not be available (e.g., during tests)
  }
  return _apiToken;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

// Add auth token to all requests
api.interceptors.request.use((config) => {
  if (_apiToken) {
    config.headers.Authorization = `Bearer ${_apiToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (!error.response) {
      // Network error or timeout
      if (error.code === 'ECONNABORTED') {
        error.message = '请求超时，请检查网络连接';
      } else {
        error.message = '网络连接失败，请检查后端服务是否运行';
      }
    } else {
      const detail = error?.response?.data?.detail;
      if (detail) {
        error.message = detail;
      }
    }
    return Promise.reject(error);
  }
);

export const documentApi = {
  uploadBatch: (files: File[]) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return api.post('/documents/upload/batch', formData) as Promise<Document[]>;
  },
  list: (page = 1, pageSize = 20) =>
    api.get('/documents/', { params: { page, page_size: pageSize } }) as Promise<PaginatedResponse<Document>>,
  getById: (id: number) => api.get(`/documents/${id}`) as Promise<Document>,
  delete: (id: number) => api.delete(`/documents/${id}`) as Promise<{ message: string }>,
  retryProcess: (id: number) => api.post(`/documents/${id}/process`) as Promise<{ status: string }>,
};

export const auditApi = {
  createTask: (data: { task_name: string; task_type: string; document_ids: number[] }) =>
    api.post('/audit/tasks', data) as Promise<Pick<AuditTask, 'id' | 'task_name' | 'status'>>,
  listTasks: (status?: string) =>
    api.get('/audit/tasks', { params: { status } }) as Promise<PaginatedResponse<AuditTask>>,
  getTask: (id: number) => api.get(`/audit/tasks/${id}`) as Promise<AuditTask>,
  getFindings: (id: number) => api.get(`/audit/tasks/${id}/findings`) as Promise<Finding[]>,
  runTask: (id: number) => api.post(`/audit/tasks/${id}/run`) as Promise<{ status: string; task_id: number }>,
  approveTask: (id: number, comment: string) =>
    api.post(`/audit/tasks/${id}/approve`, { comment }) as Promise<{ status: string; task_id: number }>,
  rejectTask: (id: number, comment: string) =>
    api.post(`/audit/tasks/${id}/reject`, { comment }) as Promise<{ status: string; task_id: number }>,
  cancelTask: (id: number) =>
    api.post(`/audit/tasks/${id}/cancel`) as Promise<{ status: string; task_id: number }>,
  getDashboard: () => api.get('/audit/dashboard') as Promise<DashboardData>,
  approveFinding: (findingId: number, comment?: string) =>
    api.post(`/audit/findings/${findingId}/approve`, { comment }) as Promise<{ status: string; finding_id: number }>,
  rejectFinding: (findingId: number, comment?: string) =>
    api.post(`/audit/findings/${findingId}/reject`, { comment }) as Promise<{ status: string; finding_id: number }>,
  estimateAudit: (documentIds: number[]) =>
    api.post('/audit/estimate', { document_ids: documentIds }) as Promise<{
      document_count: number;
      estimated_llm_calls: number;
      estimated_input_tokens: number;
      estimated_output_tokens: number;
      estimated_duration_seconds: number;
    }>,
};

export const agentAuditApi = {
  run: (data: AgentAuditRequest) =>
    api.post('/agent-audit/run', data) as Promise<AgentAuditResponse>,
};

export const reportApi = {
  list: (taskId?: number) =>
    api.get('/reports/', { params: { task_id: taskId } }) as Promise<PaginatedResponse<Report>>,
  get: (id: number) => api.get(`/reports/${id}`) as Promise<Report>,
  exportPdf: (id: number) =>
    api.get(`/reports/${id}/export/pdf`, { responseType: 'blob' }) as Promise<Blob>,
};

export const configApi = {
  getAll: () => api.get('/config/') as Promise<ConfigMap>,
  getModels: () => api.get('/config/llm/models') as Promise<LLMModel[]>,
  batchUpdate: (configs: Record<string, string>) =>
    api.post('/config/batch', { configs }) as Promise<{ status: string; updated: number }>,
  testWebhook: () => api.post('/config/test-webhook') as Promise<{ success: boolean; error: string | null }>,
  testLLM: (data: { provider: string; api_key: string; base_url?: string; model?: string }) =>
    api.post('/config/test-llm', data) as Promise<{ success: boolean; model_used?: string; latency_ms?: number; error?: string | null }>,
};

export const alertsApi = {
  list: (status?: string) =>
    api.get('/alerts/', { params: { status } }) as Promise<PaginatedResponse<RiskAlert>>,
  acknowledge: (id: number) => api.put(`/alerts/${id}/acknowledge`) as Promise<{ status: string }>,
  resolve: (id: number) => api.put(`/alerts/${id}/resolve`) as Promise<{ status: string }>,
};

export const kgApi = {
  getStatus: () => api.get('/kg/status') as Promise<KGStatus>,
  build: (force = false) => api.post('/kg/build', null, { params: { force } }) as Promise<{ message: string }>,
  getBuildStatus: () => api.get('/kg/build-status') as Promise<KGBuildStatus>,
  query: (query: string, method = 'local') =>
    api.post('/kg/query', { query, method }, { timeout: 120000 }) as Promise<KGQueryResult>,
  getDocuments: () => api.get('/kg/documents') as Promise<{ documents: KGDocument[] }>,
  getGraphData: () => api.get('/kg/graph') as Promise<GraphData>,
  uploadDocument: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/kg/documents/upload', formData) as Promise<{ message: string; filename: string }>;
  },
  deleteDocument: (filename: string) =>
    api.delete(`/kg/documents/${filename}`) as Promise<{ message: string }>,
};

export default api;
