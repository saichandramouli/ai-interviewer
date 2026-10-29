import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import OperationsPage from '../OperationsPage';
import * as clientModule from '../../api/client';

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual('../../api/client');
  return {
    ...actual,
    api: {
      get: vi.fn(),
    },
  };
});

describe('OperationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders operations dashboard and empty state when no tasks exist', async () => {
    clientModule.api.get.mockResolvedValueOnce({
      data: {
        results: [],
        count: 0,
      },
    });

    render(
      <BrowserRouter>
        <OperationsPage />
      </BrowserRouter>
    );

    expect(screen.getByText('Asynchronous Operations')).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByText(/No operations recorded yet/i)
      ).toBeInTheDocument();
    });
  });

  it('renders operation list with badges and metadata', async () => {
    clientModule.api.get.mockResolvedValueOnce({
      data: {
        results: [
          {
            id: 'op-12345-long-uuid',
            operation_type: 'extract_resume',
            status: 'completed',
            attempt_count: 1,
            created_at: '2026-10-27T10:00:00Z',
            completed_at: '2026-10-27T10:00:05Z',
            status_message: 'Extraction successful',
          },
          {
            id: 'op-67890-long-uuid',
            operation_type: 'generate_plan',
            status: 'running',
            attempt_count: 1,
            created_at: '2026-10-27T10:05:00Z',
            completed_at: null,
            status_message: null,
          },
        ],
        count: 2,
      },
    });

    render(
      <BrowserRouter>
        <OperationsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('extract resume')).toBeInTheDocument();
      expect(screen.getByText('generate plan')).toBeInTheDocument();
      expect(screen.getByText('completed')).toBeInTheDocument();
      expect(screen.getByText('running')).toBeInTheDocument();
    });
  });
});
