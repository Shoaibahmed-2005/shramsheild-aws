export const FINAL_RUN_STATUSES = new Set(['ACKNOWLEDGED', 'UNACKNOWLEDGED', 'FAILED']);
export const ACTIVE_RUN_STATUSES = new Set(['STARTED', 'WAITING_ACK', 'ESCALATED']);

export const RUN_STATUS_LABELS = {
  STARTED: 'STARTED',
  WAITING_ACK: 'WAITING FOR ACKNOWLEDGEMENT',
  ESCALATED: 'ESCALATED TO BACKUP',
  ACKNOWLEDGED: 'ACKNOWLEDGED',
  UNACKNOWLEDGED: 'NOT ACKNOWLEDGED',
  FAILED: 'FAILED',
};

export const RUN_EVENT_LABELS = {
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
};

export function formatCountdown(deadline, now = Date.now()) {
  const timestamp = Date.parse(deadline);
  if (!Number.isFinite(timestamp)) return '—';
  const remainingSeconds = Math.max(0, Math.ceil((timestamp - now) / 1000));
  if (remainingSeconds === 0) return 'timed out';
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export function formatEventTime(timestamp) {
  if (!timestamp) return 'Time unavailable';
  if (!Number.isFinite(Date.parse(timestamp))) return 'Time unavailable';
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(timestamp));
}

export function isFixtureData(data) {
  return data?._fixture === true;
}

export function latestRunViewState({ loading, run, error }) {
  if (loading) return 'loading';
  if (error?.status === 404 || error?.code === 'not_found') return 'empty';
  if (error) return 'error';
  return run ? 'run' : 'empty';
}

export function runConfirmationReducer(isOpen, action) {
  if (action === 'open') return true;
  if (action === 'cancel' || action === 'confirm') return false;
  return isOpen;
}

export function createRunPollingController({
  runId,
  loadRun,
  onRun,
  onError,
  visibilityTarget = document,
  intervalMs = 2_000,
  backoffMs = 5_000,
  setTimer = setTimeout,
  clearTimer = clearTimeout,
}) {
  let timer = null;
  let stopped = false;
  let inFlight = false;
  let paused = visibilityTarget.visibilityState === 'hidden';
  let consecutiveErrors = 0;

  const clearScheduledPoll = () => {
    if (timer !== null) {
      clearTimer(timer);
      timer = null;
    }
  };

  const stop = () => {
    if (stopped) return;
    stopped = true;
    clearScheduledPoll();
    visibilityTarget.removeEventListener('visibilitychange', handleVisibilityChange);
  };

  const schedulePoll = (delay) => {
    if (stopped || paused || timer !== null) return;
    timer = setTimer(() => {
      timer = null;
      poll();
    }, delay);
  };

  const poll = async (force = false) => {
    if (stopped || (paused && !force) || inFlight) return;
    inFlight = true;
    try {
      const run = await loadRun(runId);
      if (stopped) return;
      consecutiveErrors = 0;
      onRun(run);
      if (FINAL_RUN_STATUSES.has(run.status)) {
        stop();
        return;
      }
      schedulePoll(intervalMs);
    } catch (error) {
      if (stopped) return;
      consecutiveErrors += 1;
      onError(error, consecutiveErrors);
      schedulePoll(consecutiveErrors >= 3 ? backoffMs : intervalMs);
    } finally {
      inFlight = false;
    }
  };

  function handleVisibilityChange() {
    paused = visibilityTarget.visibilityState === 'hidden';
    if (paused) {
      clearScheduledPoll();
    } else {
      schedulePoll(0);
    }
  }

  const start = (initialRun) => {
    if (stopped) return;
    visibilityTarget.addEventListener('visibilitychange', handleVisibilityChange);
    if (initialRun) {
      onRun(initialRun);
      if (FINAL_RUN_STATUSES.has(initialRun.status)) {
        stop();
      } else {
        schedulePoll(intervalMs);
      }
    } else if (!paused) {
      poll();
    }
  };

  const refresh = () => {
    clearScheduledPoll();
    return poll(true);
  };

  return { start, stop, refresh };
}
