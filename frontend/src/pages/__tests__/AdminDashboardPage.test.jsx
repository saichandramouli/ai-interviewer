import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import AdminDashboardPage from '../AdminDashboardPage';
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

describe('AdminDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clientModule.api.get.mockImplementation((url) => {
      if (url.includes('/admin/users/')) {
        return Promise.resolve({
          data: [
            {
              id: 1,
              email: 'admin@example.com',
              first_name: 'Admin',
              last_name: 'User',
              role: 'admin',
              is_active: true,
              status: 'active',
              date_joined: '2026-10-27T00:00:00Z',
            },
            {
              id: 2,
              email: 'recruiter1@example.com',
              first_name: 'Jane',
              last_name: 'Recruiter',
              role: 'recruiter',
              is_active: true,
              status: 'active',
              date_joined: '2026-10-28T00:00:00Z',
            },
          ],
        });
      }
      if (url.includes('/admin/invitations/')) {
        return Promise.resolve({
          data: [
            {
              id: 10,
              email: 'pending.invite@example.com',
              status: 'pending',
              created_at: '2026-10-30T00:00:00Z',
              expires_at: '2026-11-01T00:00:00Z',
            },
            {
              id: 11,
              email: 'used.invite@example.com',
              status: 'used',
              created_at: '2026-10-28T00:00:00Z',
              expires_at: '2026-10-30T00:00:00Z',
            },
          ],
        });
      }
      return Promise.reject(new Error('Unknown url'));
    });
  });

  it('renders admin dashboard metrics, recruiter listing, and invite form', async () => {
    render(
      <BrowserRouter>
        <AdminDashboardPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
      expect(screen.getByText(/Create Recruiter Account \(Send Invitation\)/i)).toBeInTheDocument();
      expect(screen.getByText('Total Registered Recruiters')).toBeInTheDocument();
      expect(screen.getByText('recruiter1@example.com')).toBeInTheDocument();
      expect(screen.getByText('pending.invite@example.com')).toBeInTheDocument();
    });
  });

  it('allows quick invitation generation from dashboard', async () => {
    clientModule.api.post.mockResolvedValueOnce({
      data: {
        id: 12,
        email: 'quickinvite@example.com',
        status: 'pending',
        raw_token: 'raw_dash_token_abc',
      },
    });

    render(
      <BrowserRouter>
        <AdminDashboardPage />
      </BrowserRouter>
    );

    const input = await screen.findByPlaceholderText(/recruiter.name@company.com/i);
    fireEvent.change(input, { target: { value: 'quickinvite@example.com' } });

    fireEvent.click(screen.getByRole('button', { name: /Invite Recruiter/i }));

    await waitFor(() => {
      expect(clientModule.api.post).toHaveBeenCalledWith('/admin/invitations/', {
        email: 'quickinvite@example.com',
      });
      expect(screen.getByText(/Invitation successfully created/i)).toBeInTheDocument();
      expect(screen.getByText(/raw_dash_token_abc/i)).toBeInTheDocument();
    });
  });

  it('allows deactivating a recruiter account', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    clientModule.api.post.mockResolvedValueOnce({
      data: { id: 2, email: 'recruiter1@example.com', is_active: false },
    });

    render(
      <BrowserRouter>
        <AdminDashboardPage />
      </BrowserRouter>
    );

    const deactivateBtn = await screen.findByRole('button', { name: /Deactivate/i });
    fireEvent.click(deactivateBtn);

    await waitFor(() => {
      expect(clientModule.api.post).toHaveBeenCalledWith('/admin/users/2/toggle-active/');
      expect(screen.getByText(/Recruiter account deactivated successfully/i)).toBeInTheDocument();
    });
  });
});
