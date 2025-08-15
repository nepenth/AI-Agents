import { render, screen, fireEvent } from '@testing-library/react';
import { WebSocketIndicator, ConnectionDot } from '../WebSocketIndicator';

describe('WebSocketIndicator', () => {
  it('renders connected status correctly', () => {
    render(<WebSocketIndicator status="connected" />);
    
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('🟢')).toBeInTheDocument();
  });

  it('renders connecting status with animation', () => {
    const { container } = render(<WebSocketIndicator status="connecting" />);
    
    expect(screen.getByText('Connecting...')).toBeInTheDocument();
    expect(screen.getByText('🟡')).toBeInTheDocument();
    
    const icon = container.querySelector('.animate-pulse');
    expect(icon).toBeInTheDocument();
  });

  it('shows reconnect button for disconnected status', () => {
    const mockReconnect = jest.fn();
    render(
      <WebSocketIndicator 
        status="disconnected" 
        onReconnect={mockReconnect}
        reconnectAttempts={3}
      />
    );
    
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
    expect(screen.getByText('Attempts: 3')).toBeInTheDocument();
    
    const reconnectButton = screen.getByText('Reconnect');
    fireEvent.click(reconnectButton);
    
    expect(mockReconnect).toHaveBeenCalledTimes(1);
  });

  it('formats last connected time correctly', () => {
    const lastConnected = new Date(Date.now() - 5 * 60 * 1000); // 5 minutes ago
    
    render(
      <WebSocketIndicator 
        status="disconnected" 
        lastConnected={lastConnected}
      />
    );
    
    expect(screen.getByText('Last: 5m ago')).toBeInTheDocument();
  });

  it('hides label when showLabel is false', () => {
    render(<WebSocketIndicator status="connected" showLabel={false} />);
    
    expect(screen.getByText('🟢')).toBeInTheDocument();
    expect(screen.queryByText('Connected')).not.toBeInTheDocument();
  });

  it('applies correct size classes', () => {
    const { container } = render(<WebSocketIndicator status="connected" size="lg" />);
    const indicator = container.querySelector('.px-4.py-2.text-base');
    
    expect(indicator).toBeInTheDocument();
  });
});

describe('ConnectionDot', () => {
  it('renders correct color for each status', () => {
    const { container: connectedContainer } = render(<ConnectionDot status="connected" />);
    expect(connectedContainer.firstChild).toHaveClass('bg-green-500');

    const { container: connectingContainer } = render(<ConnectionDot status="connecting" />);
    expect(connectingContainer.firstChild).toHaveClass('bg-yellow-500', 'animate-pulse');

    const { container: disconnectedContainer } = render(<ConnectionDot status="disconnected" />);
    expect(disconnectedContainer.firstChild).toHaveClass('bg-red-500');

    const { container: errorContainer } = render(<ConnectionDot status="error" />);
    expect(errorContainer.firstChild).toHaveClass('bg-red-500');
  });

  it('applies custom className', () => {
    const { container } = render(<ConnectionDot status="connected" className="custom-class" />);
    
    expect(container.firstChild).toHaveClass('custom-class');
  });
});