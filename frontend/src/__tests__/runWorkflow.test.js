import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  RUN_EVENT_LABELS,
  RUN_STATUS_LABELS,
  createRunPollingController,
  formatCountdown,
  formatEventTime,
  isFixtureData,
  latestRunViewState,
  runConfirmationReducer,
} from '../runWorkflow.js';

function visibilityTarget(initialState = 'visible') {
  const listeners = new Map();
  return {
    visibilityState: initialState,
    addEventListener: (name, listener) => listeners.set(name, listener),
    removeEventListener: (name) => listeners.delete(name),
    change(state) {
      this.visibilityState = state;
      listeners.get('visibilitychange')?.();
    },
  };
}

afterEach(() => vi.useRealTimers());

describe('run event and display helpers', () => {
  it('maps every contract event step to its exact display label', () => {
    expect(RUN_EVENT_LABELS).toEqual({
      plan_built: 'Heat plan built',
      voice_ready: 'Hindi voice message created',
      telegram_sent: 'Message sent on Telegram',
      telegram_failed: 'Telegram delivery failed',
      notified_primary: 'Supervisor notified',
      escalated: 'No answer: escalating to backup',
      notified_backup: 'Backup notified',
      acknowledged: 'Acknowledged',
      unacknowledged: 'Nobody acknowledged',
      error: 'Error',
    });
  });

  it('labels every run status in the UI', () => {
    expect(RUN_STATUS_LABELS).toEqual({
      STARTED: 'STARTED',
      WAITING_ACK: 'WAITING FOR ACKNOWLEDGEMENT',
      ESCALATED: 'ESCALATED TO BACKUP',
      ACKNOWLEDGED: 'ACKNOWLEDGED',
      UNACKNOWLEDGED: 'NOT ACKNOWLEDGED',
      FAILED: 'FAILED',
    });
  });

  it('formats a deadline as mm:ss and reports when it has elapsed', () => {
    const deadline = '1970-01-01T00:01:05.000Z';
    expect(formatCountdown(deadline, 0)).toBe('01:05');
    expect(formatCountdown(deadline, 5_000)).toBe('01:00');
    expect(formatCountdown(deadline, 65_000)).toBe('timed out');
    expect(formatCountdown('invalid')).toBe('—');
  });

  it('formats event times in India local time with seconds', () => {
    expect(formatEventTime('2026-10-09T00:30:24Z')).toBe('06:00:24');
  });

  it('marks fixture data only when the fixture flag is exactly true', () => {
    expect(isFixtureData({ _fixture: true })).toBe(true);
    expect(isFixtureData({ _fixture: false })).toBe(false);
    expect(isFixtureData({})).toBe(false);
  });

  it('distinguishes latest-run empty and recoverable error states', () => {
    expect(latestRunViewState({ loading: true })).toBe('loading');
    expect(latestRunViewState({ run: null, error: { status: 404 } })).toBe('empty');
    expect(latestRunViewState({ run: null, error: { code: 'network' } })).toBe('error');
    expect(latestRunViewState({ run: { run_id: 'r1' } })).toBe('run');
  });

  it('closes a cancelled confirmation without invoking any run action', () => {
    const startRun = vi.fn();
    const opened = runConfirmationReducer(false, 'open');
    const cancelled = runConfirmationReducer(opened, 'cancel');
    expect(opened).toBe(true);
    expect(cancelled).toBe(false);
    expect(startRun).not.toHaveBeenCalled();
  });
});

