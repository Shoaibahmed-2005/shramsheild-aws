/**
 * ShramShield API Client
 * Follows contract: docs/BUILD_PLAN.md section 3.9 & P3.1 step 4
 */

import sitesFixture from './fixtures/sites.json';
import planChennaiFixture from './fixtures/plan_chennai_moderate.json';
import runWaitingFixture from './fixtures/run_waiting.json';
import runEscalatedFixture from './fixtures/run_escalated.json';
import runAcknowledgedFixture from './fixtures/run_acknowledged.json';
import runUnacknowledgedFixture from './fixtures/run_unacknowledged.json';
import backtestFixture from './fixtures/backtest.json';

const API_BASE = import.meta.env.VITE_API_BASE || '';
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true' || !API_BASE;

function delay(ms = 300) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * List all worksites.
 * @returns {Promise<{ sites: Array }>}
 */
export async function listSites() {
  await delay(300);
  return {
    sites: JSON.parse(JSON.stringify(sitesFixture.sites))
  };
}

/**
 * Get site details by ID.
 * @param {string} id
 * @returns {Promise<Object>}
 */
export async function getSite(id) {
  await delay(300);
  const site = sitesFixture.sites.find((s) => s.site_id === id);
  if (!site) {
    const err = new Error(`Site ${id} not found`);
    err.code = 'not_found';
    err.status = 404;
    throw err;
  }
  return JSON.parse(JSON.stringify(site));
}

/**
 * Get site daily heat-stress plan.
 * Mock plan exists ONLY for chn-01; other sites reject with not_found
 * to exercise the error UI.
 * @param {string} id
 * @param {string} [date]
 * @returns {Promise<Object>}
 */
export async function getPlan(id, date) {
  await delay(300);
  if (id === 'chn-01') {
    const plan = JSON.parse(JSON.stringify(planChennaiFixture));
    if (date) {
      plan.date = date;
    }
    return plan;
  }
  const err = new Error(`No plan available for site ${id}. In mock mode, only chn-01 has a precomputed plan.`);
  err.code = 'not_found';
  err.status = 404;
  throw err;
}

/**
 * Get latest run for site.
 * @param {string} id
 * @returns {Promise<Object>}
 */
export async function getLatestRun(id) {
  await delay(300);
  if (id === 'chn-01') {
    return JSON.parse(JSON.stringify(runWaitingFixture));
  }
  const err = new Error(`No runs found for site ${id}`);
  err.code = 'not_found';
  err.status = 404;
  throw err;
}

/**
 * Get run by ID.
 * @param {string} runId
 * @returns {Promise<Object>}
 */
export async function getRun(runId) {
  await delay(300);
  const runs = [runWaitingFixture, runEscalatedFixture, runAcknowledgedFixture, runUnacknowledgedFixture];
  const found = runs.find((r) => r.run_id === runId);
  if (found) {
    return JSON.parse(JSON.stringify(found));
  }
  // Default to waiting fixture if mock
  return JSON.parse(JSON.stringify(runWaitingFixture));
}

/**
 * Start a workflow run for site.
 * @param {string} id
 * @param {Object} [options]
 * @returns {Promise<{ run_id: string, status: string }>}
 */
export async function startRun(id, options = {}) {
  await delay(300);
  const nowStr = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
  return {
    run_id: `${id}_${nowStr}`,
    status: 'STARTED'
  };
}

/**
 * Acknowledge an active run.
 * @param {string} runId
 * @param {string} [by]
 * @returns {Promise<{ ok: boolean, status: string }>}
 */
export async function ack(runId, by = 'Site Supervisor') {
  await delay(300);
  return {
    ok: true,
    status: 'ACKNOWLEDGED'
  };
}

/**
 * Create a new worksite.
 * @param {Object} site
 * @returns {Promise<Object>}
 */
export async function createSite(site) {
  await delay(300);
  return {
    ...site,
    site_id: site.site_id || `site-${Math.random().toString(36).substring(2, 8)}`
  };
}

/**
 * Get historical backtest results (April-June 2024).
 * @returns {Promise<Object>}
 */
export async function getBacktest() {
  await delay(300);
  return JSON.parse(JSON.stringify(backtestFixture));
}

export const isMockMode = USE_MOCK;
