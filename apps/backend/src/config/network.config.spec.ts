import {
  Controller,
  Get,
  INestApplication,
  Module,
  Post,
  UnauthorizedException,
  Headers,
} from '@nestjs/common';
import { Test } from '@nestjs/testing';
import * as request from 'supertest';
import {
  DEFAULT_BACKEND_PORT,
  DEFAULT_DEV_CORS_ORIGINS,
  buildNestCorsOptions,
  parseAndValidateCorsOrigins,
  resolveHost,
  resolveNetworkConfig,
  resolvePort,
} from './network.config';

@Controller('probe')
class ProbeController {
  @Get('public')
  getPublic() {
    return { status: 'ok' };
  }

  @Post('protected')
  postProtected(@Headers('authorization') authHeader?: string) {
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      throw new UnauthorizedException('Missing Bearer token');
    }
    return { authenticated: true };
  }
}

@Module({
  controllers: [ProbeController],
})
class ProbeModule {}

describe('PROD-NET-01: NestJS HOST / PORT / CORS configuration', () => {
  describe('resolvePort', () => {
    it('defaults to 3000 when PORT is omitted or blank', () => {
      expect(resolvePort(undefined)).toBe(DEFAULT_BACKEND_PORT);
      expect(resolvePort('')).toBe(DEFAULT_BACKEND_PORT);
      expect(resolvePort('   ')).toBe(DEFAULT_BACKEND_PORT);
    });

    it('parses valid integer ports within 1..65535', () => {
      expect(resolvePort('3000')).toBe(3000);
      expect(resolvePort('8080')).toBe(8080);
      expect(resolvePort(4000)).toBe(4000);
    });

    it('rejects non-numeric or out-of-range ports', () => {
      for (const badPort of ['0', '-1', '65536', 'abc', '3000tcp', '3.14']) {
        expect(() => resolvePort(badPort)).toThrow(/Invalid PORT configuration/);
      }
    });
  });

  describe('resolveHost', () => {
    it('returns undefined when HOST is omitted or blank', () => {
      expect(resolveHost(undefined)).toBeUndefined();
      expect(resolveHost('')).toBeUndefined();
      expect(resolveHost('   ')).toBeUndefined();
    });

    it('accepts valid IP addresses and hostnames', () => {
      expect(resolveHost('0.0.0.0')).toBe('0.0.0.0');
      expect(resolveHost('127.0.0.1')).toBe('127.0.0.1');
      expect(resolveHost('  api.internal.local  ')).toBe('api.internal.local');
    });

    it('rejects HOST values containing protocol, slashes, spaces, or query strings', () => {
      for (const badHost of [
        'http://0.0.0.0',
        '0.0.0.0/24',
        'localhost:3000/api',
        'host with spaces',
        'localhost?foo=1',
      ]) {
        expect(() => resolveHost(badHost)).toThrow(/Invalid HOST configuration/);
      }
    });
  });

  describe('parseAndValidateCorsOrigins & resolveNetworkConfig', () => {
    it('returns development defaults when CORS_ORIGINS is omitted in development', () => {
      const origins = parseAndValidateCorsOrigins(undefined, 'development');
      expect(origins).toEqual([...DEFAULT_DEV_CORS_ORIGINS]);
    });

    it('trims, normalizes, and deduplicates comma-separated origins', () => {
      const origins = parseAndValidateCorsOrigins(
        ' http://localhost:4200 , https://app.gomate.example.com , http://localhost:4200 ',
        'development',
      );
      expect(origins).toEqual([
        'http://localhost:4200',
        'https://app.gomate.example.com',
      ]);
    });

    it('rejects wildcard "*", "null", trailing slashes, paths, queries, and credentials in origins', () => {
      for (const invalid of [
        '*',
        'https://*.gomate.example.com',
        'null',
        'https://app.gomate.example.com/',
        'https://app.gomate.example.com/subpath',
        'https://app.gomate.example.com?foo=bar',
        'https://user:pass@app.gomate.example.com',
        'ftp://app.gomate.example.com',
        'not-an-origin',
      ]) {
        expect(() =>
          parseAndValidateCorsOrigins(invalid, 'development'),
        ).toThrow(/Invalid CORS_ORIGINS configuration/);
      }
    });

    it('fails closed in production when CORS_ORIGINS is missing, uses HTTP, or points to loopback/10.0.2.2', () => {
      expect(() => parseAndValidateCorsOrigins('', 'production')).toThrow(
        /explicit CORS allowlist is required/,
      );
      expect(() =>
        parseAndValidateCorsOrigins(
          'http://app.gomate.example.com',
          'production',
        ),
      ).toThrow(/production origins must use https/);
      expect(() =>
        parseAndValidateCorsOrigins('https://localhost:4200', 'production'),
      ).toThrow(/loopback or emulator host/);
      expect(() =>
        parseAndValidateCorsOrigins('https://10.0.2.2:3000', 'production'),
      ).toThrow(/loopback or emulator host/);

      expect(
        parseAndValidateCorsOrigins(
          'https://app.gomate.example.com, https://admin.gomate.example.com',
          'production',
        ),
      ).toEqual([
        'https://app.gomate.example.com',
        'https://admin.gomate.example.com',
      ]);
    });

    it('resolves complete network configuration from env map', () => {
      const resolved = resolveNetworkConfig({
        NODE_ENV: 'production',
        PORT: '4000',
        HOST: '0.0.0.0',
        CORS_ORIGINS: 'https://app.gomate.example.com',
      });
      expect(resolved).toEqual({
        nodeEnv: 'production',
        port: 4000,
        host: '0.0.0.0',
        corsOrigins: ['https://app.gomate.example.com'],
      });
    });
  });

  describe('HTTP CORS runtime behavior (OPTIONS preflight, allowed, disallowed, native mobile)', () => {
    let app: INestApplication;

    beforeAll(async () => {
      const moduleRef = await Test.createTestingModule({
        imports: [ProbeModule],
      }).compile();

      app = moduleRef.createNestApplication();
      app.enableCors(
        buildNestCorsOptions([
          'https://app.gomate.example.com',
          'http://localhost:4200',
        ]),
      );
      await app.init();
    });

    afterAll(async () => {
      await app.close();
    });

    it('1. OPTIONS preflight from an allowed browser origin returns 204 and explicit CORS headers', async () => {
      const res = await request(app.getHttpServer())
        .options('/probe/protected')
        .set('Origin', 'https://app.gomate.example.com')
        .set('Access-Control-Request-Method', 'POST')
        .set('Access-Control-Request-Headers', 'Content-Type,Authorization');

      expect(res.status).toBe(204);
      expect(res.headers['access-control-allow-origin']).toBe(
        'https://app.gomate.example.com',
      );
      expect(res.headers['access-control-allow-credentials']).toBe('true');
      expect(res.headers['access-control-allow-methods']).toContain('POST');
    });

    it('2. Request from an allowed browser origin receives matching Access-Control-Allow-Origin', async () => {
      const res = await request(app.getHttpServer())
        .get('/probe/public')
        .set('Origin', 'http://localhost:4200');

      expect(res.status).toBe(200);
      expect(res.headers['access-control-allow-origin']).toBe(
        'http://localhost:4200',
      );
      expect(res.headers['access-control-allow-credentials']).toBe('true');
    });

    it('3. OPTIONS preflight and GET from a disallowed browser origin do NOT receive CORS allow headers', async () => {
      const preflightRes = await request(app.getHttpServer())
        .options('/probe/protected')
        .set('Origin', 'https://evil.example.com')
        .set('Access-Control-Request-Method', 'POST');

      expect(
        preflightRes.headers['access-control-allow-origin'],
      ).toBeUndefined();

      const getRes = await request(app.getHttpServer())
        .get('/probe/public')
        .set('Origin', 'https://evil.example.com');

      expect(getRes.headers['access-control-allow-origin']).toBeUndefined();
    });

    it('4. Non-browser native mobile requests (no Origin header) are permitted and still enforce Bearer auth', async () => {
      // Public route without Origin header succeeds
      const publicRes = await request(app.getHttpServer()).get('/probe/public');
      expect(publicRes.status).toBe(200);
      expect(publicRes.body).toEqual({ status: 'ok' });

      // Protected route without Bearer token fails 401 (even with allowed Origin or no Origin)
      const unauthMobileRes = await request(app.getHttpServer()).post(
        '/probe/protected',
      );
      expect(unauthMobileRes.status).toBe(401);

      const unauthBrowserRes = await request(app.getHttpServer())
        .post('/probe/protected')
        .set('Origin', 'https://app.gomate.example.com');
      expect(unauthBrowserRes.status).toBe(401);

      // Protected route with Bearer token succeeds
      const authMobileRes = await request(app.getHttpServer())
        .post('/probe/protected')
        .set('Authorization', 'Bearer valid-test-token');
      expect(authMobileRes.status).toBe(201);
      expect(authMobileRes.body).toEqual({ authenticated: true });
    });
  });
});
