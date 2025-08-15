import { render, screen, act } from '@testing-library/react';
import { ProgressIndicator, PhaseProgressIndicator } from '../ProgressIndicator';

// Mock requestAnimationFrame
global.requestAnimationFrame = jest.fn((cb) => {
  setTimeout(cb, 16);
  return 1;
});

describe('ProgressIndicator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders with basic props', () => {
    render(
      <ProgressIndicator
        value={50}
        status="running"
        label="Test Progress"
      />
    );

    expect(screen.getByText('Test Progress')).toBeInTheDocument();
    expect(screen.getByText('50.0%')).toBeInTheDocument();
    expect(screen.getByText('Processing')).toBeInTheDocument();
  });

  it('shows ETA when enabled', () => {
    const startTime = new Date(Date.now() - 10000); // 10 seconds ago
    
    render(
      <ProgressIndicator
        value={25}
        status="running"
        showETA={true}
        startTime={startTime}
      />
    );

    // Should show some ETA (exact value depends on calculation)
    expect(screen.getByText(/ETA:/)).toBeInTheDocument();
  });

  it('shows speedometer when enabled', () => {
    const startTime = new Date(Date.now() - 5000); // 5 seconds ago
    
    render(
      <ProgressIndicator
        value={50}
        status="running"
        showSpeedometer={true}
        startTime={startTime}
      />
    );

    // Should show speed indicator
    expect(screen.getByText(/\/s$/)).toBeInTheDocument();
  });

  it('displays completed status correctly', () => {
    render(
      <ProgressIndicator
        value={100}
        status="completed"
        label="Completed Task"
      />
    );

    expect(screen.getByText('✅')).toBeInTheDocument();
    expect(screen.getByText('Completed successfully')).toBeInTheDocument();
  });

  it('displays failed status correctly', () => {
    render(
      <ProgressIndicator
        value={75}
        status="failed"
        label="Failed Task"
      />
    );

    expect(screen.getByText('❌')).toBeInTheDocument();
    expect(screen.getByText('Processing failed')).toBeInTheDocument();
  });

  it('handles different sizes', () => {
    const { rerender } = render(
      <ProgressIndicator
        value={50}
        status="running"
        size="sm"
      />
    );

    // Test that component renders without error for different sizes
    rerender(
      <ProgressIndicator
        value={50}
        status="running"
        size="lg"
      />
    );

    expect(screen.getAllByText('50.0%')).toHaveLength(1);
  });

  it('animates value changes', async () => {
    const { rerender } = render(
      <ProgressIndicator
        value={25}
        status="running"
        animated={true}
      />
    );

    expect(screen.getByText('25.0%')).toBeInTheDocument();

    // Change value and check animation
    rerender(
      <ProgressIndicator
        value={75}
        status="running"
        animated={true}
      />
    );

    // Animation should eventually reach the new value
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 600));
    });

    expect(screen.getByText('75.0%')).toBeInTheDocument();
  });
});

describe('PhaseProgressIndicator', () => {
  const mockSubPhases = [
    {
      name: 'Sub-phase 1',
      status: 'completed' as const,
      progress: 100
    },
    {
      name: 'Sub-phase 2',
      status: 'running' as const,
      progress: 50
    },
    {
      name: 'Sub-phase 3',
      status: 'pending' as const
    }
  ];

  it('renders phase information correctly', () => {
    render(
      <PhaseProgressIndicator
        phaseName="Content Processing"
        phaseNumber={3}
        status="running"
        progress={60}
        aiModelUsed="llama2"
        isRealAI={true}
      />
    );

    expect(screen.getByText('Phase 3: Content Processing')).toBeInTheDocument();
    expect(screen.getByText('llama2 (Real AI)')).toBeInTheDocument();
    expect(screen.getByText('🔄')).toBeInTheDocument();
  });

  it('displays sub-phases when provided', () => {
    render(
      <PhaseProgressIndicator
        phaseName="Content Processing"
        phaseNumber={3}
        status="running"
        progress={60}
        subPhases={mockSubPhases}
      />
    );

    expect(screen.getByText('Sub-phases:')).toBeInTheDocument();
    expect(screen.getByText('Sub-phase 1')).toBeInTheDocument();
    expect(screen.getByText('Sub-phase 2')).toBeInTheDocument();
    expect(screen.getByText('Sub-phase 3')).toBeInTheDocument();
  });

  it('shows different icons for AI vs simulated processing', () => {
    const { rerender } = render(
      <PhaseProgressIndicator
        phaseName="Media Analysis"
        phaseNumber={1}
        status="completed"
        isRealAI={true}
      />
    );

    expect(screen.getByText('🤖✅')).toBeInTheDocument();

    rerender(
      <PhaseProgressIndicator
        phaseName="Media Analysis"
        phaseNumber={1}
        status="completed"
        isRealAI={false}
      />
    );

    expect(screen.getByText('✅')).toBeInTheDocument();
  });

  it('displays duration when provided', () => {
    render(
      <PhaseProgressIndicator
        phaseName="Embedding Generation"
        phaseNumber={5}
        status="completed"
        duration={2500}
      />
    );

    expect(screen.getByText('Duration: 2.5s')).toBeInTheDocument();
  });

  it('handles pending status correctly', () => {
    render(
      <PhaseProgressIndicator
        phaseName="Git Sync"
        phaseNumber={7}
        status="pending"
      />
    );

    expect(screen.getByText('⏳')).toBeInTheDocument();
    expect(screen.getByText('Phase 7: Git Sync')).toBeInTheDocument();
  });

  it('shows progress for running sub-phases', () => {
    render(
      <PhaseProgressIndicator
        phaseName="Content Processing"
        phaseNumber={3}
        status="running"
        subPhases={mockSubPhases}
      />
    );

    // Should show progress for the running sub-phase
    const runningSubPhase = screen.getByText('Sub-phase 2');
    expect(runningSubPhase).toBeInTheDocument();
  });
});