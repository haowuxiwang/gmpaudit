export interface Document {
  id: number;
  filename: string;
  file_type: string;
  process_status: 'uploaded' | 'processing' | 'processed' | 'failed';
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditTask {
  id: number;
  task_name: string;
  task_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  document_ids: number[];
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface Report {
  id: number;
  task_id: number;
  report_type: string;
  title: string;
  content: string;
  created_at: string;
}

export interface RiskAlert {
  id: number;
  finding_id: number;
  alert_level: 'low' | 'medium' | 'high' | 'critical';
  status: 'active' | 'resolved';
  created_at: string;
  resolved_at?: string;
}

export interface KGStatus {
  built: boolean;
  file_count: number;
  last_modified: string | null;
  input_file_count: number;
  building: boolean;
}

export interface KGDocument {
  filename: string;
  size: number;
  modified: string;
}

export interface KGQueryResult {
  results: Array<{
    regulation: string;
    chapter: string;
    title: string;
    content: string;
    relevance: number;
  }>;
}

export interface AgentAuditRequest {
  document_id: number;
  audit_type: 'deviation' | 'sop' | 'change_control';
  focus?: string;
}

export interface AgentAuditResponse {
  task_id: number;
  status: string;
  message: string;
}

export interface AgentAuditStatus {
  task_id: number;
  status: string;
  progress: number;
  findings: Finding[];
  report: Report | null;
  error?: string;
}

export interface Finding {
  id: number;
  task_id: number;
  finding_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  regulation_ref?: string;
  created_at: string;
}

export interface DashboardData {
  total_tasks: number;
  task_counts: Record<string, number>;
  severity_counts: Record<string, number>;
}

export interface GraphNode {
  id: string;
  name: string;
  category: string;
  description?: string;
  symbolSize?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ConfigItem {
  config_key: string;
  config_value: string;
  config_type: string;
}
