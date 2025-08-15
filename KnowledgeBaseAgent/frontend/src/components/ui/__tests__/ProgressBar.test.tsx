import { render, screen } from '@testing-library/react';
import { ProgressBar } from '../ProgressBar';

describe('ProgressBar', () => {
  it('renders with correct progress percentage', () => {
    render(<ProgressBar value={50} showLabel />);
    
    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('renders with custom label', () => {
    render(<ProgressBar value={75} showLabel label="Custom Progress" />);
    
    expect(screen.getByText('Custom Progress')).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('handles values outside 0-100 range', () => {
    const { rerender } = render(<ProgressBar value={-10} showLabel />);
    expect(screen.getByText('0%')).toBeInTheDocument();

    rerender(<ProgressBar value={150} showLabel />);
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('applies correct variant classes', () => {
    const { container } = render(<ProgressBar value={50} variant="success" />);
    const progressBar = container.querySelector('[style*="width: 50%"]');
    
    expect(progressBar).toHaveClass('bg-green-600');
  });

  it('applies correct size classes', () => {
    const { container } = render(<ProgressBar value={50} size="lg" />);
    const progressContainer = container.querySelector('.h-4');
    
    expect(progressContainer).toBeInTheDocument();
  });

  it('shows animated state when specified', () => {
    const { container } = render(<ProgressBar value={50} animated />);
    const progressBar = container.querySelector('[style*="width: 50%"]');
    
    expect(progressBar).toHaveClass('animate-pulse');
  });

  it('calculates percentage correctly with custom max', () => {
    render(<ProgressBar value={25} max={50} showLabel />);
    
    expect(screen.getByText('50%')).toBeInTheDocument();
  });
});