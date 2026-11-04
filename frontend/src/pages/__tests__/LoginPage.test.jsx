import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../../context/AuthContext';
import LoginPage from '../LoginPage';
import * as clientModule from '../../api/client';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual('../../api/client');
  return {
    ...actual,
    api: {
      post: vi.fn(),
      get: vi.fn(),
    },
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
    getAccessToken: vi.fn(() => null),
    getRefreshToken: vi.fn(() => null),
  };
});

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('renders login form with inputs, sign in button, and register invitation link', () => {
    render(
      <AuthProvider>
        <BrowserRouter>
          <LoginPage />
        </BrowserRouter>
      </AuthProvider>
    );

    expect(screen.getByText('Recruiter Login')).toBeInTheDocument();
    expect(screen.getByLabelText(/Email Address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign in/i })).toBeInTheDocument();
    expect(screen.getByText(/Register with Invitation/i)).toBeInTheDocument();
  });

  it('validates empty inputs before submission', async () => {
    render(
      <AuthProvider>
        <BrowserRouter>
          <LoginPage />
        </BrowserRouter>
      </AuthProvider>
    );

    const form = screen.getByRole('button', { name: /Sign in/i }).closest('form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText(/Please enter both email and password/i)).toBeInTheDocument();
    });
  });

  it('handles invalid credentials with appropriate error message', async () => {
    clientModule.api.post.mockRejectedValueOnce({
      response: {
        status: 401,
        data: { detail: 'No active account found with the given credentials' },
      },
    });

    render(
      <AuthProvider>
        <BrowserRouter>
          <LoginPage />
        </BrowserRouter>
      </AuthProvider>
    );

    fireEvent.change(screen.getByLabelText(/Email Address/i), {
      target: { value: 'recruiter@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: 'wrongpassword' },
    });

    const form = screen.getByRole('button', { name: /Sign in/i }).closest('form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(
        screen.getByText(/No active account found with the given credentials/i)
      ).toBeInTheDocument();
    });
  });

  it('authenticates recruiter successfully and navigates to recruiter /dashboard', async () => {
    clientModule.api.post.mockResolvedValueOnce({
      data: {
        access: 'mock-access-token',
        refresh: 'mock-refresh-token',
      },
    });
    clientModule.api.get.mockResolvedValueOnce({
      data: {
        email: 'recruiter@example.com',
        role: 'recruiter',
      },
    });

    render(
      <AuthProvider>
        <BrowserRouter>
          <LoginPage />
        </BrowserRouter>
      </AuthProvider>
    );

    fireEvent.change(screen.getByLabelText(/Email Address/i), {
      target: { value: 'recruiter@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: 'validpassword' },
    });

    const form = screen.getByRole('button', { name: /Sign in/i }).closest('form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(clientModule.setTokens).toHaveBeenCalledWith(
        'mock-access-token',
        'mock-refresh-token'
      );
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('authenticates admin successfully and navigates to /admin/dashboard', async () => {
    clientModule.api.post.mockResolvedValueOnce({
      data: {
        access: 'mock-admin-access-token',
        refresh: 'mock-admin-refresh-token',
      },
    });
    clientModule.api.get.mockResolvedValueOnce({
      data: {
        email: 'admin@example.com',
        role: 'admin',
      },
    });

    render(
      <AuthProvider>
        <BrowserRouter>
          <LoginPage />
        </BrowserRouter>
      </AuthProvider>
    );

    fireEvent.change(screen.getByLabelText(/Email Address/i), {
      target: { value: 'admin@example.com' },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: 'adminpassword' },
    });

    const form = screen.getByRole('button', { name: /Sign in/i }).closest('form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/admin/dashboard');
    });
  });
});
