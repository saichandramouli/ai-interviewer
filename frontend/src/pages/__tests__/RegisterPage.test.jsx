import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import RegisterPage from '../RegisterPage';
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

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders token input screen initially when no token is in URL', () => {
    render(
      <MemoryRouter initialEntries={['/register']}>
        <RegisterPage />
      </MemoryRouter>
    );

    expect(screen.getByText('Recruiter Registration')).toBeInTheDocument();
    expect(screen.getByLabelText(/Invitation Token/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Verify Invitation/i })).toBeInTheDocument();
  });

  it('rejects empty token validation', async () => {
    render(
      <MemoryRouter initialEntries={['/register']}>
        <RegisterPage />
      </MemoryRouter>
    );

    const input = screen.getByLabelText(/Invitation Token/i);
    fireEvent.change(input, { target: { value: '   ' } });

    const btn = screen.getByRole('button', { name: /Verify Invitation/i });
    expect(btn).toBeDisabled();
  });

  it('displays error when token is invalid or expired', async () => {
    clientModule.api.get.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { detail: 'This invitation has expired.' },
      },
    });

    render(
      <MemoryRouter initialEntries={['/register?token=expired-token']}>
        <RegisterPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/This invitation has expired/i)).toBeInTheDocument();
    });
  });

  it('advances to details form when token is verified successfully', async () => {
    clientModule.api.get.mockResolvedValueOnce({
      data: {
        valid: true,
        email: 'recruiter@company.com',
        status: 'pending',
      },
    });

    render(
      <MemoryRouter initialEntries={['/register?token=valid-token-123']}>
        <RegisterPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('recruiter@company.com')).toBeInTheDocument();
      expect(screen.getByLabelText(/Full Name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^Password$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Confirm Password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Complete Registration/i })).toBeInTheDocument();
    });
  });

  it('completes registration when valid details are submitted', async () => {
    clientModule.api.get.mockResolvedValueOnce({
      data: {
        valid: true,
        email: 'recruiter@company.com',
        status: 'pending',
      },
    });
    clientModule.api.post.mockResolvedValueOnce({
      data: {
        message: 'Registration successful. You can now log in.',
        email: 'recruiter@company.com',
        role: 'recruiter',
      },
    });

    render(
      <MemoryRouter initialEntries={['/register?token=valid-token-123']}>
        <RegisterPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('recruiter@company.com')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: 'Alex Morgan' },
    });
    fireEvent.change(screen.getByLabelText(/^Password$/i), {
      target: { value: 'SecurePass123!' },
    });
    fireEvent.change(screen.getByLabelText(/Confirm Password/i), {
      target: { value: 'SecurePass123!' },
    });

    fireEvent.click(screen.getByRole('button', { name: /Complete Registration/i }));

    await waitFor(() => {
      expect(clientModule.api.post).toHaveBeenCalledWith('/auth/register/', {
        token: 'valid-token-123',
        full_name: 'Alex Morgan',
        password: 'SecurePass123!',
        password_confirm: 'SecurePass123!',
      });
      expect(screen.getByText(/Registration successful/i)).toBeInTheDocument();
    });
  });
});

