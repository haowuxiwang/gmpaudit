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
  AgentAuditStatus,
  DashboardData,
  GraphData,
  ConfigItem,
} from '../types/api';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => Promise.reject(error)
);

export const documentApi = {
  uploadBatch: (files: File[]) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return api.post('/documents/upload/batch', formData) as Promise<{ message: string }>;
  },
  list: (page = 1, pageSize = 20) =>
    api.get('/documents/', { params: { page, page_size: pageSize } }) as Promise<PaginatedResponse<Document>>,
  delete: (id: number) => api.delete(`/documents/${id}`) as Promise<{ message: string }>,
};

export const auditApi = {
  createTask: (data: { task_name: string; task_type: string; document_ids: number[] }) =>
    api.post('/audit/tasks', data) as Promise<AuditTask>,
  listTasks: (status?: string) =>
    api.get('/audit/tasks', { params: { status } }) as Promise<PaginatedResponse<AuditTask>>,
  getTask: (id: number) => api.get(`/audit/tasks/${id}`) as Promise<AuditTask>,
  getFindings: (id: number) => api.get(`/audit/tasks/${id}/findings`) as Promise<Finding[]>,
  runTask: (id: number) => api.post(`/audit/tasks/${id}/run`) as Promise<{ status: string; task_id: number }>,
  getDashboard: () => api.get('/audit/dashboard') as Promise<DashboardData>,
};

export const agentAuditApi = {
  run: (data: AgentAuditRequest) =>
    api.post('/agent-audit/run', data) as Promise<AgentAuditResponse>,
  getStatus: (taskId: number) =>
    api.get(`/agent-audit/status/${taskId}`) as Promise<AgentAuditStatus>,
};

export const reportApi = {
  list: (taskId?: number) =>
    api.get('/reports/', { params: { task_id: taskId } }) as Promise<PaginatedResponse<Report>>,
  get: (id: number) => api.get(`/reports/${id}`) as Promise<Report>,
  exportMarkdown: (id: number) =>
    api.get(`/reports/${id}`, { responseType: 'blob' }) as Promise<Blob>,
};

export const configApi = {
  getAll: () => api.get('/config/') as Promise<ConfigItem[]>,
  batchUpdate: (configs: Record<string, string>) =>
    api.post('/config/batch', { configs }) as Promise<{ message: string }>,
  testWebhook: () => api.post('/config/test-webhook') as Promise<{ message: string }>,
};

export const alertsApi = {
  list: (status?: string) =>
    api.get('/alerts/', { params: { status } }) as Promise<PaginatedResponse<RiskAlert>>,
  acknowledge: (id: number) => api.put(`/alerts/${id}/acknowledge`) as Promise<RiskAlert>,
  resolve: (id: number) => api.put(`/alerts/${id}/resolve`) as Promise<RiskAlert>,
};

export const kgApi = {
  getStatus: () => api.get('/kg/status') as Promise<KGStatus>,
  build: (force = false) => api.post('/kg/build', null, { params: { force } }) as Promise<{ message: string }>,
  getBuildStatus: () => api.get('/kg/build-status') as Promise<KGBuildStatus>,
  query: (query: string, method = 'local') =>
    api.post('/kg/query', { query, method }) as Promise<KGQueryResult>,
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
