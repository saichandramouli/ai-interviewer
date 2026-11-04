import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import CandidateInviteModal from '../../components/CandidateInviteModal';
import { api } from '../../api/client';

vi.mock('../../api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe('CandidateInviteModal', () => {
  const mockInterview = {
    id: 'intv-1234',
    candidate_name: 'John Candidate',
    job_title: 'Full Stack Engineer',
    status: 'scheduled',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders modal when open and fetches status', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        has_token: true,
        delivery_status: 'sent',
        is_valid: true,
        recipient_email: 'john@example.com',
        expires_at: '2026-11-06T10:00:00Z',
      },
    });

    render(<CandidateInviteModal interview={mockInterview} isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByText('Candidate Interview Invitation')).toBeInTheDocument();
    expect(screen.getByText(/John Candidate/)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('john@example.com')).toBeInTheDocument();
      expect(screen.getByText('SENT')).toBeInTheDocument();
      expect(screen.getByText('Active & Valid')).toBeInTheDocument();
    });
  });

  it('generates link and triggers invitation send when no token exists', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        has_token: false,
        candidate_email: 'john@example.com',
      },
    });

    api.post.mockResolvedValueOnce({
      data: {
        candidate_url: 'http://localhost/interview/session?token=mocktoken123',
        email_enqueued: true,
      },
    });

    render(<CandidateInviteModal interview={mockInterview} isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Generate & Send Invite')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Generate & Send Invite'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/interviews/intv-1234/generate-candidate-link/',
        { valid_hours: 72 }
      );
      expect(screen.getByText(/Interview link created and invitation email queued successfully!/)).toBeInTheDocument();
      expect(screen.getByDisplayValue('http://localhost/interview/session?token=mocktoken123')).toBeInTheDocument();
    });
  });

  it('resends invitation email on demand', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        has_token: true,
        delivery_status: 'failed',
        is_valid: true,
        recipient_email: 'john@example.com',
        delivery_error: 'Temporary SMTP glitch',
      },
    });

    api.post.mockResolvedValueOnce({
      data: {
        candidate_url: 'http://localhost/interview/session?token=newtoken456',
        email_delivery_status: 'pending',
      },
    });

    render(<CandidateInviteModal interview={mockInterview} isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Resend Existing Link')).toBeInTheDocument();
      expect(screen.getByText('Replace Link')).toBeInTheDocument();
      expect(screen.getByText(/Temporary SMTP glitch/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Resend Existing Link'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/interviews/intv-1234/resend-candidate-link/',
        { valid_hours: 72 }
      );
      expect(screen.getByText(/Existing invitation email enqueued successfully/)).toBeInTheDocument();
    });
  });
});

