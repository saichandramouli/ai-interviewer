import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import UserManagementPage from '../UserManagementPage';
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

describe('UserManagementPage', () => {
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
              status: 'active',
              date_joined: '2026-10-27T00:00:00Z',
            },
          ],
        });
      }
      if (url.includes('/admin/invitations/')) {
        return Promise.resolve({
          data: [
            {
              id: 10,
              email: 'pending.recruiter@example.com',
              status: 'pending',
              created_at: '2026-10-30T00:00:00Z',
              expires_at: '2026-11-01T00:00:00Z',
              created_by_email: 'admin@example.com',
            },
          ],
        });
      }
      return Promise.reject(new Error('Unknown url'));
    });
  });

  it('renders invitation and user tabs and lists active invitations', async () => {
    render(<UserManagementPage />);

    expect(screen.getByText('User Management')).toBeInTheDocument();
    expect(screen.getByText(/Invite New Recruiter/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('pending.recruiter@example.com')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Revoke/i })).toBeInTheDocument();
    });
  });

  it('generates an invitation link when valid email is submitted', async () => {
    clientModule.api.post.mockResolvedValueOnce({
      data: {
        id: 11,
        email: 'newrecruiter@example.com',
        status: 'pending',
        raw_token: 'secure_sample_raw_token_xyz',
      },
    });

    render(<UserManagementPage />);

    const input = screen.getByPlaceholderText(/recruiter.candidate@company.com/i);
    fireEvent.change(input, { target: { value: 'newrecruiter@example.com' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Recruiter Invitation/i }));

    await waitFor(() => {
      expect(clientModule.api.post).toHaveBeenCalledWith('/admin/invitations/', {
        email: 'newrecruiter@example.com',
      });
      expect(screen.getByText(/Invitation successfully created/i)).toBeInTheDocument();
      expect(screen.getByText(/secure_sample_raw_token_xyz/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Copy Link/i })).toBeInTheDocument();
    });
  });

  it('revokes an invitation when revoke button is clicked', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    clientModule.api.post.mockResolvedValueOnce({
      data: { id: 10, status: 'revoked', is_revoked: true },
    });

    render(<UserManagementPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Revoke/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Revoke/i }));

    await waitFor(() => {
      expect(clientModule.api.post).toHaveBeenCalledWith('/admin/invitations/10/revoke/');
      expect(screen.getByText(/Invitation revoked successfully/i)).toBeInTheDocument();
    });
  });

  it('switches to Registered Users tab and displays users', async () => {
    render(<UserManagementPage />);

    const usersTabBtn = await screen.findByRole('button', { name: /Registered Users/i });
    fireEvent.click(usersTabBtn);

    await waitFor(() => {
      expect(screen.getByText('admin@example.com')).toBeInTheDocument();
      expect(screen.getByText('Admin User')).toBeInTheDocument();
    });
  });
});
