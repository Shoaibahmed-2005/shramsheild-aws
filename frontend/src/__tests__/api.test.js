import { describe, expect, it } from 'vitest';
import { ApiError, request } from '../api.js';

function response({ ok = true, status = 200, body = {}, headers = {} } = {}) {
  return {
    ok,
    status,
    headers: new Headers(headers),
    json: async () => body,
  };
}

describe('live API request helper', () => {
  it('returns JSON and does not attach the demo key to GET requests', async () => {
    let received;
    const result = await request('/health', {
      baseUrl: 'https://example.test/',
      fetchImpl: async (url, options) => {
        received = { url, options };
        return response({ body: { ok: true } });
      },
    });

    expect(result.data).toEqual({ ok: true });
    expect(received.url).toBe('https://example.test/health');
    expect(received.options.headers['x-demo-key']).toBeUndefined();
  });

  it('maps contract error bodies to ApiError code and message', async () => {
    await expect(request('/sites', {
      baseUrl: 'https://example.test',
      fetchImpl: async () => response({
        ok: false,
        status: 400,
        body: { error: { code: 'bad_request', message: 'Latitude is outside India.' } },
      }),
    })).rejects.toMatchObject({
      name: 'ApiError', code: 'bad_request', message: 'Latitude is outside India.', status: 400,
    });
  });

  it('maps an aborted request to timeout', async () => {
    const fakeFetch = (_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })));
    });
    await expect(request('/health', {
      baseUrl: 'https://example.test', fetchImpl: fakeFetch, timeoutMs: 1,
    })).rejects.toMatchObject({ name: 'ApiError', code: 'timeout' });
  });

  it('keeps the timeout active while parsing the response body', async () => {
    const fakeFetch = async (_url, { signal }) => ({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: () => new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })));
      }),
    });
    await expect(request('/health', {
      baseUrl: 'https://example.test', fetchImpl: fakeFetch, timeoutMs: 1,
    })).rejects.toMatchObject({ name: 'ApiError', code: 'timeout' });
  });

  it('maps fetch failures to network', async () => {
    await expect(request('/health', {
      baseUrl: 'https://example.test',
      fetchImpl: async () => { throw new TypeError('Failed to fetch'); },
    })).rejects.toMatchObject({ name: 'ApiError', code: 'network' });
  });

  it('sends the demo-key header only with POST requests', async () => {
    let received;
    await request('/sites', {
      method: 'POST',
      body: { name: 'Demo' },
      baseUrl: 'https://example.test',
      fetchImpl: async (_url, options) => {
        received = options;
        return response({ body: { site_id: 'demo-01' } });
      },
    });
    expect(received.headers).toHaveProperty('x-demo-key');
    expect(received.headers['Content-Type']).toBe('application/json');
  });
});
