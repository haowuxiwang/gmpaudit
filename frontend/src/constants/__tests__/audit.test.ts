import {
  STATUS_COLORS,
  STATUS_LABELS,
  STAGE_LABELS,
  STAGE_COLORS,
  TASK_TYPE_LABELS,
  SEVERITY_COLORS,
  DOC_STATUS_LABELS,
  DOC_STATUS_COLORS,
} from '../audit';

describe('STATUS_COLORS', () => {
  test('contains all expected status keys', () => {
    expect(STATUS_COLORS).toHaveProperty('pending');
    expect(STATUS_COLORS).toHaveProperty('running');
    expect(STATUS_COLORS).toHaveProperty('completed');
    expect(STATUS_COLORS).toHaveProperty('failed');
    expect(STATUS_COLORS).toHaveProperty('cancelled');
    expect(STATUS_COLORS).toHaveProperty('awaiting_review');
    expect(STATUS_COLORS).toHaveProperty('rejected');
  });

  test('maps statuses to valid Ant Design tag colors', () => {
    const validColors = ['default', 'processing', 'success', 'error', 'warning'];
    Object.values(STATUS_COLORS).forEach((color) => {
      expect(validColors).toContain(color);
    });
  });

  test('pending maps to default', () => {
    expect(STATUS_COLORS.pending).toBe('default');
  });

  test('running maps to processing', () => {
    expect(STATUS_COLORS.running).toBe('processing');
  });

  test('completed maps to success', () => {
    expect(STATUS_COLORS.completed).toBe('success');
  });

  test('failed maps to error', () => {
    expect(STATUS_COLORS.failed).toBe('error');
  });
});

describe('STATUS_LABELS', () => {
  test('contains all expected status keys', () => {
    expect(Object.keys(STATUS_LABELS)).toEqual(Object.keys(STATUS_COLORS));
  });

  test('all values are non-empty Chinese strings', () => {
    Object.values(STATUS_LABELS).forEach((label) => {
      expect(typeof label).toBe('string');
      expect(label.length).toBeGreaterThan(0);
    });
  });

  test('pending label is correct', () => {
    expect(STATUS_LABELS.pending).toBe('待处理');
  });

  test('completed label is correct', () => {
    expect(STATUS_LABELS.completed).toBe('已完成');
  });
});

describe('STAGE_LABELS', () => {
  test('contains pipeline stages', () => {
    expect(STAGE_LABELS).toHaveProperty('parsing');
    expect(STAGE_LABELS).toHaveProperty('regulation');
    expect(STAGE_LABELS).toHaveProperty('risk');
    expect(STAGE_LABELS).toHaveProperty('report');
  });

  test('contains lifecycle stages', () => {
    expect(STAGE_LABELS).toHaveProperty('pending');
    expect(STAGE_LABELS).toHaveProperty('completed');
    expect(STAGE_LABELS).toHaveProperty('failed');
    expect(STAGE_LABELS).toHaveProperty('cancelled');
  });

  test('all values are non-empty strings', () => {
    Object.values(STAGE_LABELS).forEach((label) => {
      expect(typeof label).toBe('string');
      expect(label.length).toBeGreaterThan(0);
    });
  });
});

describe('STAGE_COLORS', () => {
  test('contains expected stage color keys', () => {
    const expectedKeys = [
      'pending', 'queued', 'running', 'routing', 'parsing',
      'regulation', 'risk', 'report', 'completed', 'failed', 'cancelled',
    ];
    expectedKeys.forEach((key) => {
      expect(STAGE_COLORS).toHaveProperty(key);
    });
  });

  test('all values are hex color strings', () => {
    Object.values(STAGE_COLORS).forEach((color) => {
      expect(color).toMatch(/^#[0-9A-Fa-f]{6}$/);
    });
  });
});

describe('TASK_TYPE_LABELS', () => {
  test('contains expected task types', () => {
    expect(TASK_TYPE_LABELS).toHaveProperty('deviation_analysis');
    expect(TASK_TYPE_LABELS).toHaveProperty('sop_compliance');
    expect(TASK_TYPE_LABELS).toHaveProperty('consistency_check');
    expect(TASK_TYPE_LABELS).toHaveProperty('risk_assessment');
  });

  test('all values are non-empty strings', () => {
    Object.values(TASK_TYPE_LABELS).forEach((label) => {
      expect(typeof label).toBe('string');
      expect(label.length).toBeGreaterThan(0);
    });
  });
});

describe('SEVERITY_COLORS', () => {
  test('contains all severity levels', () => {
    expect(SEVERITY_COLORS).toHaveProperty('high');
    expect(SEVERITY_COLORS).toHaveProperty('critical');
    expect(SEVERITY_COLORS).toHaveProperty('medium');
    expect(SEVERITY_COLORS).toHaveProperty('low');
    expect(SEVERITY_COLORS).toHaveProperty('info');
  });

  test('high and critical map to red', () => {
    expect(SEVERITY_COLORS.high).toBe('red');
    expect(SEVERITY_COLORS.critical).toBe('red');
  });

  test('medium maps to orange', () => {
    expect(SEVERITY_COLORS.medium).toBe('orange');
  });

  test('low maps to green', () => {
    expect(SEVERITY_COLORS.low).toBe('green');
  });

  test('info maps to blue', () => {
    expect(SEVERITY_COLORS.info).toBe('blue');
  });
});

describe('DOC_STATUS_LABELS', () => {
  test('contains all document statuses', () => {
    expect(DOC_STATUS_LABELS).toHaveProperty('uploaded');
    expect(DOC_STATUS_LABELS).toHaveProperty('processing');
    expect(DOC_STATUS_LABELS).toHaveProperty('processed');
    expect(DOC_STATUS_LABELS).toHaveProperty('failed');
  });

  test('all values are non-empty strings', () => {
    Object.values(DOC_STATUS_LABELS).forEach((label) => {
      expect(typeof label).toBe('string');
      expect(label.length).toBeGreaterThan(0);
    });
  });
});

describe('DOC_STATUS_COLORS', () => {
  test('contains all DOC_STATUS_LABELS keys', () => {
    Object.keys(DOC_STATUS_LABELS).forEach((key) => {
      expect(DOC_STATUS_COLORS).toHaveProperty(key);
    });
  });

  test('maps to valid Ant Design tag colors', () => {
    const validColors = ['default', 'processing', 'success', 'error'];
    Object.values(DOC_STATUS_COLORS).forEach((color) => {
      expect(validColors).toContain(color);
    });
  });

  test('processed maps to success', () => {
    expect(DOC_STATUS_COLORS.processed).toBe('success');
  });

  test('failed maps to error', () => {
    expect(DOC_STATUS_COLORS.failed).toBe('error');
  });
});
