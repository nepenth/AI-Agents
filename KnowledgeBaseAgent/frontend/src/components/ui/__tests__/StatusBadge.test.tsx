import { render, screen } from '@testing-library/react';
import { StatusBadge, getStatusType } from '../StatusBadge';

describe('StatusBadge', () => {
  it('renders with default status configuration', () => {
    render(<StatusBadge status="completed" />);
    
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('✅')).toBeInTheDocument();
  });

  it('renders with custom label', () => {
    render(<StatusBadge status="running" label="Processing Data" />);
    
    expect(screen.getByText('Processing Data')).toBeInTheDocument();
    expect(screen.getByText('🔄')).toBeInTheDocument();
  });

  it('applies correct status classes', () => {
    const { container } = render(<StatusBadge status="failed" />);
    const badge = container.firstChild;
    
    expect(badge).toHaveClass('bg-red-100', 'text-red-800', 'border-red-200');
  });

  it('hides icon when showIcon is false', () => {
    render(<StatusBadge status="completed" showIcon={false} />);
    
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.queryByText('✅')).not.toBeInTheDocument();
  });

  it('applies animation for running status', () => {
    const { container } = render(<StatusBadge status="running" animated />);
    const badge = container.firstChild;
    
    expect(badge).toHaveClass('animate-pulse');
  });

  it('applies correct size classes', () => {
    const { container } = render(<StatusBadge status="pending" size="lg" />);
    const badge = container.firstChild;
    
    expect(badge).toHaveClass('px-4', 'py-2', 'text-base');
  });
});

describe('getStatusType', () => {
  it('correctly identifies status types from strings', () => {
    expect(getStatusType('pending')).toBe('pending');
    expect(getStatusType('RUNNING')).toBe('running');
    expect(getStatusType('completed successfully')).toBe('completed');
    expect(getStatusType('failed with error')).toBe('failed');
    expect(getStatusType('warning message')).toBe('warning');
    expect(getStatusType('unknown status')).toBe('info');
  });

  it('handles processing and waiting variations', () => {
    expect(getStatusType('processing')).toBe('running');
    expect(getStatusType('waiting')).toBe('pending');
    expect(getStatusType('done')).toBe('completed');
    expect(getStatusType('error occurred')).toBe('failed');
  });
});