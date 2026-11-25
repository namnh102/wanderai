import './harness-env';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import * as http from 'node:http';
import { AddressInfo } from 'node:net';
import { AppModule } from '../../src/app.module';
import { HttpExceptionFilter } from '../../src/common/filters/http-exception.filter';
import { TransformInterceptor } from '../../src/common/interceptors/transform.interceptor';
import {
  buildNestCorsOptions,
  resolveNetworkConfig,
} from '../../src/config/network.config';
import {
  FACEBOOK_OAUTH_VERIFIER,
  GOOGLE_OAUTH_VERIFIER,
} from '../../src/modules/auth/verifiers/oauth-verifier.interface';
import { InMemoryTestMailTransport } from '../../src/modules/mail/transports/in-memory-test-mail.transport';
import { MAIL_TRANSPORT } from '../../src/modules/mail/transports/mail-transport.interface';
import { PrismaService } from '../../src/prisma/prisma.service';
import { ensureTestHarnessEnv } from './harness-env';
import { InMemoryPrismaService } from './in-memory-prisma.service';
import {
  TestFacebookOAuthVerifier,
  TestGoogleOAuthVerifier,
} from './test-oauth-verifiers';

function writeJson(
  res: http.ServerResponse,
  statusCode: number,
  payload: unknown,
): void {
  const body = JSON.stringify(payload);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

async function readJsonBody(
  req: http.IncomingMessage,
): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  const raw = Buffer.concat(chunks).toString('utf8').trim();
  if (!raw) return {};
  return JSON.parse(raw) as Record<string, unknown>;
}

function extractResetToken(text: string): string | null {
  const match = text.match(/token=([a-zA-Z0-9_-]+)/);
  return match ? match[1] : null;
}

function createHookServer(
  prisma: InMemoryPrismaService,
  mailTransport: InMemoryTestMailTransport,
): http.Server {
  return http.createServer(async (req, res) => {
    const reqUrl = new URL(req.url || '/', 'http://127.0.0.1');
    const method = (req.method || 'GET').toUpperCase();

    if (method === 'GET' && reqUrl.pathname === '/mail-outbox') {
      const emailParam = reqUrl.searchParams.get('email')?.toLowerCase().trim();
      const items = mailTransport
        .getMessages()
        .filter((m) =>
          emailParam ? m.to.toLowerCase().trim() === emailParam : true,
        )
        .map((m) => ({
          to: m.to,
          subject: m.subject,
          rawToken: extractResetToken(m.text),
          sentAt: m.sentAt.toISOString(),
        }));
      const latestToken =
        items.length > 0 ? items[items.length - 1].rawToken : null;
      writeJson(res, 200, {
        success: true,
        data: { items, token: latestToken },
        timestamp: new Date().toISOString(),
      });
      return;
    }

    if (method === 'POST' && reqUrl.pathname === '/seed-expired-reset-token') {
      try {
        const body = await readJsonBody(req);
        const email = typeof body.email === 'string' ? body.email.trim() : '';
        if (!email) {
          writeJson(res, 400, {
            success: false,
            statusCode: 400,
            message: 'email is required',
          });
          return;
        }
        const token = prisma.seedExpiredResetToken(email);
        if (!token) {
          writeJson(res, 404, {
            success: false,
            statusCode: 404,
            message: `User not found for email ${email}`,
          });
          return;
        }
        writeJson(res, 200, {
          success: true,
          data: { token },
          timestamp: new Date().toISOString(),
        });
      } catch (err) {
        writeJson(res, 400, {
          success: false,
          statusCode: 400,
          message: err instanceof Error ? err.message : 'Invalid JSON body',
        });
      }
      return;
    }

    if (method === 'GET' && reqUrl.pathname === '/db-stats') {
      writeJson(res, 200, {
        success: true,
        data: prisma.getDbStats(),
        timestamp: new Date().toISOString(),
      });
      return;
    }

    if (method === 'POST' && reqUrl.pathname === '/reset') {
      prisma.seed();
      mailTransport.clear();
      writeJson(res, 200, {
        success: true,
        data: { reset: true },
        timestamp: new Date().toISOString(),
      });
      return;
    }

    writeJson(res, 404, {
      success: false,
      statusCode: 404,
      message: `Unknown hook route ${method} ${reqUrl.pathname}`,
    });
  });
}

async function main(): Promise<void> {
  ensureTestHarnessEnv();

  const apiPort = Number(process.env.E2E_API_PORT ?? process.env.PORT ?? 3000);
  const hookPort = Number(process.env.E2E_HOOK_PORT ?? 3001);

  const inMemoryPrisma = new InMemoryPrismaService();
  inMemoryPrisma.seed();
  const mailTransport = new InMemoryTestMailTransport();
  const googleVerifier = new TestGoogleOAuthVerifier();
  const facebookVerifier = new TestFacebookOAuthVerifier();

  const moduleRef = await Test.createTestingModule({
    imports: [AppModule],
  })
    .overrideProvider(PrismaService)
    .useValue(inMemoryPrisma)
    .overrideProvider(MAIL_TRANSPORT)
    .useValue(mailTransport)
    .overrideProvider(InMemoryTestMailTransport)
    .useValue(mailTransport)
    .overrideProvider(GOOGLE_OAUTH_VERIFIER)
    .useValue(googleVerifier)
    .overrideProvider(FACEBOOK_OAUTH_VERIFIER)
    .useValue(facebookVerifier)
    .compile();

  const app: INestApplication = moduleRef.createNestApplication();
  const networkConfig = resolveNetworkConfig(process.env);
  app.enableCors(buildNestCorsOptions(networkConfig.corsOrigins));
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
    }),
  );
  app.useGlobalFilters(new HttpExceptionFilter());
  app.useGlobalInterceptors(new TransformInterceptor());

  await app.listen(apiPort, '127.0.0.1');
  const apiAddr = app.getHttpServer().address() as AddressInfo;

  const hookServer = createHookServer(inMemoryPrisma, mailTransport);
  await new Promise<void>((resolve, reject) => {
    hookServer.once('error', reject);
    hookServer.listen(hookPort, '127.0.0.1', () => {
      hookServer.removeListener('error', reject);
      resolve();
    });
  });
  const hookAddr = hookServer.address() as AddressInfo;

  const readiness = {
    baseUrl: `http://127.0.0.1:${apiAddr.port}`,
    hookBaseUrl: `http://127.0.0.1:${hookAddr.port}`,
    mailOutboxUrl: `http://127.0.0.1:${hookAddr.port}/mail-outbox`,
    expiredResetSeedUrl: `http://127.0.0.1:${hookAddr.port}/seed-expired-reset-token`,
    dbStatsUrl: `http://127.0.0.1:${hookAddr.port}/db-stats`,
  };
  process.stdout.write(`READY ${JSON.stringify(readiness)}\n`);

  let shuttingDown = false;
  const shutdown = async (): Promise<void> => {
    if (shuttingDown) return;
    shuttingDown = true;
    await new Promise<void>((resolve) => {
      hookServer.close(() => resolve());
    });
    await app.close();
    process.exit(0);
  };

  process.on('SIGINT', () => {
    void shutdown();
  });
  process.on('SIGTERM', () => {
    void shutdown();
  });
}

void main().catch((err) => {
  process.stderr.write(
    `[e2e-live-server] Fatal startup error: ${err instanceof Error ? err.stack || err.message : String(err)}\n`,
  );
  process.exit(1);
});
