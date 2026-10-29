import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BrowserRouter, MemoryRouter, Route, Routes } from 'react-router-dom';
import MockInterviewSessionPage from '../MockInterviewSessionPage';
import * as clientModule from '../../api/client';

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual('../../api/client');
  return {
    ...actual,
    api: {
      get: vi.fn(),
      post: vi.fn(),
    },
  };
});

describe('MockInterviewSessionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockSessionData = {
    interview_id: 'test-interview-123',
    status: 'draft',
    provider_call_id: null,
    is_mock: true,
    simulation_disclaimer: 'Simulated mock session only.',
    candidate: {
      id: 'cand-1',
      name: 'Alice Walker',
      email: 'alice@example.com',
      phone: '+15550001111',
      consent_status: 'granted',
      consent_recorded_at: '2026-10-27T10:00:00Z',
      consent_method: 'Email Confirmation',
    },
    job: {
      id: 'job-1',
      title: 'Senior Backend Engineer',
    },
    timing: {
      elapsed_seconds: 0,
      remaining_seconds: 1800,
      duration_limit_seconds: 1800,
      is_expired: false,
      warning_triggered: false,
    },
    current_question: {
      id: 101,
      sequence_number: 1,
      text: 'Explain how you design resilient distributed message queues.',
      category: 'System Design',
      competency: 'Architecture',
      expected_evidence: 'Idempotency and dead-letter queues',
      suggested_follow_up: 'What happens during network partitions?',
    },
    progress: {
      total_questions: 3,
      questions_asked: 0,
      is_completed: false,
      awaiting_candidate_response: false,
    },
    transcripts: [],
    message: '',
  };

  it('renders explicit mock telephony disclaimer banner and session details', async () => {
    clientModule.api.get.mockResolvedValueOnce({ data: mockSessionData });

    render(
      <MemoryRouter initialEntries={['/interviews/test-interview-123/session']}>
        <Routes>
          <Route path="/interviews/:id/session" element={<MockInterviewSessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Phase 7 Mock Telephony Environment/i)).toBeInTheDocument();
      expect(screen.getByText('Alice Walker')).toBeInTheDocument();
      expect(screen.getByText('Senior Backend Engineer')).toBeInTheDocument();
      expect(screen.getByText(/MOCK SIMULATION MODE ONLY/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Start Mock Interview/i })).toBeInTheDocument();
    });
  });

  it('starts mock interview session on user click', async () => {
    clientModule.api.get.mockResolvedValueOnce({ data: mockSessionData });
    clientModule.api.post.mockResolvedValueOnce({
      data: {
        ...mockSessionData,
        status: 'in_progress',
        provider_call_id: 'mock-call-test-1234',
        progress: {
          ...mockSessionData.progress,
          awaiting_candidate_response: true,
        },
        transcripts: [
          {
            id: 1,
            sequence_number: 1,
            speaker: 'ai',
            text: 'Welcome to your interview.',
            timestamp: '2026-10-27T10:01:00Z',
          },
        ],
      },
    });

    render(
      <MemoryRouter initialEntries={['/interviews/test-interview-123/session']}>
        <Routes>
          <Route path="/interviews/:id/session" element={<MockInterviewSessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Start Mock Interview/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Start Mock Interview/i }));

    await waitFor(() => {
      expect(clientModule.api.post).toHaveBeenCalledWith('/interviews/test-interview-123/start/');
      expect(screen.getByText(/Welcome to your interview/i)).toBeInTheDocument();
      expect(screen.getByText('mock-call-test-1234')).toBeInTheDocument();
    });
  });

  it('allows submitting candidate response to advance question', async () => {
    const inProgressSession = {
      ...mockSessionData,
      status: 'in_progress',
      provider_call_id: 'mock-call-test-1234',
      transcripts: [
        {
          id: 1,
          sequence_number: 1,
          speaker: 'ai',
          text: 'Question 1: Explain distributed queues.',
          timestamp: '2026-10-27T10:01:00Z',
        },
      ],
    };

    clientModule.api.get.mockResolvedValueOnce({ data: inProgressSession });
    clientModule.api.post.mockResolvedValueOnce({
      data: {
        ...inProgressSession,
        transcripts: [
          ...inProgressSession.transcripts,
          {
            id: 2,
            sequence_number: 2,
            speaker: 'candidate',
            text: 'I use Kafka with at-least-once delivery.',
            timestamp: '2026-10-27T10:02:00Z',
          },
        ],
      },
    });

    render(
      <MemoryRouter initialEntries={['/interviews/test-interview-123/session']}>
        <Routes>
          <Route path="/interviews/:id/session" element={<MockInterviewSessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Type simulated candidate response here/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Type simulated candidate response here/i), {
      target: { value: 'I use Kafka with at-least-once delivery.' },
    });

    fireEvent.click(screen.getByRole('button', { name: /Submit Response & Next Question/i }));

    await waitFor(() => {
      expect(clientModule.api.post).toHaveBeenCalledWith(
        '/interviews/test-interview-123/advance/',
        expect.objectContaining({
          simulated_response: 'I use Kafka with at-least-once delivery.',
        })
      );
      expect(screen.getByText(/I use Kafka with at-least-once delivery/i)).toBeInTheDocument();
    });
  });
});
