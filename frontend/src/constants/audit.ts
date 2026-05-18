export const STATUS_COLORS: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
};

export const STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  running: '进行中',
  completed: '已完成',
  failed: '失败',
};

export const STAGE_LABELS: Record<string, string> = {
  pending: '等待执行',
  queued: '排队中',
  running: '执行中',
  parsing: '解析文档',
  risk: '风险评估',
  completed: '已完成',
  failed: '执行失败',
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
