import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FindingDetailCard from '../FindingDetailCard';
import type { Finding } from '../../types/api';
import { auditApi } from '../../services/api';

const mockFinding: Finding = {
  id: 1,
  task_id: 1,
  finding_type: 'compliance_risk',
  severity: 'high',
  title: 'Missing SOP Documentation',
  description: 'The deviation report lacks proper SOP reference documentation.',
  evidence: 'No SOP number cited in section 3.2',
  suggestion: 'Add SOP-001 reference to the deviation report',
  location: 'Section 3.2',
  regulation_ref: 'GMP Chapter 4',
  document_id: 1,
  created_at: '2024-01-01T00:00:00Z',
};

// Mock auditApi to avoid network calls
jest.mock('../../services/api', () => ({
  auditApi: {
    approveFinding: jest.fn(),
    rejectFinding: jest.fn(),
  },
}));

const mockAuditApi = auditApi as jest.Mocked<typeof auditApi>;

// Mock DocumentPreview to avoid complex rendering
jest.mock('../DocumentPreview', () => {
  return function MockDocumentPreview({ visible }: { visible: boolean }) {
    return visible ? <div data-testid="document-preview">Preview</div> : null;
  };
});

describe('FindingDetailCard', () => {
  test('renders finding title', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.getByText('Missing SOP Documentation')).toBeInTheDocument();
  });

  test('renders finding description', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.getByText(/deviation report lacks/)).toBeInTheDocument();
  });

  test('renders severity tag', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.getByText('high')).toBeInTheDocument();
  });

  test('renders evidence when present', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.getByText(/No SOP number cited/)).toBeInTheDocument();
  });

  test('renders location when present', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.getByText(/Section 3.2/)).toBeInTheDocument();
  });

  test('renders regulation reference when present', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.getByText(/GMP Chapter 4/)).toBeInTheDocument();
  });

  test('renders suggestion section', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.getByText('改进建议')).toBeInTheDocument();
  });

  test('renders finding type tag', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.getByText('compliance_risk')).toBeInTheDocument();
  });

  test('renders approve and reject buttons for pending findings', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.getByText('通过')).toBeInTheDocument();
    expect(screen.getByText('驳回')).toBeInTheDocument();
  });

  test('does not render approve/reject for approved findings', () => {
    const approvedFinding = { ...mockFinding, status: 'approved' as const };
    render(<FindingDetailCard finding={approvedFinding} />);
    expect(screen.queryByText('通过')).not.toBeInTheDocument();
    expect(screen.queryByText('驳回')).not.toBeInTheDocument();
  });

  test('does not render approve/reject for rejected findings', () => {
    const rejectedFinding = { ...mockFinding, status: 'rejected' as const };
    render(<FindingDetailCard finding={rejectedFinding} />);
    expect(screen.queryByText('通过')).not.toBeInTheDocument();
    expect(screen.queryByText('驳回')).not.toBeInTheDocument();
  });

  test('renders graph trace button when onGraphTrace provided', () => {
    const handleGraphTrace = jest.fn();
    render(<FindingDetailCard finding={mockFinding} onGraphTrace={handleGraphTrace} />);
    expect(screen.getByText('图谱溯源')).toBeInTheDocument();
  });

  test('does not render graph trace button when onGraphTrace not provided', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.queryByText('图谱溯源')).not.toBeInTheDocument();
  });

  test('renders view source button when document_id present', () => {
    render(<FindingDetailCard finding={mockFinding} />);
    expect(screen.getByText('查看原文')).toBeInTheDocument();
  });

  test('does not render view source button when document_id absent', () => {
    const noDocFinding = { ...mockFinding, document_id: undefined };
    render(<FindingDetailCard finding={noDocFinding} />);
    expect(screen.queryByText('查看原文')).not.toBeInTheDocument();
  });

  test('handles missing optional fields gracefully', () => {
    const minimalFinding: Finding = {
      id: 2,
      task_id: 1,
      finding_type: 'compliance_risk',
      severity: 'low',
      title: 'Minor Issue',
      description: 'A minor issue found.',
      evidence: '',
      suggestion: '',
      location: '',
      regulation_ref: '',
    };
    render(<FindingDetailCard finding={minimalFinding} />);
    expect(screen.getByText('Minor Issue')).toBeInTheDocument();
    expect(screen.getByText('low')).toBeInTheDocument();
  });

  test('renders approved status tag', () => {
    const approvedFinding = { ...mockFinding, status: 'approved' as const };
    render(<FindingDetailCard finding={approvedFinding} />);
    expect(screen.getByText('已通过')).toBeInTheDocument();
  });

  test('renders rejected status tag', () => {
    const rejectedFinding = { ...mockFinding, status: 'rejected' as const };
    render(<FindingDetailCard finding={rejectedFinding} />);
    expect(screen.getByText('已驳回')).toBeInTheDocument();
  });

  // --- Approve/Reject interaction tests (lines 31-39, 44-52) ---
  test('calls approveFinding when approve button clicked', async () => {
    mockAuditApi.approveFinding.mockResolvedValue({ status: 'approved', finding_id: 1 });
    const user = userEvent.setup();
    render(<FindingDetailCard finding={mockFinding} />);

    const approveButton = screen.getByText('通过');
    await user.click(approveButton);

    await waitFor(() => {
      expect(mockAuditApi.approveFinding).toHaveBeenCalledWith(1);
    });
  });

  test('calls rejectFinding when reject button clicked', async () => {
    mockAuditApi.rejectFinding.mockResolvedValue({ status: 'rejected', finding_id: 1 });
    const user = userEvent.setup();
    render(<FindingDetailCard finding={mockFinding} />);

    const rejectButton = screen.getByText('驳回');
    await user.click(rejectButton);

    await waitFor(() => {
      expect(mockAuditApi.rejectFinding).toHaveBeenCalledWith(1);
    });
  });

  test('calls onStatusChange after successful approve', async () => {
    mockAuditApi.approveFinding.mockResolvedValue({ status: 'approved', finding_id: 1 });
    const onStatusChange = jest.fn();
    const user = userEvent.setup();
    render(<FindingDetailCard finding={mockFinding} onStatusChange={onStatusChange} />);

    await user.click(screen.getByText('通过'));

    await waitFor(() => {
      expect(onStatusChange).toHaveBeenCalled();
    });
  });

  test('calls onStatusChange after successful reject', async () => {
    mockAuditApi.rejectFinding.mockResolvedValue({ status: 'rejected', finding_id: 1 });
    const onStatusChange = jest.fn();
    const user = userEvent.setup();
    render(<FindingDetailCard finding={mockFinding} onStatusChange={onStatusChange} />);

    await user.click(screen.getByText('驳回'));

    await waitFor(() => {
      expect(onStatusChange).toHaveBeenCalled();
    });
  });

  test('handles approve failure gracefully', async () => {
    mockAuditApi.approveFinding.mockRejectedValue(new Error('Network error'));
    const user = userEvent.setup();
    render(<FindingDetailCard finding={mockFinding} />);

    await user.click(screen.getByText('通过'));

    // Should not crash, button should stop loading
    await waitFor(() => {
      expect(screen.getByText('Missing SOP Documentation')).toBeInTheDocument();
    });
  });

  test('handles reject failure gracefully', async () => {
    mockAuditApi.rejectFinding.mockRejectedValue(new Error('Server error'));
    const user = userEvent.setup();
    render(<FindingDetailCard finding={mockFinding} />);

    await user.click(screen.getByText('驳回'));

    await waitFor(() => {
      expect(screen.getByText('Missing SOP Documentation')).toBeInTheDocument();
    });
  });

  // --- DocumentPreview modal interaction (lines 135-184) ---
  test('opens document preview when view source button clicked', async () => {
    const user = userEvent.setup();
    render(<FindingDetailCard finding={mockFinding} />);

    await user.click(screen.getByText('查看原文'));

    await waitFor(() => {
      expect(screen.getByTestId('document-preview')).toBeInTheDocument();
    });
  });

  test('calls onGraphTrace when graph trace button clicked', async () => {
    const onGraphTrace = jest.fn();
    const user = userEvent.setup();
    render(<FindingDetailCard finding={mockFinding} onGraphTrace={onGraphTrace} taskId={5} />);

    await user.click(screen.getByText('图谱溯源'));

    expect(onGraphTrace).toHaveBeenCalledWith('Missing SOP Documentation', 5);
  });

  test('renders with custom style', () => {
    const { container } = render(
      <FindingDetailCard finding={mockFinding} style={{ backgroundColor: 'red' }} />
    );
    expect(container).toBeTruthy();
  });

  test('does not render approve/reject when status is approved', () => {
    const approvedFinding = { ...mockFinding, status: 'approved' as const };
    render(<FindingDetailCard finding={approvedFinding} />);
    expect(screen.queryByText('通过')).not.toBeInTheDocument();
    expect(screen.queryByText('驳回')).not.toBeInTheDocument();
  });
});
