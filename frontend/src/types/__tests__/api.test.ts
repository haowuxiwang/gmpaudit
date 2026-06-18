/**
 * Type-level tests for api.ts interfaces.
 * These tests verify that the types can be used correctly at compile time
 * and that the shape of data matches expectations at runtime.
 */

import type {
  Document,
  PaginatedResponse,
  TaskEvent,
  AgentThinkingEvent,
  TaskDocumentStatus,
  AuditTask,
  Report,
  RiskAlert,
  KGStatus,
  KGDocument,
  KGBuildStatus,
  KGQueryResult,
  AgentAuditRequest,
  AgentAuditResponse,
  Finding,
  DashboardData,
  GraphNode,
  GraphEdge,
  GraphData,
  ConfigItem,
  ConfigMap,
  LLMModel,
} from '../api';

describe('Document type', () => {
  test('can construct a valid Document', () => {
    const doc: Document = {
      id: 1,
      filename: 'test.pdf',
      file_type: 'pdf',
      process_status: 'processed',
    };
    expect(doc.id).toBe(1);
    expect(doc.filename).toBe('test.pdf');
    expect(doc.process_status).toBe('processed');
  });

  test('process_status accepts all valid values', () => {
    const statuses: Document['process_status'][] = ['uploaded', 'processing', 'processed', 'failed'];
    statuses.forEach((s) => {
      expect(['uploaded', 'processing', 'processed', 'failed']).toContain(s);
    });
  });

  test('supports optional fields', () => {
    const doc: Document = {
      id: 2,
      filename: 'test.docx',
      file_type: 'docx',
      process_status: 'uploaded',
      file_size: 1024,
      created_at: '2024-01-01T00:00:00Z',
      content_text: 'some text',
      doc_metadata: { error: 'some error' },
    };
    expect(doc.file_size).toBe(1024);
    expect(doc.doc_metadata?.error).toBe('some error');
  });
});

describe('PaginatedResponse type', () => {
  test('can construct with Document items', () => {
    const resp: PaginatedResponse<Document> = {
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    };
    expect(resp.items).toEqual([]);
    expect(resp.total).toBe(0);
  });
});

describe('TaskEvent type', () => {
  test('can construct a valid TaskEvent', () => {
    const event: TaskEvent = {
      time: '2024-01-01T00:00:00Z',
      stage: 'parsing',
      level: 'info',
      message: 'Document parsed',
    };
    expect(event.level).toBe('info');
  });

  test('level accepts warning and error', () => {
    const warn: TaskEvent['level'] = 'warning';
    const err: TaskEvent['level'] = 'error';
    expect(warn).toBe('warning');
    expect(err).toBe('error');
  });
});

describe('AgentThinkingEvent type', () => {
  test('can construct with required fields', () => {
    const event: AgentThinkingEvent = {
      node: 'regulation_expert',
      status: 'started',
      message: 'Starting regulation analysis',
    };
    expect(event.node).toBe('regulation_expert');
  });

  test('stage is optional', () => {
    const event: AgentThinkingEvent = {
      node: 'risk_assessor',
      status: 'completed',
      message: 'Done',
      stage: 'risk',
    };
    expect(event.stage).toBe('risk');
  });
});

describe('TaskDocumentStatus type', () => {
  test('can construct a valid instance', () => {
    const status: TaskDocumentStatus = {
      document_id: 1,
      filename: 'test.pdf',
      status: 'completed',
      findings_count: 3,
      risk_level: 'high',
    };
    expect(status.findings_count).toBe(3);
  });

  test('report_path is optional', () => {
    const status: TaskDocumentStatus = {
      document_id: 1,
      filename: 'test.pdf',
      status: 'completed',
      findings_count: 0,
      risk_level: 'low',
      report_path: '/reports/1.pdf',
    };
    expect(status.report_path).toBe('/reports/1.pdf');
  });
});

