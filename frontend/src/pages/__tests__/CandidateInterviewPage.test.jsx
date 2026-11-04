import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CandidateInterviewPage from '../CandidateInterviewPage';

describe('CandidateInterviewPage', () => {
  const mockSession = {
    interview_id: 'test-interview-id',
    status: 'draft',
    candidate: {
      name: 'Priya Sharma',
      consent_status: 'pending',
    },
    job: {
      title: 'Senior SRE',
      description: 'Distributed Kubernetes reliability.',
    },
    timing: {
      elapsed_seconds: 0,
      remaining_seconds: 1800,
    },
    disclosure: {
      ai_interviewer: true,
      duration_limit_minutes: 30,
    },
    transcripts: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
    // Mock navigator.mediaDevices
    Object.defineProperty(navigator, 'mediaDevices', {
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: vi.fn() }],
        }),
      },
      writable: true,
      configurable: true,
    });
    // Mock MediaRecorder
    global.MediaRecorder = vi.fn().mockImplementation(() => ({
      start: vi.fn(),
      stop: vi.fn(),
      ondataavailable: vi.fn(),
      onstop: vi.fn(),
    }));
    global.MediaRecorder.isTypeSupported = vi.fn().mockReturnValue(true);
    // Mock Audio
    global.Audio = vi.fn().mockImplementation(() => ({
      play: vi.fn().mockResolvedValue(),
      pause: vi.fn(),
      onended: vi.fn(),
      onerror: vi.fn(),
    }));
  });

  it('renders missing token error if token query parameter is absent', async () => {
    render(
      <MemoryRouter initialEntries={['/interview/session']}>
        <Routes>
          <Route path="/interview/session" element={<CandidateInterviewPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText(/Missing interview access token/i)).toBeInTheDocument();
  });

  it('loads candidate session and displays consent disclosure', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockSession,
    });

    render(
      <MemoryRouter initialEntries={['/interview/session?token=valid-test-token']}>
        <Routes>
          <Route path="/interview/session" element={<CandidateInterviewPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText(/Interview Overview & Consent Disclosure/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Priya Sharma/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Senior SRE/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /Grant Consent & Enter Interview/i })).toBeDisabled();
  });

  it('enables start button when consent checkbox is toggled', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockSession,
    });

    render(
      <MemoryRouter initialEntries={['/interview/session?token=valid-test-token']}>
        <Routes>
          <Route path="/interview/session" element={<CandidateInterviewPage />} />
        </Routes>
      </MemoryRouter>
    );

    const checkbox = await screen.findByRole('checkbox');
    expect(checkbox).not.toBeChecked();

    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();

    const submitBtn = screen.getByRole('button', { name: /Grant Consent & Enter Interview/i });
    expect(submitBtn).not.toBeDisabled();
  });

  it('submits consent and enters active interview screen', async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockSession,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'granted' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          current_message: 'Welcome Priya. Let us begin.',
          session_state: { status: 'in_progress' },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        blob: async () => new Blob(['dummy'], { type: 'audio/wav' }),
      });

    render(
      <MemoryRouter initialEntries={['/interview/session?token=valid-test-token']}>
        <Routes>
          <Route path="/interview/session" element={<CandidateInterviewPage />} />
        </Routes>
      </MemoryRouter>
    );

    const checkbox = await screen.findByRole('checkbox');
    fireEvent.click(checkbox);

    const submitBtn = screen.getByRole('button', { name: /Grant Consent & Enter Interview/i });
    fireEvent.click(submitBtn);

    expect(await screen.findByText(/Welcome Priya. Let us begin./i)).toBeInTheDocument();
    expect(screen.getByText(/Start Speaking/i)).toBeInTheDocument();
  });
});

