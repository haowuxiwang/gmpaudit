export interface Document {
  id: number;
  filename: string;
  file_type: string;
  file_size?: number;
  process_status: 'uploaded' | 'processing' | 'processed' | 'failed';
  created_at?: string;
  upload_time?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface TaskEvent {
  time: string;
  stage: string;
  level: 'info' | 'warning' | 'error';
  message: string;
}

export interface TaskDocumentStatus {
  document_id: number;
  filename: string;
  status: string;
  findings_count: number;
  risk_level: string;
  report_path?: string;
}

export interface AuditTask {
  task_id?: number;
  id: number;
  task_name: string;
  task_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  stage?: string;
  document_ids?: number[];
  error?: string | null;
  error_message?: string | null;
  created_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
  findings_count?: number;
  report_id?: number | null;
  events?: TaskEvent[];
  documents?: TaskDocumentStatus[];
}

export interface Report {
  id: number;
  task_id: number;
  report_type: string;
  title: string;
  content?: string;
  created_at: string;
  report_metadata?: {
    report_source?: string;
    report_mode?: string;
    findings_count?: number;
    task_type?: string;
  };
}

export interface RiskAlert {
  id: number;
  finding_id: number;
  alert_level: 'critical' | 'warning' | 'info';
  status: 'active' | 'acknowledged' | 'resolved';
  created_at: string;
  resolved_at?: string;
  resolved_by?: string;
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

export interface KGBuildStatus {
  building: boolean;
  started_at?: string | null;
  error?: string | null;
  recent_logs?: string[];
}

export interface KGQueryResult {
  results: Array<{
    regulation: string;
    chapter: string;
    title: string;
    content: string;
    relevance: string | number;
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

export interface AgentAuditStatus extends AuditTask {}

export interface Finding {
  id: number;
  task_id: number;
  finding_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical' | 'info';
  title: string;
  description: string;
  regulation_ref?: string;
  evidence?: string;
  suggestion?: string;
  location?: string;
  document_id?: number;
  created_at: string;
}

export interface DashboardData {
  total_tasks: number;
  total_findings?: number;
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
  weight?: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ConfigItem {
  value: string;
  type: string;
  description?: string;
}

export type ConfigMap = Record<string, ConfigItem>;
