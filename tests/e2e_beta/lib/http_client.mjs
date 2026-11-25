import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';

export function decodeJwtPayload(token) {
  if (typeof token !== 'string' || !token.includes('.')) {
    throw new Error('Invalid JWT format');
  }
  const parts = token.split('.');
  if (parts.length !== 3) {
    throw new Error('JWT must contain 3 segments');
  }
  const padded = parts[1].replace(/-/g, '+').replace(/_/g, '/');
  const json = Buffer.from(padded, 'base64').toString('utf8');
  return JSON.parse(json);
}

export class HttpClient {
  constructor(baseUrl, defaultHeaders = {}) {
    if (!baseUrl) {
      throw new Error('HttpClient requires a non-empty baseUrl');
    }
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.defaultHeaders = { ...defaultHeaders };
  }

  withToken(accessToken) {
    return new HttpClient(this.baseUrl, {
      ...this.defaultHeaders,
      Authorization: `Bearer ${accessToken}`,
    });
  }

  async request(method, routePath, options = {}) {
    const normalizedPath = !routePath
      ? ''
      : routePath.startsWith('/')
        ? routePath
        : `/${routePath}`;
    const url = new URL(`${this.baseUrl}${normalizedPath}`);
    if (options.query) {
      for (const [key, val] of Object.entries(options.query)) {
        if (val !== undefined && val !== null) {
          url.searchParams.set(key, String(val));
        }
      }
    }

    const headers = {
      ...this.defaultHeaders,
      ...(options.headers || {}),
    };

    if (options.token) {
      headers.Authorization = `Bearer ${options.token}`;
    }

    let bodyPayload;
    if (options.rawBody !== undefined) {
      bodyPayload = options.rawBody;
    } else if (options.body !== undefined) {
      bodyPayload = JSON.stringify(options.body);
      if (!headers['Content-Type'] && !headers['content-type']) {
        headers['Content-Type'] = 'application/json';
      }
    }

    const startedAt = performance.now();
    let response;
    try {
      const controller = options.timeoutMs ? new AbortController() : null;
      const timer = controller
        ? setTimeout(() => controller.abort(), options.timeoutMs)
        : null;
      try {
        response = await fetch(url, {
          method,
          headers,
          body: bodyPayload,
          signal: controller?.signal,
        });
      } finally {
        if (timer) clearTimeout(timer);
      }
    } catch (err) {
      const durationMs = Math.round((performance.now() - startedAt) * 100) / 100;
      if (options.allowNetworkError) {
        return {
          ok: false,
          networkError: true,
          status: 0,
          headers: new Headers(),
          text: '',
          json: null,
          durationMs,
          error: err,
        };
      }
      throw err;
    }

    const durationMs = Math.round((performance.now() - startedAt) * 100) / 100;
    const rawText = await response.text();
    let parsedJson = null;
    if (rawText.trim().length > 0) {
      try {
        parsedJson = JSON.parse(rawText);
      } catch {
        parsedJson = null;
      }
    }

    return {
      ok: response.ok,
      networkError: false,
      status: response.status,
      headers: response.headers,
      text: rawText,
      json: parsedJson,
      durationMs,
    };
  }

  get(routePath, options = {}) {
    return this.request('GET', routePath, options);
  }

  post(routePath, bodyOrOptions = {}, extraOptions = {}) {
    const opts =
      bodyOrOptions &&
      ('body' in bodyOrOptions || 'rawBody' in bodyOrOptions || 'headers' in bodyOrOptions)
        ? { ...bodyOrOptions, ...extraOptions }
        : { body: bodyOrOptions, ...extraOptions };
    return this.request('POST', routePath, opts);
  }

  put(routePath, body, options = {}) {
    return this.request('PUT', routePath, { body, ...options });
  }

  delete(routePath, options = {}) {
    return this.request('DELETE', routePath, options);
  }
}

export async function registerUser(client, { email, password, name }) {
  const res = await client.post('/auth/register', { email, password, name });
  return res;
}

export async function loginUser(client, { email, password }) {
  const res = await client.post('/auth/login', { email, password });
  return res;
}

export async function registerAndLogin(client, { email, password, name = 'WanderAI Traveler' }) {
  const reg = await registerUser(client, { email, password, name });
  if (reg.status === 201 && reg.json?.data?.access_token) {
    return {
      accessToken: reg.json.data.access_token,
      refreshToken: reg.json.data.refresh_token,
      registerResponse: reg,
    };
  }
  const login = await loginUser(client, { email, password });
  if (login.status === 200 && login.json?.data?.access_token) {
    return {
      accessToken: login.json.data.access_token,
      refreshToken: login.json.data.refresh_token,
      loginResponse: login,
    };
  }
  throw new Error(
    `Failed to register or login ${email}: reg=${reg.status} ${reg.text}, login=${login.status} ${login.text}`,
  );
}

const haLongCache = new Map();

