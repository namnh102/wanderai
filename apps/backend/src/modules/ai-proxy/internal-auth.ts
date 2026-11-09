import { createHmac } from 'crypto';

export const INTERNAL_ASSERTION_HEADER = 'X-WanderAI-Internal-Assertion';
export const EXPECTED_ISSUER = 'wanderai-backend';
export const EXPECTED_AUDIENCE = 'wanderai-ai-service';
export const MIN_INTERNAL_SECRET_LENGTH = 32;
export const MIN_INTERNAL_SECRET_UNIQUE_CHARS = 8;

const DISALLOWED_INTERNAL_SECRETS = new Set([
  'super-secret',
  'wanderai-dev-jwt-secret-2026',
  'wanderai-dev-refresh-secret-2026',
  'wanderai-jwt-secret-change-in-production',
  'wanderai-refresh-secret-change-in-production',
  '<replace_with_distinct_internal_service_secret_min_32_chars>',
  'dummy-key-not-used-in-ci',
  'dummy-key-for-openapi-export',
  'changeme',
  'secret',
  'password',
]);

function base64UrlEncode(input: Buffer | string): string {
  const buf = typeof input === 'string' ? Buffer.from(input, 'utf8') : input;
  return buf
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '');
}

export function validateInternalAuthSecret(
  rawSecret: unknown,
  jwtSecret?: unknown,
  jwtRefreshSecret?: unknown,
): string {
  if (typeof rawSecret !== 'string' || rawSecret.trim().length === 0) {
    throw new Error(
      'Invalid internal auth configuration: AI_INTERNAL_AUTH_SECRET is required.',
    );
  }

  const secret = rawSecret.trim();
  const normalized = secret.toLowerCase();

  if (
    DISALLOWED_INTERNAL_SECRETS.has(normalized) ||
    normalized.startsWith('<replace_with_') ||
    normalized.includes('change-in-production') ||
    normalized.includes('wanderai-dev-')
  ) {
    throw new Error(
      'Invalid internal auth configuration: AI_INTERNAL_AUTH_SECRET uses a disallowed placeholder.',
    );
  }

  if (secret.length < MIN_INTERNAL_SECRET_LENGTH) {
    throw new Error(
      `Invalid internal auth configuration: AI_INTERNAL_AUTH_SECRET must be at least ${MIN_INTERNAL_SECRET_LENGTH} characters.`,
    );
  }

  if (new Set(secret).size < MIN_INTERNAL_SECRET_UNIQUE_CHARS) {
    throw new Error(
      'Invalid internal auth configuration: AI_INTERNAL_AUTH_SECRET lacks character diversity.',
    );
  }

  const trimmedJwt = typeof jwtSecret === 'string' ? jwtSecret.trim() : '';
  const trimmedRefresh =
    typeof jwtRefreshSecret === 'string' ? jwtRefreshSecret.trim() : '';

  if (
    (trimmedJwt && secret === trimmedJwt) ||
    (trimmedRefresh && secret === trimmedRefresh)
  ) {
    throw new Error(
      'Invalid internal auth configuration: AI_INTERNAL_AUTH_SECRET must be distinct from JWT_SECRET and JWT_REFRESH_SECRET.',
    );
  }

  return secret;
}

export interface CreateInternalAssertionParams {
  secret: unknown;
  userId: string;
  action: string;
  sessionId?: string;
  nowSeconds?: number;
  ttlSeconds?: number;
  jwtSecret?: unknown;
  jwtRefreshSecret?: unknown;
}

export function createInternalServiceAssertion(
  params: CreateInternalAssertionParams,
): string {
  const validatedSecret = validateInternalAuthSecret(
    params.secret,
    params.jwtSecret,
    params.jwtRefreshSecret,
  );

  const userId = typeof params.userId === 'string' ? params.userId.trim() : '';
  if (!userId) {
    throw new Error('Authenticated userId is required for internal assertion.');
  }

  const action = typeof params.action === 'string' ? params.action.trim() : '';
  if (!action) {
    throw new Error('Request action is required for internal assertion.');
  }

  const iat =
    typeof params.nowSeconds === 'number'
      ? Math.floor(params.nowSeconds)
      : Math.floor(Date.now() / 1000);
  const ttl = typeof params.ttlSeconds === 'number' ? Math.floor(params.ttlSeconds) : 60;
  const sid =
    typeof params.sessionId === 'string' && params.sessionId.trim()
      ? params.sessionId.trim()
      : '';

  // Keep keys sorted alphabetically to match FastAPI canonical JSON encoding
  const canonicalPayload = {
    act: action,
    aud: EXPECTED_AUDIENCE,
    exp: iat + ttl,
    iat,
    iss: EXPECTED_ISSUER,
    sid,
    sub: userId,
  };

  const payloadB64 = base64UrlEncode(JSON.stringify(canonicalPayload));
  const signingInput = `v1.${payloadB64}`;
  const sigBytes = createHmac('sha256', validatedSecret)
    .update(signingInput, 'ascii')
    .digest();
  const sigB64 = base64UrlEncode(sigBytes);

  return `v1.${payloadB64}.${sigB64}`;
}
