import { afterEach, describe, expect, it, vi } from 'vitest';
import { createMockRunStore } from '../mockRunWorkflow.js';

afterEach(() => vi.useRealTimers());

describe('mock run lifecycle', () => {
  it('starts from the waiting fixture and advances through escalation to unacknowledged', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-11T08:00:00Z'));
    const store = createMockRunStore();
    const site = {
      site_id: 'demo-site',
      ack_timeout_seconds: 600,
      supervisor: { name: 'Supervisor' },
    };
    const started = await store.startRun(site, { ack_timeout_seconds: 60 });

    expect(started).toMatchObject({ status: 'STARTED', _fixture: true });
    expect(started.run_id).toMatch(/^demo-site_\d{8}T\d{6}$/);
    const waiting = store.getRun(started.run_id);
    expect(waiting).toMatchObject({
      status: 'WAITING_ACK',
      site_id: 'demo-site',
      plan_id: expect.stringMatching(/^demo-site_\d{4}-\d{2}-\d{2}$/),
      _fixture: true,
    });
    expect(Date.parse(waiting.ack_deadline) - Date.parse(waiting.created_at)).toBe(60_000);

    await vi.advanceTimersByTimeAsync(5_000);
    expect(store.getRun(started.run_id).status).toBe('ESCALATED');
    await vi.advanceTimersByTimeAsync(5_000);
    expect(store.getRun(started.run_id).status).toBe('UNACKNOWLEDGED');
    expect(store.getLatestRun('demo-site').run_id).toBe(started.run_id);
  });

  it('acknowledges a mock run as the acknowledged fixture and cancels pending transitions', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-11T08:00:00Z'));
    const store = createMockRunStore();
    const started = await store.startRun({ site_id: 'demo-site', ack_timeout_seconds: 900 });
    const result = await store.acknowledge(started.run_id, 'Asha');

    expect(result).toMatchObject({ status: 'ACKNOWLEDGED', _fixture: true });
    const acknowledgedRun = store.getRun(started.run_id);
    expect(acknowledgedRun).toMatchObject({
      status: 'ACKNOWLEDGED',
      acked_by: 'Asha',
      acked_via: 'web',
      _fixture: true,
    });
    expect(acknowledgedRun.events.at(-1)).toMatchObject({ step: 'acknowledged' });
    await vi.advanceTimersByTimeAsync(10_000);
    expect(store.getRun(started.run_id).status).toBe('ACKNOWLEDGED');
  });

  it('returns no latest run for a site without a run', () => {
    expect(createMockRunStore().getLatestRun('empty-site')).toBeNull();
  });
});
