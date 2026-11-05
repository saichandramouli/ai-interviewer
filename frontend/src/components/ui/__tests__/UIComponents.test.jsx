import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import {
  Button,
  Card,
  Badge,
  DataTable,
  Modal,
  PageHeader,
  Input,
} from '../index';

describe('Enterprise Slate Reusable UI Components', () => {
  describe('Button Component', () => {
    it('renders with children and responds to click events', () => {
      const handleClick = vi.fn();
      render(<Button onClick={handleClick}>Save Changes</Button>);
      const btn = screen.getByRole('button', { name: /save changes/i });
      expect(btn).toBeInTheDocument();
      fireEvent.click(btn);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('renders loading state and disables user interactions', () => {
      const handleClick = vi.fn();
      render(<Button loading onClick={handleClick}>Submit</Button>);
      const btn = screen.getByRole('button', { name: /submit/i });
      expect(btn).toBeDisabled();
      fireEvent.click(btn);
      expect(handleClick).not.toHaveBeenCalled();
    });

    it('supports danger and secondary variants', () => {
      const { rerender } = render(<Button variant="danger">Delete</Button>);
      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
      rerender(<Button variant="secondary">Cancel</Button>);
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });
  });

  describe('Card Component', () => {
    it('renders title, description, content and footer actions', () => {
      render(
        <Card
          title="Interview Metrics"
          description="Summary of recent activity"
          footer={<button>View details</button>}
        >
          <div>Card Body Content</div>
        </Card>
      );
      expect(screen.getByText('Interview Metrics')).toBeInTheDocument();
      expect(screen.getByText('Summary of recent activity')).toBeInTheDocument();
      expect(screen.getByText('Card Body Content')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /view details/i })).toBeInTheDocument();
    });
  });

  describe('Badge Component', () => {
    it('renders text with appropriate status mapping', () => {
      const { rerender } = render(<Badge status="completed" />);
      expect(screen.getByText('completed')).toBeInTheDocument();

      rerender(<Badge variant="warning">Pending Review</Badge>);
      expect(screen.getByText('Pending Review')).toBeInTheDocument();
    });
  });

  describe('DataTable Component', () => {
    const columns = [
      { header: 'Candidate', accessor: 'name' },
      { header: 'Status', accessor: 'status', render: (row) => <Badge status={row.status} /> },
    ];
    const data = [
      { id: 1, name: 'Alice Smith', status: 'completed' },
      { id: 2, name: 'Bob Jones', status: 'scheduled' },
    ];

    it('renders column headers and row data correctly', () => {
      render(<DataTable columns={columns} data={data} />);
      expect(screen.getByText('Candidate')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Alice Smith')).toBeInTheDocument();
      expect(screen.getByText('Bob Jones')).toBeInTheDocument();
    });

    it('renders empty message when data is empty', () => {
      render(<DataTable columns={columns} data={[]} emptyMessage="No candidates found" />);
      expect(screen.getByText('No candidates found')).toBeInTheDocument();
    });

    it('renders loading indicator when loading is true', () => {
      render(<DataTable columns={columns} data={[]} loading />);
      expect(screen.getByText(/loading records/i)).toBeInTheDocument();
    });
  });

  describe('Modal Component', () => {
    it('renders dialog content when open and supports close callback', () => {
      const handleClose = vi.fn();
      render(
        <Modal
          isOpen={true}
          onClose={handleClose}
          title="Confirm Action"
          description="Are you sure you want to proceed?"
        >
          <div>Modal details</div>
        </Modal>
      );
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Confirm Action')).toBeInTheDocument();
      expect(screen.getByText('Modal details')).toBeInTheDocument();

      const closeBtn = screen.getByLabelText(/close modal/i);
      fireEvent.click(closeBtn);
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('does not render when isOpen is false', () => {
      render(<Modal isOpen={false} title="Hidden" />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('handles Escape key listener to trigger onClose', () => {
      const handleClose = vi.fn();
      render(<Modal isOpen={true} onClose={handleClose} title="Escape Test" />);
      fireEvent.keyDown(window, { key: 'Escape' });
      expect(handleClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('PageHeader Component', () => {
    it('renders title, description, actions, and breadcrumbs', () => {
      render(
        <BrowserRouter>
          <PageHeader
            title="Candidate Directory"
            description="Manage all applicants"
            breadcrumbs={[
              { label: 'Home', to: '/dashboard' },
              { label: 'Candidates' },
            ]}
            actions={<button>Add Candidate</button>}
          />
        </BrowserRouter>
      );
      expect(screen.getByText('Candidate Directory')).toBeInTheDocument();
      expect(screen.getByText('Manage all applicants')).toBeInTheDocument();
      expect(screen.getByText('Home')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /add candidate/i })).toBeInTheDocument();
    });
  });

  describe('Input Component', () => {
    it('renders label, input value, and handles onChange events', () => {
      const handleChange = vi.fn();
      render(
        <Input
          label="Full Name"
          value="Jane Doe"
          onChange={handleChange}
          required
        />
      );
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
      const input = screen.getByDisplayValue('Jane Doe');
      fireEvent.change(input, { target: { value: 'Jane Smith' } });
      expect(handleChange).toHaveBeenCalled();
    });

    it('renders error message when error prop is provided', () => {
      render(<Input label="Email" error="Invalid email address" />);
      expect(screen.getByText('Invalid email address')).toBeInTheDocument();
    });
  });
});
