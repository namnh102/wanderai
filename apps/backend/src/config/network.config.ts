import { CorsOptions } from '@nestjs/common/interfaces/external/cors-options.interface';

export const DEFAULT_BACKEND_PORT = 3000;

export const DEFAULT_DEV_CORS_ORIGINS: readonly string[] = [
  'http://localhost:4200',
  'http://localhost:5000',
  'http://localhost:3000',
  'http://127.0.0.1:4200',
  'http://127.0.0.1:5000',
];

const DISALLOWED_PRODUCTION_HOSTS = new Set([
  'localhost',
  '127.0.0.1',
  '::1',
  '[::1]',
  '0.0.0.0',
  '10.0.2.2',
]);

export interface ResolvedNetworkConfig {
  port: number;
  host?: string;
  corsOrigins: string[];
  nodeEnv: string;
}

export function resolvePort(rawPort: unknown): number {
  if (rawPort === undefined || rawPort === null) {
    return DEFAULT_BACKEND_PORT;
  }

  const trimmed = String(rawPort).trim();
  if (trimmed.length === 0) {
    return DEFAULT_BACKEND_PORT;
  }

  if (!/^\d+$/.test(trimmed)) {
    throw new Error(
      `Invalid PORT configuration "${trimmed}": must be an integer between 1 and 65535.`,
    );
  }

  const parsed = Number.parseInt(trimmed, 10);
  if (!Number.isSafeInteger(parsed) || parsed < 1 || parsed > 65535) {
    throw new Error(
      `Invalid PORT configuration "${trimmed}": must be an integer between 1 and 65535.`,
    );
  }

  return parsed;
}

export function resolveHost(rawHost: unknown): string | undefined {
  if (rawHost === undefined || rawHost === null) {
    return undefined;
  }

  const trimmed = String(rawHost).trim();
  if (trimmed.length === 0) {
    return undefined;
  }

  if (
    /\s/.test(trimmed) ||
    trimmed.includes('://') ||
    trimmed.includes('/') ||
    trimmed.includes('?') ||
    trimmed.includes('#')
  ) {
    throw new Error(
      `Invalid HOST configuration "${trimmed}": must be a valid IP address or hostname without protocol or path.`,
    );
  }

  return trimmed;
}

export function parseAndValidateCorsOrigins(
  rawOrigins: unknown,
  nodeEnv: unknown = 'development',
): string[] {
  const normalizedEnv =
    typeof nodeEnv === 'string' && nodeEnv.trim().length > 0
      ? nodeEnv.trim().toLowerCase()
      : 'development';
  const isProduction = normalizedEnv === 'production';

  const rawString = typeof rawOrigins === 'string' ? rawOrigins.trim() : '';
  if (rawString.length === 0) {
    if (isProduction) {
      throw new Error(
        'Invalid CORS_ORIGINS configuration: explicit CORS allowlist is required when NODE_ENV=production.',
      );
    }
    return [...DEFAULT_DEV_CORS_ORIGINS];
  }

  const candidates = rawString
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);

  if (candidates.length === 0) {
    throw new Error(
      'Invalid CORS_ORIGINS configuration: at least one valid origin is required.',
    );
  }

  const deduplicated: string[] = [];
  const seen = new Set<string>();

  for (const candidate of candidates) {
    if (candidate === '*' || candidate.includes('*')) {
      throw new Error(
        `Invalid CORS_ORIGINS configuration "${candidate}": wildcard origins are forbidden when credentials are enabled.`,
      );
    }

    if (candidate.toLowerCase() === 'null') {
      throw new Error(
        'Invalid CORS_ORIGINS configuration: "null" origin is forbidden.',
      );
    }

    if (candidate.endsWith('/')) {
      throw new Error(
        `Invalid CORS_ORIGINS configuration "${candidate}": origins must not have a trailing slash or path.`,
      );
    }

    let parsed: URL;
    try {
      parsed = new URL(candidate);
    } catch {
      throw new Error(
        `Invalid CORS_ORIGINS configuration "${candidate}": must be a valid http(s) origin.`,
      );
    }

    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new Error(
        `Invalid CORS_ORIGINS configuration "${candidate}": scheme must be http or https.`,
      );
    }

    if (
      parsed.pathname !== '/' ||
      parsed.search.length > 0 ||
      parsed.hash.length > 0 ||
      parsed.username.length > 0 ||
      parsed.password.length > 0
    ) {
      throw new Error(
        `Invalid CORS_ORIGINS configuration "${candidate}": origin must not include path, query, fragment, or credentials.`,
      );
    }

    if (isProduction) {
      if (parsed.protocol !== 'https:') {
        throw new Error(
          `Invalid CORS_ORIGINS configuration "${candidate}": production origins must use https://.`,
        );
      }
      if (DISALLOWED_PRODUCTION_HOSTS.has(parsed.hostname.toLowerCase())) {
        throw new Error(
          `Invalid CORS_ORIGINS configuration "${candidate}": loopback or emulator host "${parsed.hostname}" is forbidden in production.`,
        );
      }
    }

    const normalizedOrigin = parsed.origin;
    if (!seen.has(normalizedOrigin)) {
      seen.add(normalizedOrigin);
      deduplicated.push(normalizedOrigin);
    }
  }

  return deduplicated;
}

export function buildNestCorsOptions(
  allowedOrigins: readonly string[],
): CorsOptions {
  const allowedSet = new Set(allowedOrigins.map((origin) => origin.trim()));

  return {
    origin: (
      requestOrigin: string | undefined,
      callback: (err: Error | null, allow?: boolean) => void,
    ) => {
      // Non-browser clients (Flutter Android/iOS native apps) do not send an Origin header;
      // their access is governed by JWT Bearer authentication guards.
      if (!requestOrigin) {
        callback(null, true);
        return;
      }

      if (allowedSet.has(requestOrigin.trim())) {
        callback(null, true);
        return;
      }

      callback(null, false);
    },
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
    credentials: true,
    optionsSuccessStatus: 204,
  };
}

export function resolveNetworkConfig(
  env: Record<string, string | undefined> = process.env,
): ResolvedNetworkConfig {
  const nodeEnv =
    typeof env.NODE_ENV === 'string' && env.NODE_ENV.trim().length > 0
      ? env.NODE_ENV.trim()
      : 'development';
  const port = resolvePort(env.PORT);
  const host = resolveHost(env.HOST);
  const rawCorsOrigins = env.BACKEND_CORS_ORIGINS ?? env.CORS_ORIGINS;
  const corsOrigins = parseAndValidateCorsOrigins(rawCorsOrigins, nodeEnv);

  return {
    port,
    host,
    corsOrigins,
    nodeEnv,
  };
}