export async function resolveHaLongDestination(client) {
  if (haLongCache.has(client.baseUrl)) {
    return haLongCache.get(client.baseUrl);
  }
  const promise = (async () => {
    const res = await client.get('/destinations', { query: { limit: 100 } });
    if (res.status === 200 && res.json?.success === true) {
      const items = res.json?.data?.items || res.json?.data;
      if (Array.isArray(items)) {
        const match = items.find((d) => d.slug === 'ha-long');
        if (match) return match;
      }
    }
    const poiRes = await client.get('/places/65562a67-84ff-44a0-990d-31917a2a9bd0');
    if (
      poiRes.status === 200 &&
      poiRes.json?.success === true &&
      poiRes.json?.data?.destination?.slug === 'ha-long'
    ) {
      return poiRes.json.data.destination;
    }
    throw new Error(
      `Could not resolve ha-long destination from ${client.baseUrl} (GET /destinations status=${res.status})`,
    );
  })().catch((err) => {
    haLongCache.delete(client.baseUrl);
    throw err;
  });

  haLongCache.set(client.baseUrl, promise);
  return promise;
}

export async function resolveVerifiedNullFieldPlace(
  client,
  predicate,
  label = 'verified null-field Hạ Long place',
) {
  const haLong = await resolveHaLongDestination(client);
  const firstPageRes = await client.get('/places', {
    query: { destinationId: haLong.id, verifiedOnly: true, page: 1, limit: 50 },
  });
  assert.equal(
    firstPageRes.status,
    200,
    `GET /places failed while searching for ${label}: ${firstPageRes.status} ${firstPageRes.text}`,
  );
  const firstData = firstPageRes.json?.data || {};
  const totalPages = Math.max(1, Number(firstData.totalPages || 1));
  const candidates = [...(firstData.items || [])];

  for (let p = 2; p <= totalPages; p++) {
    const nextRes = await client.get('/places', {
      query: { destinationId: haLong.id, verifiedOnly: true, page: p, limit: 50 },
    });
    if (nextRes.status === 200 && Array.isArray(nextRes.json?.data?.items)) {
      candidates.push(...nextRes.json.data.items);
    }
  }

  for (const cand of candidates) {
    const detailRes = await client.get(`/places/${cand.id}`);
    if (detailRes.status !== 200 || detailRes.json?.success !== true) continue;
    const place = detailRes.json.data;
    if (place && place.isVerified === true && predicate(place)) {
      return place;
    }
  }

  throw new Error(
    `No verified Hạ Long place matched ${label} across ${candidates.length} candidates`,
  );
}

export async function fetchResetToken(client, cfg, email) {
  if (cfg.mode === 'self-test') {
    const outbox = await client.get('/_test/mail-outbox', { query: { email } });
    assert.equal(outbox.status, 200, `Self-test mail outbox failed: ${outbox.text}`);
    const items = outbox.json?.data?.items || [];
    assert.ok(items.length > 0, `No reset email found in self-test outbox for ${email}`);
    return items[items.length - 1].rawToken;
  }
  if (process.env.E2E_TEST_RESET_TOKEN) {
    return process.env.E2E_TEST_RESET_TOKEN;
  }
  if (process.env.E2E_MAIL_OUTBOX_URL) {
    const outboxClient = new HttpClient(process.env.E2E_MAIL_OUTBOX_URL);
    const res = await outboxClient.get('', { query: { email } });
    if (res.json?.token) return res.json.token;
    if (res.json?.data?.token) return res.json.data.token;
    if (res.json?.data?.items?.length) {
      return res.json.data.items[res.json.data.items.length - 1].rawToken;
    }
    if (res.json?.items?.length) {
      return res.json.items[res.json.items.length - 1].rawToken;
    }
    throw new Error(
      `E2E_MAIL_OUTBOX_URL returned no reset token for ${email} (status=${res.status}: ${res.text})`,
    );
  }
  throw new Error('Live mode reset test requires E2E_MAIL_OUTBOX_URL or E2E_TEST_RESET_TOKEN');
}

export async function resolveExpiredResetToken(client, cfg, email) {
  if (cfg.mode === 'self-test') {
    const seeded = await client.post('/_test/seed-expired-reset-token', { email });
    assert.equal(seeded.status, 200, `Failed to seed expired token: ${seeded.text}`);
    const tok = seeded.json?.data?.token;
    assert.ok(typeof tok === 'string' && tok.length > 0, 'Seeded expired token must be non-empty');
    return tok;
  }
  if (process.env.E2E_EXPIRED_RESET_SEED_URL) {
    const seedClient = new HttpClient(process.env.E2E_EXPIRED_RESET_SEED_URL);
    const res = await seedClient.post('', { email });
    assert.equal(
      res.status,
      200,
      `E2E_EXPIRED_RESET_SEED_URL failed (${res.status}): ${res.text}`,
    );
    const tok = res.json?.data?.token || res.json?.token;
    assert.ok(
      typeof tok === 'string' && tok.length > 0,
      `E2E_EXPIRED_RESET_SEED_URL returned empty token: ${res.text}`,
    );
    return tok;
  }
  if (process.env.E2E_EXPIRED_RESET_TOKEN) {
    return process.env.E2E_EXPIRED_RESET_TOKEN;
  }
  throw new Error(
    'Live mode RESET_TOKEN_EXPIRED test requires E2E_EXPIRED_RESET_SEED_URL or E2E_EXPIRED_RESET_TOKEN',
  );
}
