import { randomBytes } from 'node:crypto';

export function ensureTestHarnessEnv(): void {
  if (!process.env.NODE_ENV) {
    process.env.NODE_ENV = 'test';
  }
  if (!process.env.JWT_SECRET || process.env.JWT_SECRET.trim().length < 32) {
    process.env.JWT_SECRET = `e2e-harness-access-secret-${randomBytes(24).toString('hex')}`;
  }
  if (
    !process.env.JWT_REFRESH_SECRET ||
    process.env.JWT_REFRESH_SECRET.trim().length < 32 ||
    process.env.JWT_REFRESH_SECRET === process.env.JWT_SECRET
  ) {
    process.env.JWT_REFRESH_SECRET = `e2e-harness-refresh-secret-${randomBytes(24).toString('hex')}`;
  }
  if (!process.env.YOUTUBE_EVENTS_INTERNAL_SECRET) {
    process.env.YOUTUBE_EVENTS_INTERNAL_SECRET =
      process.env.E2E_YOUTUBE_INTERNAL_SECRET || 'e2e-youtube-internal-secret';
  }
  if (!process.env.YOUTUBE_WEBSUB_SECRET) {
    process.env.YOUTUBE_WEBSUB_SECRET =
      process.env.E2E_WEBSUB_SECRET || 'e2e-websub-hmac-secret';
  }
  if (!process.env.YOUTUBE_REALTIME_SLA_MAX_LATENCY_MS) {
    process.env.YOUTUBE_REALTIME_SLA_MAX_LATENCY_MS = '300000';
  }
}

ensureTestHarnessEnv();
