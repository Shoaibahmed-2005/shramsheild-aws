import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ack, getPlan, getRun } from '../api.js';
import {
  ACTIVE_RUN_STATUSES,
  RUN_EVENT_LABELS,
  RUN_STATUS_LABELS,
  createRunPollingController,
  formatCountdown,
  formatEventTime,
  isFixtureData,
} from '../runWorkflow.js';

function safeErrorMessage(error) {
  return (error?.message || 'The request could not be completed.')
    .replace(/https?:\/\/\S+/gi, '[link hidden]');
}

function stageState(run, stage) {
  const steps = new Set((run.events || []).map((event) => event.step));
  if (stage === 'plan') {
    return steps.has('plan_built') ? 'complete' : 'current';
  }
  if (stage === 'supervisor') {
    if (steps.has('notified_primary')) return 'complete';
    return ACTIVE_RUN_STATUSES.has(run.status) ? 'current' : 'pending';
  }
  if (steps.has('notified_backup')) return 'complete';
  return run.status === 'ESCALATED' ? 'current' : 'pending';
}

function statusClass(status) {
  return `run-status-chip run-status-${String(status || '').toLowerCase()}`;
}

export function RunPage({ runId }) {
  const [run, setRun] = useState(null);
  const [plan, setPlan] = useState(null);
  const [planError, setPlanError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pollErrors, setPollErrors] = useState(0);
  const [ackName, setAckName] = useState('');
  const [ackPending, setAckPending] = useState(false);
  const [ackMessage, setAckMessage] = useState('');
  const [voiceFailed, setVoiceFailed] = useState(false);
  const [now, setNow] = useState(Date.now());
  const controllerRef = useRef(null);
  const statusAnnouncement = useMemo(
    () => run ? `Run status: ${RUN_STATUS_LABELS[run.status] || run.status}` : '',
    [run?.status],
  );
  const canAcknowledge = run && ['WAITING_ACK', 'ESCALATED'].includes(run.status);

  useEffect(() => {
    setRun(null);
    setPlan(null);
    setPlanError(null);
    setLoading(true);
    setPollErrors(0);
    setAckMessage('');
    setVoiceFailed(false);
    let active = true;
    let controller = null;
    const makeController = () => {
      controller = createRunPollingController({
        runId,
        loadRun: getRun,
        onRun: (nextRun) => {
          if (!active) return;
          setRun(nextRun);
          setLoading(false);
          setPollErrors(0);
        },
        onError: (_error, count) => {
          if (!active) return;
          setPollErrors(count);
          setLoading(false);
        },
      });
      controllerRef.current = controller;
    };
    getRun(runId)
      .then((initialRun) => {
        if (!active) return;
        setRun(initialRun);
        setLoading(false);
        makeController();
        controller.start(initialRun);
      })
      .catch(() => {
        if (!active) return;
        setLoading(false);
        setPollErrors(1);
        makeController();
        controller.start();
      });
    return () => {
      active = false;
      controller?.stop();
      if (controllerRef.current === controller) controllerRef.current = null;
    };
  }, [runId]);

  useEffect(() => {
    if (!run?.site_id || !run?.plan_id) return undefined;
    let active = true;
    const date = run.plan_id.slice(run.site_id.length + 1);
    getPlan(run.site_id, date)
      .then(({ plan: nextPlan }) => {
        if (active) {
          setPlan(nextPlan);
          setPlanError(null);
        }
      })
      .catch((error) => {
        if (active) setPlanError(safeErrorMessage(error));
      });
    return () => { active = false; };
  }, [run?.site_id, run?.plan_id]);

  useEffect(() => {
    if (!run?.ack_deadline || !canAcknowledge) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [run?.ack_deadline, canAcknowledge]);

  const submitAcknowledgement = async (event) => {
    event.preventDefault();
    if (!run) return;
    setAckPending(true);
    setAckMessage('');
    try {
      await ack(run.run_id, ackName.trim() || undefined);
      setAckMessage('Acknowledgement sent.');
      await controllerRef.current?.refresh();
    } catch (error) {
      if (error?.status === 409 || error?.code === 'conflict') {
        try {
          const current = await getRun(run.run_id);
          setRun(current);
          setAckMessage(`Already closed — current status: ${RUN_STATUS_LABELS[current.status] || current.status}`);
        } catch (refreshError) {
          setAckMessage(`Already closed. ${safeErrorMessage(refreshError)}`);
        }
      } else {
        setAckMessage(safeErrorMessage(error));
      }
    } finally {
      setAckPending(false);
    }
  };

  if (loading && !run) {
    return (
      <section className="card" aria-busy="true">
        <h1 className="page-title">Loading run…</h1>
        <p>Fetching the run timeline.</p>
      </section>
    );
  }

  if (!run) {
    return (
      <section className="error-card" role="alert">
        <h1 className="error-title">Run not available</h1>
        <p className="error-msg">{pollErrors ? 'Unable to load this run. Retrying…' : 'Run data was not returned.'}</p>
        <a className="return-link" href="#/">Return to Sites</a>
      </section>
    );
  }

  const events = run.events || [];
  const fixture = isFixtureData(run);
  const voiceUrl = run.voice_url;

  return (
    <div className="run-page">
      <div className="run-page-heading">
        <div>
          <a href={`#/site/${encodeURIComponent(run.site_id)}`} className="run-back-link">← Back to site</a>
          <h1 className="page-title">Run timeline</h1>
          <p className="page-desc">Run ID: {run.run_id}</p>
        </div>
        <span className={statusClass(run.status)}>{RUN_STATUS_LABELS[run.status] || run.status}</span>
      </div>

      {fixture && (
        <div className="fixture-banner" role="status">
          <strong>DEMO DATA (fixture)</strong>
        </div>
      )}

      <p className="run-live-status" aria-live="polite" aria-atomic="true">{statusAnnouncement}</p>
      {pollErrors > 0 && <p className="run-connection-warning" role="status">connection lost, retrying</p>}

      <section className="card run-tracker-card" aria-labelledby="run-tracker-heading">
        <h2 id="run-tracker-heading" className="card-title">Delivery stages</h2>
        <ol className="run-stage-tracker">
          {[
            ['plan', 'Plan built'],
            ['supervisor', 'Supervisor notified'],
            ['backup', 'Backup notified'],
          ].map(([key, label]) => {
            const state = stageState(run, key);
            return (
              <li key={key} className={`run-stage run-stage-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
                <span className="run-stage-marker" aria-hidden="true">{state === 'complete' ? '✓' : key === 'plan' ? '1' : key === 'supervisor' ? '2' : '3'}</span>
                <span>{label}</span>
                <span className="run-stage-state">{state === 'complete' ? 'Complete' : state === 'current' ? 'Current' : 'Pending'}</span>
              </li>
            );
          })}
        </ol>
        {canAcknowledge && (
          <p className="run-countdown" role="timer">
            Acknowledgement deadline: <strong>{formatCountdown(run.ack_deadline, now)}</strong>
          </p>
        )}
      </section>

      <div className="plan-two-col run-detail-grid">
        <section className="card" aria-labelledby="run-summary-heading">
          <h2 id="run-summary-heading" className="card-title">Plan summary</h2>
          <p><strong>Plan:</strong> {run.plan_id || 'Unavailable'}</p>
          <p><strong>Status:</strong> {RUN_STATUS_LABELS[run.status] || run.status}</p>
          {plan ? (
            <>
              <p><strong>Heat level:</strong> {plan.summary?.worst_level || 'UNKNOWN'}</p>
              <p><strong>Peak WBGT:</strong> {plan.summary?.peak_wbgt_c == null ? 'Unavailable' : `${plan.summary.peak_wbgt_c.toFixed(1)}°C`}</p>
            </>
          ) : (
            <p role={planError ? 'alert' : undefined}>{planError ? `Plan summary unavailable: ${planError}` : 'Loading plan summary…'}</p>
          )}
          <a href={`#/site/${encodeURIComponent(run.site_id)}`}>View site plan</a>
        </section>

        {voiceUrl && (
          <section className="card voice-player-card" aria-labelledby="voice-player-heading">
            <h2 id="voice-player-heading" className="card-title">Hindi voice message</h2>
            <audio controls preload="none" src={voiceUrl} onError={() => setVoiceFailed(true)}>
              Your browser does not support audio playback.
            </audio>
            {voiceFailed && <p role="alert">voice link expired (links last 1 hour)</p>}
            <a href={voiceUrl} target="_blank" rel="noreferrer">Open Hindi voice message</a>
          </section>
        )}
      </div>

      {canAcknowledge && (
        <section className="card run-ack-card" aria-labelledby="ack-heading">
          <h2 id="ack-heading" className="card-title">Web acknowledgement</h2>
          <form onSubmit={submitAcknowledgement}>
            <label htmlFor="ack-name">Your name (optional)</label>
            <input id="ack-name" name="ack-name" value={ackName} onChange={(event) => setAckName(event.target.value)} maxLength="60" />
            <button className="btn-view-plan" type="submit" disabled={ackPending}>
              {ackPending ? 'Acknowledging…' : 'Acknowledge (web)'}
            </button>
          </form>
          {ackMessage && <p role="status" className="run-action-message">{ackMessage}</p>}
        </section>
      )}

      <section className="card run-timeline-card" aria-labelledby="event-timeline-heading">
        <h2 id="event-timeline-heading" className="card-title">Event timeline</h2>
        {events.length ? (
          <ol className="run-event-list">
            {events.map((event, index) => (
              <li key={`${event.ts}-${event.step}-${index}`} className="run-event">
                <time dateTime={event.ts}>{formatEventTime(event.ts)}</time>
                <div>
                  <strong>{RUN_EVENT_LABELS[event.step] || event.step}</strong>
                  {event.detail && <p>{event.detail.replace(/https?:\/\/\S+/gi, '[link hidden]')}</p>}
                </div>
              </li>
            ))}
          </ol>
        ) : <p>No run events recorded yet.</p>}
      </section>
    </div>
  );
}
