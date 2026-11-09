import { ConfigService } from '@nestjs/config';

export const MIN_JWT_SECRET_LENGTH = 32;
export const MIN_JWT_SECRET_UNIQUE_CHARS = 8;

const DISALLOWED_WEAK_SECRETS = new Set([
  'super-secret',
  'wanderai-dev-jwt-secret-2026',
  'wanderai-dev-refresh-secret-2026',
  'wanderai-jwt-secret-change-in-production',
  'wanderai-refresh-secret-change-in-production',
  '<replace_with_strong_jwt_secret_min_32_chars>',
  '<replace_with_distinct_jwt_refresh_secret_min_32_chars>',
  'changeme',
  'secret',
  'password',
  'jwt_secret',
  'jwt_refresh_secret',
]);

export type JwtTokenType = 'access' | 'refresh';

export interface JwtTokenPayload {
  sub: string;
  email: string;
  type?: JwtTokenType;
  iat?: number;
  exp?: number;
}

export interface ValidatedJwtConfig {
  accessSecret: string;
  refreshSecret: string;
}

function assertValidSecretValue(
  rawSecret: unknown,
  keyName: 'JWT_SECRET' | 'JWT_REFRESH_SECRET',
): string {
  if (typeof rawSecret !== 'string' || rawSecret.trim().length === 0) {
    throw new Error(
      `Invalid JWT configuration: ${keyName} is required and must be a non-empty string.`,
    );
  }

  const secret = rawSecret.trim();
  const normalized = secret.toLowerCase();

  if (
    DISALLOWED_WEAK_SECRETS.has(normalized) ||
    normalized.startsWith('<replace_with_') ||
    normalized.includes('change-in-production') ||
    normalized.includes('wanderai-dev-')
  ) {
    throw new Error(
      `Invalid JWT configuration: ${keyName} uses a disallowed fallback or placeholder value.`,
    );
  }

  if (secret.length < MIN_JWT_SECRET_LENGTH) {
    throw new Error(
      `Invalid JWT configuration: ${keyName} must be at least ${MIN_JWT_SECRET_LENGTH} characters long.`,
    );
  }

  const uniqueChars = new Set(secret).size;
  if (uniqueChars < MIN_JWT_SECRET_UNIQUE_CHARS) {
    throw new Error(
      `Invalid JWT configuration: ${keyName} has insufficient character diversity.`,
    );
  }

  return secret;
}

export function validateJwtSecrets(
  rawAccessSecret: unknown,
  rawRefreshSecret: unknown,
): ValidatedJwtConfig {
  const accessSecret = assertValidSecretValue(rawAccessSecret, 'JWT_SECRET');
  const refreshSecret = assertValidSecretValue(rawRefreshSecret, 'JWT_REFRESH_SECRET');

  if (accessSecret === refreshSecret) {
    throw new Error(
      'Invalid JWT configuration: JWT_SECRET and JWT_REFRESH_SECRET must be distinct.',
    );
  }

  return {
    accessSecret,
    refreshSecret,
  };
}

export function getValidatedJwtConfig(configService: ConfigService): ValidatedJwtConfig {
  return validateJwtSecrets(
    configService.get<string>('JWT_SECRET'),
    configService.get<string>('JWT_REFRESH_SECRET'),
  );
}

export function validateEnvironmentJwtConfig(
  config: Record<string, unknown>,
): Record<string, unknown> {
  validateJwtSecrets(config.JWT_SECRET, config.JWT_REFRESH_SECRET);
  return config;
}
