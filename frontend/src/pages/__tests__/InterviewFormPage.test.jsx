import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import InterviewFormPage from '../InterviewFormPage';
import * as clientModule from '../../api/client';

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual('../../api/client');
  return {
    ...actual,
    api: {
      post: vi.fn(),
      get: vi.fn(),
    },
  };
});

describe('InterviewFormPage - Scheduling workflows', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    clientModule.api.get.mockImplementation((url) => {
      if (url === '/candidates/') {
        return Promise.resolve({
          data: [{ id: 'cand-1', full_name: 'Jane Doe', email: 'jane@example.com', consent_status: 'granted' }],
        });
      }
      if (url === '/jobs/') {
        return Promise.resolve({
          data: [{ id: 'job-1', title: 'Backend Engineer', is_active: true }],
        });
      }
      return Promise.reject(new Error('Unknown url'));
    });
  });

  it('renders call initiation dropdown with manual as default and hides scheduling fields', async () => {
    render(
      <BrowserRouter>
        <InterviewFormPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Call Initiation Mode/i)).toBeInTheDocument();
    });

    const initiationSelect = screen.getByLabelText(/Call Initiation Mode/i);
    expect(initiationSelect.value).toBe('manual');
    expect(screen.queryByLabelText(/Interview Date/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Interview Time/i)).not.toBeInTheDocument();
  });

  it('conditionally displays date, time, and detected timezone when scheduled mode is chosen', async () => {
    render(
      <BrowserRouter>
        <InterviewFormPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Call Initiation Mode/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Call Initiation Mode/i), {
      target: { value: 'scheduled' },
    });

    expect(screen.getByLabelText(/Interview Date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Interview Time/i)).toBeInTheDocument();
    expect(screen.getByText(/Detected Timezone:/i)).toBeInTheDocument();
  });

  it('validates that date and time must be provided and must be in the future', async () => {
    render(
      <BrowserRouter>
        <InterviewFormPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Call Initiation Mode/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Call Initiation Mode/i), {
      target: { value: 'scheduled' },
    });

    // Try submitting without date/time
    fireEvent.click(screen.getByRole('button', { name: /Create Interview Session/i }));

    await waitFor(() => {
      expect(screen.getByText(/Please select both an interview date and time for scheduled mode/i)).toBeInTheDocument();
    });

    // Enter a past date
    fireEvent.change(screen.getByLabelText(/Interview Date/i), {
      target: { value: '2020-01-01' },
    });
    fireEvent.change(screen.getByLabelText(/Interview Time/i), {
      target: { value: '10:00' },
    });

    fireEvent.click(screen.getByRole('button', { name: /Create Interview Session/i }));

    await waitFor(() => {
      expect(screen.getByText(/Scheduled interview date and time must be in the future/i)).toBeInTheDocument();
    });
  });

  it('submits scheduled_at in ISO format and timezone in payload when valid future date/time is provided', async () => {
    clientModule.api.post.mockResolvedValueOnce({
      data: { id: 'intv-123', status: 'scheduled' },
    });

    render(
      <BrowserRouter>
        <InterviewFormPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Call Initiation Mode/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Call Initiation Mode/i), {
      target: { value: 'scheduled' },
    });

    // Pick future date (2099-12-31)
    fireEvent.change(screen.getByLabelText(/Interview Date/i), {
      target: { value: '2099-12-31' },
    });
    fireEvent.change(screen.getByLabelText(/Interview Time/i), {
      target: { value: '14:30' },
    });

    fireEvent.click(screen.getByRole('button', { name: /Create Interview Session/i }));

    await waitFor(() => {
      expect(clientModule.api.post).toHaveBeenCalledTimes(1);
    });

    const callArgs = clientModule.api.post.mock.calls[0];
    expect(callArgs[0]).toBe('/interviews/');
    expect(callArgs[1].initiation_type).toBe('scheduled');
    expect(callArgs[1].scheduled_at).toMatch(/^2099-12-31T/);
    expect(callArgs[1].timezone).toBeTruthy();
  });
});

