/**
 * ShramShield API client. Implements the HTTP contract in BUILD_PLAN.md 3.9.
 */

import sitesFixture from './fixtures/sites.json';
import planChennaiFixture from './fixtures/plan_chennai_moderate.json';
import backtestFixture from './fixtures/backtest.json';
import { createMockRunStore } from './mockRunWorkflow.js';

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '');
const DEMO_KEY = import.meta.env.VITE_DEMO_KEY || '';
const LIVE_MODE = import.meta.env.VITE_USE_MOCK === 'false' && Boolean(API_BASE);
const REQUEST_TIMEOUT_MS = 10_000;

let mockSites = clone(sitesFixture.sites);
const mockRuns = createMockRunStore();

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function delay(ms = 300) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export class ApiError extends Error {
  constructor(code, message, status = null) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

function buildUrl(baseUrl, path) {
  return `${baseUrl.replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`;
}

/** Request JSON from the deployed API. Exported for focused client tests. */
export async function request(path, {
  method = 'GET',
  body,
  baseUrl = API_BASE,
  fetchImpl = fetch,
  timeoutMs = REQUEST_TIMEOUT_MS,
} = {}) {
  if (!baseUrl) {
    throw new ApiError('configuration', 'The live API base URL is not configured.');
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const headers = { Accept: 'application/json' };
  const isPost = method.toUpperCase() === 'POST';

  if (isPost) {
    headers['Content-Type'] = 'application/json';
    headers['x-demo-key'] = DEMO_KEY;
  }

  let response;
  try {
    response = await fetchImpl(buildUrl(baseUrl, path), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (error) {
    clearTimeout(timeout);
    if (controller.signal.aborted || error?.name === 'AbortError') {
      throw new ApiError('timeout', 'The API request timed out. Please retry.');
    }
    throw new ApiError('network', 'The API could not be reached. Check your connection and retry.');
  }

  let payload;
  try {
    payload = await response.json();
  } catch (error) {
    if (controller.signal.aborted || error?.name === 'AbortError') {
      throw new ApiError('timeout', 'The API request timed out. Please retry.');
    }
    throw new ApiError('invalid_response', 'The API returned an invalid JSON response.', response.status);
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    const apiError = payload?.error;
    throw new ApiError(
      apiError?.code || 'request_failed',
      apiError?.message || `The API request failed (${response.status}).`,
      response.status,
    );
  }

  return { data: payload, headers: response.headers };
}

const mockApi = {
  async listSites() {
    await delay();
    return { sites: clone(mockSites) };
  },

  async getSite(id) {
    await delay();
    const site = mockSites.find((item) => item.site_id === id);
    if (!site) throw new ApiError('not_found', `Site ${id} not found`, 404);
    return clone(site);
  },

  async getPlan(id, date) {
    await delay();
    if (id !== 'chn-01') {
      throw new ApiError('not_found', 'No plan is available for this site in mock mode.', 404);
    }
    const plan = clone(planChennaiFixture);
    if (date) plan.date = date;
    return { plan, cache: null };
  },

  async getLatestRun(id) {
    await delay();
    const run = mockRuns.getLatestRun(id);
    if (run) return run;
    throw new ApiError('not_found', `No runs found for site ${id}`, 404);
  },

  async getRun(runId) {
    await delay();
    const run = mockRuns.getRun(runId);
    if (run) return run;
    throw new ApiError('not_found', `Run ${runId} not found`, 404);
  },

  async startRun(id, options = {}) {
    await delay();
    const site = mockSites.find((item) => item.site_id === id);
    if (!site) throw new ApiError('not_found', `Site ${id} not found`, 404);
    return mockRuns.startRun(site, options);
  },

  async ack(runId, by = 'Site Supervisor') {
    await delay();
    const run = mockRuns.getRun(runId);
    if (!run) throw new ApiError('not_found', `Run ${runId} not found`, 404);
    if (['ACKNOWLEDGED', 'UNACKNOWLEDGED', 'FAILED'].includes(run.status)) {
      throw new ApiError('conflict', `Run is already closed with status ${run.status}.`, 409);
    }
    return mockRuns.acknowledge(runId, by);
  },

  async createSite(site) {
    await delay();
    const created = {
      ...clone(site),
      site_id: site.site_id || `site-${Math.random().toString(36).slice(2, 8)}`,
    };
    mockSites = [...mockSites, created];
    return clone(created);
  },

  async getBacktest() {
    await delay();
    return clone(backtestFixture);
  },

  async getHealth() {
    await delay();
    return { ok: true, version: '0.1.0', _fixture: true };
  },
};

const liveApi = {
  async listSites() {
    return (await request('/sites')).data;
  },

  async getSite(id) {
    return (await request(`/sites/${encodeURIComponent(id)}`)).data;
  },

  async getPlan(id, date) {
    const query = date ? `?date=${encodeURIComponent(date)}` : '';
    const result = await request(`/sites/${encodeURIComponent(id)}/plan${query}`);
    return { plan: result.data, cache: result.headers.get('x-cache') };
  },

  async getLatestRun(id) {
    return (await request(`/sites/${encodeURIComponent(id)}/runs/latest`)).data;
  },

  async getRun(runId) {
    return (await request(`/runs/${encodeURIComponent(runId)}`)).data;
  },

  async startRun(id, options = {}) {
    return (await request(`/sites/${encodeURIComponent(id)}/run`, { method: 'POST', body: options })).data;
  },

  async ack(runId, by) {
    return (await request('/ack', { method: 'POST', body: { run_id: runId, by } })).data;
  },

  async createSite(site) {
    return (await request('/sites', { method: 'POST', body: site })).data;
  },

  async getBacktest() {
    throw new ApiError('not_available', 'Backtest data is not available from the live API yet.');
  },

  async getHealth() {
    return (await request('/health')).data;
  },
};

const api = LIVE_MODE ? liveApi : mockApi;

export const listSites = (...args) => api.listSites(...args);
export const getSite = (...args) => api.getSite(...args);
export const getPlan = (...args) => api.getPlan(...args);
export const getLatestRun = (...args) => api.getLatestRun(...args);
export const getRun = (...args) => api.getRun(...args);
export const startRun = (...args) => api.startRun(...args);
export const ack = (...args) => api.ack(...args);
export const createSite = (...args) => api.createSite(...args);
export const getBacktest = (...args) => api.getBacktest(...args);
export const getHealth = (...args) => api.getHealth(...args);
export const isMockMode = !LIVE_MODE;
