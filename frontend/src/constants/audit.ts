export const STATUS_COLORS: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
};

export const STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  running: '进行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

export const STAGE_LABELS: Record<string, string> = {
  pending: '等待执行',
  queued: '排队中',
  running: '执行中',
  parsing: '文档解析',
  regulation: '法规匹配',
  risk: '风险评估',
  report: '报告生成',
  completed: '已完成',
  failed: '执行失败',
  cancelled: '已取消',
};

export const STAGE_COLORS: Record<string, string> = {
  pending: '#D1D5DB',
  queued: '#93C5FD',
  running: '#3B82F6',
  parsing: '#8B5CF6',
  regulation: '#F59E0B',
  risk: '#EF4444',
  report: '#10B981',
  completed: '#10B981',
  failed: '#DC2626',
  cancelled: '#9CA3AF',
};

export const TASK_TYPE_LABELS: Record<string, string> = {
  deviation_analysis: '偏差分析',
  sop_compliance: 'SOP 合规',
  consistency_check: '变更控制一致性',
  risk_assessment: '风险评估',
};

export const SEVERITY_COLORS: Record<string, string> = {
  high: 'red',
  critical: 'red',
  medium: 'orange',
  low: 'green',
  info: 'blue',
};

export const DOC_STATUS_LABELS: Record<string, string> = {
  uploaded: '已上传',
  processing: '处理中',
  processed: '已处理',
  failed: '处理失败',
};
