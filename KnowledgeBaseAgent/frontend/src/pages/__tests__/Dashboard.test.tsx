import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from '../Dashboard';

describe('Dashboard', () => {
  it('renders loading state initially', () => {
    render(<Dashboard />);
    expect(screen.getByRole('generic')).toHaveClass('animate-spin');
  });

  it('renders dashboard content after loading', async () => {
    render(<Dashboard />);
    
    await waitFor(() => {
      expect(screen.getByText('System Overview')).toBeInTheDocument();
    });

    expect(screen.getByText('Active Tasks')).toBeInTheDocument();
    expect(screen.getByText('Queue Size')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Items')).toBeInTheDocument();
    expect(screen.getByText('Chat Sessions')).toBeInTheDocument();
  });

  it('displays system metrics', async () => {
    render(<Dashboard />);
    
    await waitFor(() => {
      expect(screen.getByText('System Resources')).toBeInTheDocument();
    });

    expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    expect(screen.getByText('Memory Usage')).toBeInTheDocument();
    expect(screen.getByText('Disk Usage')).toBeInTheDocument();
  });
});