import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';
import { TransformInterceptor } from '../src/common/interceptors/transform.interceptor';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';
import { AiProxyService } from '../src/modules/ai-proxy/ai-proxy.service';
import { JwtService } from '@nestjs/jwt';
import { PrismaService } from '../src/prisma/prisma.service';

describe('AI Chat Proxy (e2e)', () => {
  let app: INestApplication;
  let jwtService: JwtService;
  let prisma: PrismaService;
  let aiProxyService: AiProxyService;

  let testUserToken: string;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true, forbidNonWhitelisted: true }));
    app.useGlobalFilters(new HttpExceptionFilter());
    app.useGlobalInterceptors(new TransformInterceptor());
    await app.init();

    jwtService = moduleFixture.get<JwtService>(JwtService);
    prisma = moduleFixture.get<PrismaService>(PrismaService);
    aiProxyService = moduleFixture.get<AiProxyService>(AiProxyService);

    // Get an existing user for auth token
    const user = await prisma.user.findFirst();
    if (user) {
      testUserToken = jwtService.sign({ sub: user.id, email: user.email });
    }
  });

  afterAll(async () => {
    await app.close();
  });

  describe('POST /ai/chat security & contract', () => {
    it('1. should reject unauthenticated requests with 401', async () => {
      await request(app.getHttpServer())
        .post('/ai/chat')
        .send({ message: 'Xin chào' })
        .expect(401);
    });

    it('2. should reject requests with empty message with 400', async () => {
      await request(app.getHttpServer())
        .post('/ai/chat')
        .set('Authorization', `Bearer ${testUserToken}`)
        .send({ message: '' })
        .expect(400);
    });

    it('3. should preserve and return sources array in response data', async () => {
      const mockSources = [
        'https://www.openstreetmap.org/way/37933256',
        'https://en.wikivoyage.org/wiki/Hanoi',
      ];

      // Spy on aiProxyService.chat
      jest.spyOn(aiProxyService, 'chat').mockResolvedValueOnce({
        reply: 'Hà Nội có Bảo tàng Lịch sử Quốc gia và nhiều di tích cổ kính.',
        session_id: 'test-session-sources-1',
        tools_used: ['search_places'],
        tool_calls: [],
        sources: mockSources,
      });

      const response = await request(app.getHttpServer())
        .post('/ai/chat')
        .set('Authorization', `Bearer ${testUserToken}`)
        .send({
          message: 'Các địa điểm văn hóa ở Hà Nội?',
          session_id: 'test-session-sources-1',
        })
        .expect(201);

      expect(response.body).toHaveProperty('success', true);
      expect(response.body).toHaveProperty('data');
      expect(response.body.data.reply).toBe('Hà Nội có Bảo tàng Lịch sử Quốc gia và nhiều di tích cổ kính.');
      expect(response.body.data.session_id).toBe('test-session-sources-1');
      expect(response.body.data.sources).toEqual(mockSources);
      expect(Array.isArray(response.body.data.sources)).toBe(true);
      expect(response.body.data.sources.length).toBe(2);
    });

    it('4. should preserve empty sources array when no RAG documents were retrieved', async () => {
      jest.spyOn(aiProxyService, 'chat').mockResolvedValueOnce({
        reply: 'Xin chào! Mình có thể giúp gì cho bạn?',
        session_id: 'test-session-empty-sources',
        tools_used: [],
        tool_calls: [],
        sources: [],
      });

      const response = await request(app.getHttpServer())
        .post('/ai/chat')
        .set('Authorization', `Bearer ${testUserToken}`)
        .send({
          message: 'Xin chào',
        })
        .expect(201);

      expect(response.body.success).toBe(true);
      expect(response.body.data.sources).toEqual([]);
      expect(Array.isArray(response.body.data.sources)).toBe(true);
    });
  });
});
