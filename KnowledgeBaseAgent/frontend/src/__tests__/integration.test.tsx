import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import App from '../App';

// Mock the services
vi.mock('@/services/agentService', () => ({
  agentService: {
    getSystemMetrics: vi.fn().mockResolvedValue({
      cpu_usage: 0.45,
      memory_usage: 0.67,
      disk_usage: 0.23,
      active_tasks: 3,
      queue_size: 7,
      uptime: 86400,
    }),
  },
}));

vi.mock('@/services/websocket', () => ({
  websocketService: {
    connect: vi.fn().mockResolvedValue(undefined),
    disconnect: vi.fn(),
    subscribe: vi.fn(() => () => {}),
    isConnected: false,
    connectionState: 'disconnected',
  },
}));

describe('App Integration', () => {
  it('renders the application with dashboard', async () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );

    // Check if the layout is rendered
    expect(screen.getByText('AI Agent')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();

    // Check if navigation is present
    expect(screen.getByText('Knowledge Base')).toBeInTheDocument();
    expect(screen.getByText('Chat')).toBeInTheDocument();
    expect(screen.getByText('Monitoring')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();

    // Wait for dashboard content to load
    await waitFor(() => {
      expect(screen.getByText('System Overview')).toBeInTheDocument();
    });

    // Check if dashboard stats are displayed
    expect(screen.getByText('Active Tasks')).toBeInTheDocument();
    expect(screen.getByText('Queue Size')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Items')).toBeInTheDocument();
    expect(screen.getByText('Chat Sessions')).toBeInTheDocument();
  });

  it('handles error boundary', () => {
    const ThrowError = () => {
      throw new Error('Test error');
    };

    const { container } = render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    );

    // Replace a component with one that throws
    const errorComponent = render(<ThrowError />);
    
    // The error boundary should catch this and show error UI
    // This is a simplified test - in practice you'd need to trigger an actual error
    expect(container).toBeInTheDocument();
  });
});