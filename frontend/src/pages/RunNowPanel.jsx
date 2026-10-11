import React, { useEffect, useReducer, useRef, useState } from 'react';
import { getLatestRun, startRun } from '../api.js';
import { ACTIVE_RUN_STATUSES, RUN_STATUS_LABELS, latestRunViewState, runConfirmationReducer } from '../runWorkflow.js';

function safeErrorMessage(error) {
  return (error?.message || 'The request could not be completed.')
    .replace(/https?:\/\/\S+/gi, '[link hidden]');
}

export function RunNowPanel({ site }) {
  const [dialogOpen, dispatchDialog] = useReducer(runConfirmationReducer, false);
  const [timeoutChoice, setTimeoutChoice] = useState('default');
  const [submitting, setSubmitting] = useState(false);
  const [startError, setStartError] = useState(null);
  const [activeRun, setActiveRun] = useState(null);
  const [latestRun, setLatestRun] = useState(null);
  const [latestError, setLatestError] = useState(null);
  const [latestLoading, setLatestLoading] = useState(true);
  const sendButtonRef = useRef(null);
  const confirmButtonRef = useRef(null);

  const loadLatestRun = async () => {
    setLatestLoading(true);
    setLatestError(null);
    try {
      setLatestRun(await getLatestRun(site.site_id));
    } catch (error) {
      setLatestError(error);
      setLatestRun(null);
    } finally {
      setLatestLoading(false);
    }
  };

  useEffect(() => {
    loadLatestRun();
  }, [site.site_id]);

  useEffect(() => {
    if (!dialogOpen) {
      sendButtonRef.current?.focus();
      return undefined;
    }
    confirmButtonRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !submitting) {
        event.preventDefault();
        dispatchDialog('cancel');
      }
      if (event.key === 'Tab') {
        const buttons = document.querySelectorAll('[data-run-dialog] button:not(:disabled), [data-run-dialog] input:not(:disabled)');
        const first = buttons[0];
        const last = buttons[buttons.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [dialogOpen, submitting]);

  const confirmRun = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStartError(null);
    setActiveRun(null);
    try {
      const options = timeoutChoice === 'default'
        ? {}
        : { ack_timeout_seconds: Number(timeoutChoice) };
      const result = await startRun(site.site_id, options);
      window.location.hash = `#/run/${encodeURIComponent(result.run_id)}`;
    } catch (error) {
      setStartError(safeErrorMessage(error));
      if (error?.status === 409 || error?.code === 'conflict') {
        try {
          const latest = await getLatestRun(site.site_id);
          if (ACTIVE_RUN_STATUSES.has(latest.status)) setActiveRun(latest);
        } catch (latestError) {
          if (latestError?.status !== 404 && latestError?.code !== 'not_found') {
            setStartError(`${safeErrorMessage(error)} ${safeErrorMessage(latestError)}`);
          }
        }
      }
    } finally {
      setSubmitting(false);
      dispatchDialog('confirm');
      loadLatestRun();
    }
  };

  const latestState = latestRunViewState({ loading: latestLoading, run: latestRun, error: latestError });

  return (
    <section className="card run-now-card" aria-labelledby="run-now-heading">
      <h2 id="run-now-heading" className="card-title">Run now</h2>
      <p className="run-now-help">Send this site’s plan to its supervisor for acknowledgement.</p>
      <button
        ref={sendButtonRef}
        type="button"
        className="btn-view-plan"
        onClick={() => { setStartError(null); dispatchDialog('open'); }}
      >
        Send today&apos;s plan now
      </button>
      {startError && <p className="error-msg run-action-message" role="alert">{startError}</p>}
      {activeRun && (
        <p className="run-action-message" role="status">
          Active run: <a href={`#/run/${encodeURIComponent(activeRun.run_id)}`}>{activeRun.run_id}</a>
        </p>
      )}

      <section className="last-run" aria-labelledby="last-run-heading" aria-busy={latestLoading}>
        <h3 id="last-run-heading">Last run</h3>
        {latestState === 'loading' && <p>Loading latest run…</p>}
        {latestState === 'empty' && <p>No runs yet</p>}
        {latestState === 'error' && (
          <div role="alert">
            <p>{safeErrorMessage(latestError)}</p>
            <button type="button" className="btn-retry" onClick={loadLatestRun}>Retry latest run</button>
          </div>
        )}
        {latestState === 'run' && (
          <div>
            {latestRun._fixture === true && (
              <p className="fixture-banner run-fixture-badge"><strong>DEMO DATA (fixture)</strong></p>
            )}
            <p>Status: {RUN_STATUS_LABELS[latestRun.status] || latestRun.status}</p>
            <p>Created: {latestRun.created_at || 'Time unavailable'}</p>
            <a href={`#/run/${encodeURIComponent(latestRun.run_id)}`}>View run timeline</a>
          </div>
        )}
      </section>

      {dialogOpen && (
        <div className="run-dialog-backdrop">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="run-confirm-heading"
            data-run-dialog
            className="run-confirm-dialog"
          >
            <h2 id="run-confirm-heading">Confirm plan dispatch</h2>
            <p>This sends a real Telegram message to {site.supervisor?.name || 'the site supervisor'}.</p>
            <form onSubmit={confirmRun}>
              <fieldset>
                <legend>Acknowledgement timeout</legend>
                <label><input type="radio" name="run-timeout" value="30" checked={timeoutChoice === '30'} onChange={(event) => setTimeoutChoice(event.target.value)} /> 30 seconds</label>
                <label><input type="radio" name="run-timeout" value="60" checked={timeoutChoice === '60'} onChange={(event) => setTimeoutChoice(event.target.value)} /> 60 seconds</label>
                <label><input type="radio" name="run-timeout" value="300" checked={timeoutChoice === '300'} onChange={(event) => setTimeoutChoice(event.target.value)} /> 5 minutes</label>
                <label><input type="radio" name="run-timeout" value="default" checked={timeoutChoice === 'default'} onChange={(event) => setTimeoutChoice(event.target.value)} /> Site default</label>
              </fieldset>
              <div className="run-dialog-actions">
                <button ref={confirmButtonRef} className="btn-view-plan" type="submit" disabled={submitting}>
                  {submitting ? 'Starting…' : 'Confirm'}
                </button>
                <button className="btn-retry" type="button" disabled={submitting} onClick={() => dispatchDialog('cancel')}>
                  Cancel
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </section>
  );
}
