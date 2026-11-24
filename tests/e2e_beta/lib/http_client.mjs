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
    const normalizedPath = routePath.startsWith('/') ? routePath : `/${routePath}`;
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
