import runWaitingFixture from './fixtures/run_waiting.json';
import runEscalatedFixture from './fixtures/run_escalated.json';
import runAcknowledgedFixture from './fixtures/run_acknowledged.json';
import runUnacknowledgedFixture from './fixtures/run_unacknowledged.json';

const FIXTURE_RUNS = [
  runWaitingFixture,
  runEscalatedFixture,
  runAcknowledgedFixture,
  runUnacknowledgedFixture,
];
const TRANSITION_MS = 5_000;

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function indiaDate(now) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now);
  const dateParts = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return `${dateParts.year}-${dateParts.month}-${dateParts.day}`;
}

function utcRunTimestamp(date) {
  return date.toISOString().slice(0, 19).replace(/[-:]/g, '');
}

function fixtureRun(fixture) {
  return clone(fixture);
}

export function createMockRunStore({
  now = () => new Date(),
  setTimer = setTimeout,
  clearTimer = clearTimeout,
} = {}) {
  const runs = new Map(FIXTURE_RUNS.map((fixture) => [fixture.run_id, fixtureRun(fixture)]));
  const latestBySite = new Map(FIXTURE_RUNS.map((fixture) => [fixture.site_id, fixture.run_id]));
  const timers = new Map();
  let runSequence = 0;

  const getRun = (runId) => {
    const run = runs.get(runId);
    if (!run) return null;
    return clone(run);
  };

  const getLatestRun = (siteId) => {
    const latestRunId = latestBySite.get(siteId);
    return latestRunId ? getRun(latestRunId) : null;
  };

  const clearRunTimer = (runId) => {
    const timer = timers.get(runId);
    if (timer !== undefined) {
      clearTimer(timer);
      timers.delete(runId);
    }
  };

  const updateFixture = (runId, fixture, step) => {
    const previous = runs.get(runId);
    const updated = clone(fixture);
    updated.run_id = runId;
    updated.site_id = previous.site_id;
    updated.plan_id = previous.plan_id;
    updated.ack_deadline = previous.ack_deadline;
    updated.created_at = previous.created_at;
    updated.events = [...previous.events, ...fixture.events
      .filter((event) => event.step === step)
      .map((event) => ({ ...event, ts: now().toISOString() }))];
    runs.set(runId, updated);
  };

  const scheduleEscalation = (runId) => {
    const escalatedTimer = setTimer(() => {
      timers.delete(runId);
      const current = runs.get(runId);
      if (!current || current.status !== 'WAITING_ACK') return;
      updateFixture(runId, runEscalatedFixture, 'escalated');
      const currentAfterEscalation = runs.get(runId);
      currentAfterEscalation.events.push(
        { ...runEscalatedFixture.events.filter((event) => event.step === 'telegram_sent').at(-1), ts: now().toISOString() },
        { ...runEscalatedFixture.events.find((event) => event.step === 'notified_backup'), ts: now().toISOString() },
      );
      const unackTimer = setTimer(() => {
        timers.delete(runId);
        const latest = runs.get(runId);
        if (!latest || latest.status !== 'ESCALATED') return;
        updateFixture(runId, runUnacknowledgedFixture, 'unacknowledged');
      }, TRANSITION_MS);
      timers.set(runId, unackTimer);
    }, TRANSITION_MS);
    timers.set(runId, escalatedTimer);
  };

  const startRun = async (site, options = {}) => {
    const sequenceTime = new Date(now().getTime() + runSequence * 1_000);
    runSequence += 1;
    const runId = `${site.site_id}_${utcRunTimestamp(sequenceTime)}`;
    const createdAt = sequenceTime.toISOString();
    const timeoutSeconds = options.ack_timeout_seconds || site.ack_timeout_seconds;
    const run = clone(runWaitingFixture);
    run.run_id = runId;
    run.site_id = site.site_id;
    run.plan_id = `${site.site_id}_${indiaDate(sequenceTime)}`;
    run.ack_deadline = new Date(sequenceTime.getTime() + timeoutSeconds * 1_000).toISOString();
    run.created_at = createdAt;
    run._fixture = true;
    run.events = run.events.map((event) => ({ ...event, ts: createdAt }));
    runs.set(runId, run);
    latestBySite.set(site.site_id, runId);
    scheduleEscalation(runId);
    return { run_id: runId, status: 'STARTED', _fixture: true };
  };

  const acknowledge = async (runId, by = 'Site Supervisor') => {
    const current = runs.get(runId);
    if (!current) return null;
    clearRunTimer(runId);
    const acknowledged = clone(runAcknowledgedFixture);
    acknowledged.run_id = runId;
    acknowledged.site_id = current.site_id;
    acknowledged.plan_id = current.plan_id;
    acknowledged.ack_deadline = current.ack_deadline;
    acknowledged.created_at = current.created_at;
    acknowledged.acked_by = by;
    acknowledged.acked_via = 'web';
    acknowledged.events = [
      ...current.events,
      { ts: now().toISOString(), step: 'acknowledged', detail: `${by} acknowledged on web` },
    ];
    runs.set(runId, acknowledged);
    return { ok: true, status: 'ACKNOWLEDGED', _fixture: true };
  };

  return { getRun, getLatestRun, startRun, acknowledge };
}