describe('AuditTask type', () => {
  test('can construct with required fields', () => {
    const task: AuditTask = {
      id: 1,
      task_name: 'Test Task',
      task_type: 'deviation',
      status: 'pending',
      progress: 0,
    };
    expect(task.status).toBe('pending');
  });

  test('status accepts all valid values', () => {
    const statuses: AuditTask['status'][] = [
      'pending', 'running', 'awaiting_review', 'rejected',
      'cancelled', 'completed', 'failed',
    ];
    expect(statuses).toHaveLength(7);
  });

  test('supports optional fields', () => {
    const task: AuditTask = {
      id: 1,
      task_name: 'Test',
      task_type: 'sop',
      status: 'completed',
      progress: 100,
      stage: 'completed',
      document_ids: [1, 2],
      error_message: null,
      review_comment: 'approved',
      reviewed_at: '2024-01-01',
      auto_approve: true,
      created_at: '2024-01-01',
      started_at: '2024-01-01',
      completed_at: '2024-01-01',
      findings_count: 5,
      report_id: 10,
      events: [],
      documents: [],
    };
    expect(task.findings_count).toBe(5);
    expect(task.report_id).toBe(10);
  });
});

describe('Report type', () => {
  test('can construct with required fields', () => {
    const report: Report = {
      id: 1,
      task_id: 1,
      report_type: 'audit',
      title: 'GMP Audit Report',
      created_at: '2024-01-01T00:00:00Z',
    };
    expect(report.title).toBe('GMP Audit Report');
  });

  test('supports optional content and metadata', () => {
    const report: Report = {
      id: 1,
      task_id: 1,
      report_type: 'audit',
      title: 'Test',
      content: 'Full report content',
      created_at: '2024-01-01',
      report_metadata: {
        report_source: 'agent',
        report_mode: 'auto',
        findings_count: 5,
        task_type: 'deviation',
      },
    };
    expect(report.report_metadata?.report_source).toBe('agent');
    expect(report.report_metadata?.findings_count).toBe(5);
  });
});

describe('RiskAlert type', () => {
  test('can construct with required fields', () => {
    const alert: RiskAlert = {
      id: 1,
      finding_id: 10,
      alert_level: 'critical',
      status: 'active',
      created_at: '2024-01-01',
    };
    expect(alert.alert_level).toBe('critical');
  });

  test('alert_level accepts all valid values', () => {
    const levels: RiskAlert['alert_level'][] = ['critical', 'warning', 'info'];
    expect(levels).toHaveLength(3);
  });

  test('status accepts all valid values', () => {
    const statuses: RiskAlert['status'][] = ['active', 'acknowledged', 'resolved'];
    expect(statuses).toHaveLength(3);
  });
});

describe('KG types', () => {
  test('KGStatus can be constructed', () => {
    const status: KGStatus = {
      built: true,
      file_count: 10,
      last_modified: '2024-01-01',
      input_file_count: 5,
      building: false,
    };
    expect(status.built).toBe(true);
  });

  test('KGDocument can be constructed', () => {
    const doc: KGDocument = {
      filename: 'regulation.txt',
      size: 1024,
      modified: '2024-01-01',
    };
    expect(doc.filename).toBe('regulation.txt');
  });

  test('KGBuildStatus can be constructed', () => {
    const status: KGBuildStatus = {
      building: true,
      started_at: '2024-01-01',
      error: null,
      recent_logs: ['log line 1'],
    };
    expect(status.building).toBe(true);
  });

  test('KGQueryResult can be constructed', () => {
    const result: KGQueryResult = {
      results: [
        {
          regulation: 'GMP',
          chapter: 'Chapter 1',
          title: 'Quality Management',
          content: 'Some content',
          relevance: 0.95,
        },
      ],
    };
    expect(result.results).toHaveLength(1);
    expect(result.results[0].relevance).toBe(0.95);
  });
});

describe('AgentAudit types', () => {
  test('AgentAuditRequest can be constructed', () => {
    const req: AgentAuditRequest = {
      document_id: 1,
      audit_type: 'deviation',
    };
    expect(req.audit_type).toBe('deviation');
  });

  test('audit_type accepts all valid values', () => {
    const types: AgentAuditRequest['audit_type'][] = ['deviation', 'sop', 'change_control'];
    expect(types).toHaveLength(3);
  });

  test('focus is optional', () => {
    const req: AgentAuditRequest = {
      document_id: 1,
      audit_type: 'sop',
      focus: 'temperature control',
    };
    expect(req.focus).toBe('temperature control');
  });

  test('AgentAuditResponse can be constructed', () => {
    const resp: AgentAuditResponse = {
      task_id: 1,
      status: 'pending',
      message: 'Audit started',
    };
    expect(resp.task_id).toBe(1);
  });
});

