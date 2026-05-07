import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export const documentApi = {
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  uploadBatch: (files: File[]) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return api.post('/documents/upload/batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  list: (page = 1, pageSize = 20) => api.get('/documents/', { params: { page, page_size: pageSize } }),
  get: (id: number) => api.get(`/documents/${id}`),
  process: (id: number) => api.post(`/documents/${id}/process`),
  delete: (id: number) => api.delete(`/documents/${id}`),
};

export const auditApi = {
  createTask: (data: { task_name: string; task_type: string; document_ids: number[] }) =>
    api.post('/audit/tasks', data),
  listTasks: (status?: string) => api.get('/audit/tasks', { params: { status } }),
  getTask: (id: number) => api.get(`/audit/tasks/${id}`),
  runTask: (id: number) => api.post(`/audit/tasks/${id}/run`),
  getFindings: (taskId: number) => api.get(`/audit/tasks/${taskId}/findings`),
  getRiskAssessment: (taskId: number) => api.get(`/audit/tasks/${taskId}/risk`),
  getDashboard: () => api.get('/audit/dashboard'),
};

export const reportApi = {
  list: (taskId?: number) => api.get('/reports/', { params: { task_id: taskId } }),
  generate: (taskId: number) => api.post(`/reports/generate/${taskId}`),
  get: (id: number) => api.get(`/reports/${id}`),
};

export const configApi = {
  getAll: () => api.get('/config/'),
  get: (key: string) => api.get(`/config/${key}`),
  update: (key: string, value: string) => api.put(`/config/${key}`, null, { params: { value } }),
  getAvailableModels: () => api.get('/config/llm/models'),
};

export const authApi = {
  getFeishuLoginUrl: () => api.get('/auth/feishu/login'),
  handleCallback: (code: string, state: string) =>
    api.get('/auth/feishu/callback', { params: { code, state } }),
  getMe: () => api.get('/auth/me'),
};

export const alertsApi = {
  list: (status?: string) => api.get('/alerts/', { params: { status } }),
  acknowledge: (id: number) => api.put(`/alerts/${id}/acknowledge`),
  resolve: (id: number) => api.put(`/alerts/${id}/resolve`),
};

export default api;