describe('run polling controller', () => {
  it('stops polling when a final status is returned', async () => {
    vi.useFakeTimers();
    const loadRun = vi.fn()
      .mockResolvedValueOnce({ status: 'WAITING_ACK' })
      .mockResolvedValueOnce({ status: 'ACKNOWLEDGED' });
    const controller = createRunPollingController({
      runId: 'run-1',
      loadRun,
      onRun: vi.fn(),
      onError: vi.fn(),
      visibilityTarget: visibilityTarget(),
    });
    controller.start();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(2_000);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(loadRun).toHaveBeenCalledTimes(2);
    controller.stop();
  });

  it('pauses while hidden and resumes with an immediate refresh', async () => {
    vi.useFakeTimers();
    const target = visibilityTarget();
    const loadRun = vi.fn().mockResolvedValue({ status: 'WAITING_ACK' });
    const controller = createRunPollingController({
      runId: 'run-1',
      loadRun,
      onRun: vi.fn(),
      onError: vi.fn(),
      visibilityTarget: target,
    });
    controller.start();
    await vi.advanceTimersByTimeAsync(0);
    target.change('hidden');
    await vi.advanceTimersByTimeAsync(6_000);
    expect(loadRun).toHaveBeenCalledTimes(1);
    target.change('visible');
    await vi.advanceTimersByTimeAsync(0);
    expect(loadRun).toHaveBeenCalledTimes(2);
    controller.stop();
    expect(target.removeEventListener).toBeDefined();
  });

  it('keeps the initial run while hidden and starts polling when visible', async () => {
    vi.useFakeTimers();
    const target = visibilityTarget('hidden');
    const loadRun = vi.fn().mockResolvedValue({ status: 'WAITING_ACK' });
    const onRun = vi.fn();
    const controller = createRunPollingController({
      runId: 'run-1',
      loadRun,
      onRun,
      onError: vi.fn(),
      visibilityTarget: target,
    });
    controller.start({ status: 'WAITING_ACK', run_id: 'run-1' });
    expect(onRun).toHaveBeenCalledWith({ status: 'WAITING_ACK', run_id: 'run-1' });
    await vi.advanceTimersByTimeAsync(6_000);
    expect(loadRun).not.toHaveBeenCalled();
    target.change('visible');
    await vi.advanceTimersByTimeAsync(0);
    expect(loadRun).toHaveBeenCalledTimes(1);
    controller.stop();
  });

  it('allows an explicit refresh while hidden', async () => {
    const target = visibilityTarget('hidden');
    const updatedRun = { status: 'ACKNOWLEDGED', run_id: 'run-1' };
    const loadRun = vi.fn().mockResolvedValue(updatedRun);
    const onRun = vi.fn();
    const controller = createRunPollingController({
      runId: 'run-1',
      loadRun,
      onRun,
      onError: vi.fn(),
      visibilityTarget: target,
    });
    controller.start({ status: 'WAITING_ACK', run_id: 'run-1' });
    await controller.refresh();
    expect(loadRun).toHaveBeenCalledTimes(1);
    expect(onRun).toHaveBeenLastCalledWith(updatedRun);
    controller.stop();
  });

  it('backs off after three consecutive errors while retaining last successful data', async () => {
    vi.useFakeTimers();
    let displayedRun = null;
    const loadRun = vi.fn()
      .mockResolvedValueOnce({ status: 'WAITING_ACK', run_id: 'run-1' })
      .mockRejectedValue(new Error('offline'));
    const onError = vi.fn();
    const controller = createRunPollingController({
      runId: 'run-1',
      loadRun,
      onRun: (run) => { displayedRun = run; },
      onError,
      visibilityTarget: visibilityTarget(),
    });
    controller.start();
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(2_000);
    await vi.advanceTimersByTimeAsync(2_000);
    await vi.advanceTimersByTimeAsync(2_000);
    expect(displayedRun).toEqual({ status: 'WAITING_ACK', run_id: 'run-1' });
    expect(onError).toHaveBeenCalledTimes(3);
    expect(loadRun).toHaveBeenCalledTimes(4);
    await vi.advanceTimersByTimeAsync(4_999);
    expect(loadRun).toHaveBeenCalledTimes(4);
    await vi.advanceTimersByTimeAsync(1);
    expect(loadRun).toHaveBeenCalledTimes(5);
    expect(displayedRun).toEqual({ status: 'WAITING_ACK', run_id: 'run-1' });
    controller.stop();
  });
});
