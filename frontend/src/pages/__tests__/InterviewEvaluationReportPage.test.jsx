import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import InterviewEvaluationReportPage from '../InterviewEvaluationReportPage';
import { api } from '../../api/client';

vi.mock('../../api/client', () => ({
  api: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
  },
}));

describe('InterviewEvaluationReportPage', () => {
  const mockInterviewId = 'test-intv-123';

  const mockInterviewData = {
    id: mockInterviewId,
    candidate_name: 'Jane Doe',
    candidate_email: 'jane@example.com',
    job_title: 'Senior Python Engineer',
    status: 'completed',
    started_at: '2026-11-02T10:00:00Z',
    ended_at: '2026-11-02T10:25:00Z',
  };

  const mockEvaluationData = {
    id: 'eval-1',
    overall_score: 85.0,
    competency_scores: {
      'Python & Architecture': 88.0,
      'System Design': 82.0,
    },
    strengths: ['Clear explanation of transaction management.', 'Good knowledge of concurrency.'],
    improvement_areas: ['Could provide deeper profiling examples.'],
    evidence_summary: 'Candidate demonstrated high competence across core competencies.',
    evaluation_status: 'completed',
    review_status: 'pending',
    recruiter_notes: '',
    final_decision: null,
  };

  const mockTranscriptsData = [
    { id: 1, sequence_number: 1, speaker: 'ai', text: 'Welcome Jane. Let us begin.', timestamp: '2026-11-02T10:00:05Z' },
    { id: 2, sequence_number: 2, speaker: 'candidate', text: 'Thank you! Excited to be here.', timestamp: '2026-11-02T10:00:15Z' },
  ];

  const mockQuestionsData = [
    { id: 101, sequence_number: 1, competency: 'Python & Architecture', question_text: 'Explain Django ORM transactions.', expected_evidence: 'Mentions select_for_update' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter initialEntries={[`/interviews/${mockInterviewId}/report`]}>
        <Routes>
          <Route path="/interviews/:id/report" element={<InterviewEvaluationReportPage />} />
        </Routes>
      </MemoryRouter>
    );
  };

  it('renders loading state initially', () => {
    api.get.mockImplementation(() => new Promise(() => {}));
    renderComponent();
    expect(screen.getByText(/loading candidate evaluation report/i)).toBeInTheDocument();
  });

  it('renders completed evaluation report with scores, competencies, strengths, and transcript', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/evaluation/')) return Promise.resolve({ data: mockEvaluationData });
      if (url.includes('/transcript/')) return Promise.resolve({ data: mockTranscriptsData });
      if (url.includes('/questions/')) return Promise.resolve({ data: mockQuestionsData });
      return Promise.resolve({ data: mockInterviewData });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      expect(screen.getByText(/Senior Python Engineer/i)).toBeInTheDocument();
      expect(screen.getByText('85')).toBeInTheDocument(); // Overall score
      expect(screen.getAllByText('Python & Architecture').length).toBeGreaterThan(0);
      expect(screen.getByText('88 / 100')).toBeInTheDocument();
      expect(screen.getByText(/Clear explanation of transaction management/i)).toBeInTheDocument();
      expect(screen.getByText(/Could provide deeper profiling examples/i)).toBeInTheDocument();
      expect(screen.getByText(/Welcome Jane. Let us begin./i)).toBeInTheDocument();
    });
  });

  it('submits recruiter review decision and notes', async () => {
    api.get.mockImplementation((url) => {
      if (url.includes('/evaluation/')) return Promise.resolve({ data: mockEvaluationData });
      if (url.includes('/transcript/')) return Promise.resolve({ data: mockTranscriptsData });
      if (url.includes('/questions/')) return Promise.resolve({ data: mockQuestionsData });
      return Promise.resolve({ data: mockInterviewData });
    });

    api.patch.mockResolvedValueOnce({
      data: {
        ...mockEvaluationData,
        review_status: 'reviewed',
        final_decision: 'hire',
        recruiter_notes: 'Strong hire recommendation.',
      },
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    });

    // Click 'Hire Candidate' button
    const hireButton = screen.getByRole('button', { name: /Hire Candidate/i });
    fireEvent.click(hireButton);

    // Type notes
    const notesInput = screen.getByPlaceholderText(/Add your interview observations/i);
    fireEvent.change(notesInput, { target: { value: 'Strong hire recommendation.' } });

    // Submit review
    const submitBtn = screen.getByRole('button', { name: /Submit Hiring Decision/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith(
        `/interviews/${mockInterviewId}/evaluation/review/`,
        {
          final_decision: 'hire',
          recruiter_notes: 'Strong hire recommendation.',
        }
      );
      expect(screen.getByText(/Recruiter review successfully saved!/i)).toBeInTheDocument();
    });
  });

  it('renders insufficient data state when candidate had no audio', async () => {
    const insufficientEval = {
      ...mockEvaluationData,
      overall_score: null,
      evaluation_status: 'insufficient_data',
      evidence_summary: 'No candidate audio recorded.',
    };

    api.get.mockImplementation((url) => {
      if (url.includes('/evaluation/')) return Promise.resolve({ data: insufficientEval });
      if (url.includes('/transcript/')) return Promise.resolve({ data: [] });
      if (url.includes('/questions/')) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: mockInterviewData });
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Insufficient Evidence')).toBeInTheDocument();
      expect(screen.getByText('N/A')).toBeInTheDocument();
    });
  });

  it('dispatches evaluation retry when button is clicked', async () => {
    const failedEval = {
      ...mockEvaluationData,
      evaluation_status: 'failed',
    };

    api.get.mockImplementation((url) => {
      if (url.includes('/evaluation/')) return Promise.resolve({ data: failedEval });
      if (url.includes('/transcript/')) return Promise.resolve({ data: [] });
      if (url.includes('/questions/')) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: mockInterviewData });
    });

    api.post.mockResolvedValueOnce({
      data: { evaluation_status: 'processing', message: 'Evaluation enqueued.' },
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Retry Evaluation/i)).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /Retry Evaluation/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(`/interviews/${mockInterviewId}/evaluation/retry/`);
    });
  });
});