describe('Finding type', () => {
  test('can construct with required fields', () => {
    const finding: Finding = {
      id: 1,
      task_id: 1,
      finding_type: 'deviation',
      severity: 'high',
      title: 'Missing documentation',
      description: 'No SOP found',
      created_at: '2024-01-01',
    };
    expect(finding.severity).toBe('high');
  });

  test('severity accepts all valid values', () => {
    const levels: Finding['severity'][] = ['low', 'medium', 'high', 'info'];
    expect(levels).toHaveLength(4);
  });

  test('status accepts all valid values', () => {
    const statuses: NonNullable<Finding['status']>[] = ['pending', 'approved', 'rejected'];
    expect(statuses).toHaveLength(3);
  });

  test('supports all optional fields', () => {
    const finding: Finding = {
      id: 1,
      task_id: 1,
      finding_type: 'deviation',
      severity: 'medium',
      title: 'Test',
      description: 'Test desc',
      created_at: '2024-01-01',
      regulation_ref: 'EU GMP Annex 15',
      evidence: 'Evidence text',
      suggestion: 'Fix suggestion',
      location: 'Section 4.2',
      document_id: 5,
      status: 'approved',
      reviewer_comment: 'Looks good',
      reviewed_at: '2024-01-02',
    };
    expect(finding.regulation_ref).toBe('EU GMP Annex 15');
    expect(finding.status).toBe('approved');
  });
});

describe('DashboardData type', () => {
  test('can construct with required fields', () => {
    const data: DashboardData = {
      total_tasks: 10,
      task_counts: { pending: 3, running: 2, completed: 5 },
      severity_counts: { high: 1, medium: 3, low: 6 },
    };
    expect(data.total_tasks).toBe(10);
  });

  test('total_findings is optional', () => {
    const data: DashboardData = {
      total_tasks: 5,
      total_findings: 15,
      task_counts: {},
      severity_counts: {},
    };
    expect(data.total_findings).toBe(15);
  });
});

describe('Graph types', () => {
  test('GraphNode can be constructed', () => {
    const node: GraphNode = {
      id: '1',
      name: 'GMP',
      category: 'regulation',
      description: 'Good Manufacturing Practice',
      symbolSize: 50,
    };
    expect(node.id).toBe('1');
  });

  test('GraphEdge can be constructed', () => {
    const edge: GraphEdge = {
      source: '1',
      target: '2',
      label: 'references',
      weight: 0.8,
    };
    expect(edge.source).toBe('1');
  });

  test('GraphData can be constructed', () => {
    const data: GraphData = {
      nodes: [{ id: '1', name: 'A', category: 'x' }],
      edges: [{ source: '1', target: '2', label: 'rel' }],
    };
    expect(data.nodes).toHaveLength(1);
    expect(data.edges).toHaveLength(1);
  });
});

describe('Config types', () => {
  test('ConfigItem can be constructed', () => {
    const item: ConfigItem = {
      value: 'test-value',
      type: 'string',
      description: 'A test config',
    };
    expect(item.value).toBe('test-value');
  });

  test('ConfigMap is a record of ConfigItems', () => {
    const map: ConfigMap = {
      key1: { value: 'val1', type: 'string' },
      key2: { value: 'val2', type: 'number', description: 'desc' },
    };
    expect(map.key1.value).toBe('val1');
    expect(map.key2.description).toBe('desc');
  });

  test('LLMModel can be constructed', () => {
    const model: LLMModel = {
      id: 'openai',
      name: 'OpenAI',
      model: 'gpt-4',
      available: true,
      base_url: 'https://api.openai.com/v1',
      default_model: 'gpt-4',
      available_models: ['gpt-4', 'gpt-3.5-turbo'],
    };
    expect(model.available_models).toContain('gpt-4');
  });
});
