import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import CandidateFormPage from '../CandidateFormPage';
import * as clientModule from '../../api/client';

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual('../../api/client');
  return {
    ...actual,
    api: {
      post: vi.fn(),
      get: vi.fn(),
      patch: vi.fn(),
    },
  };
});

describe('CandidateFormPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders form inputs for candidate creation', () => {
    render(
      <BrowserRouter>
        <CandidateFormPage />
      </BrowserRouter>
    );

    expect(screen.getByText('Add New Candidate')).toBeInTheDocument();
    expect(screen.getByLabelText(/Full Name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email Address/i)).toBeInTheDocument();
    expect(screen.getByText(/Resume Document/i)).toBeInTheDocument();
  });

  it('validates required fields before submitting', async () => {
    render(
      <BrowserRouter>
        <CandidateFormPage />
      </BrowserRouter>
    );

    const form = screen.getByRole('button', { name: /Create Candidate/i }).closest('form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText(/Name and email are required/i)).toBeInTheDocument();
    });
  });

  it('validates file extension on resume upload', async () => {
    render(
      <BrowserRouter>
        <CandidateFormPage />
      </BrowserRouter>
    );

    const file = new File(['dummy content'], 'resume.txt', { type: 'text/plain' });
    const fileInput = document.querySelector('input[type="file"]');

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/Allowed file formats are \.pdf and \.docx only/i)).toBeInTheDocument();
    });
  });

  it('submits valid candidate data via FormData', async () => {
    clientModule.api.post.mockResolvedValueOnce({
      data: {
        id: 'mock-cand-id',
        full_name: 'Jane Doe',
        email: 'jane@example.com',
      },
    });

    render(
      <BrowserRouter>
        <CandidateFormPage />
      </BrowserRouter>
    );

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'Jane Doe' },
    });
    fireEvent.change(screen.getByLabelText(/Email Address/i), {
      target: { value: 'jane@example.com' },
    });

    const file = new File(['%PDF-1.4 dummy'], 'resume.pdf', { type: 'application/pdf' });
    const fileInput = document.querySelector('input[type="file"]');
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.click(screen.getByRole('button', { name: /Create Candidate/i }));

    await waitFor(() => {
      expect(clientModule.api.post).toHaveBeenCalledWith(
        '/candidates/',
        expect.any(FormData),
        expect.any(Object)
      );
    });
  });
});
