import { HttpException, HttpStatus, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios from 'axios';
import { AiProxyController } from './ai-proxy.controller';
import {
  AiChatProxyService,
  createInternalServiceAssertion,
  INTERNAL_ASSERTION_HEADER,
  validateInternalAuthSecret,
} from './internal-auth';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('AI Proxy Security & Fail-Closed Contract (PROD-AI-RAG-04)', () => {
  const VALID_INTERNAL_SECRET = 'internal-service-hmac-secret-2026-abcdef123456';
  const VALID_JWT_SECRET = 'jwt-access-secret-distinct-2026-abcdef123456';
  const VALID_REFRESH_SECRET = 'jwt-refresh-secret-distinct-2026-abcdef123456';

  let configMap: Record<string, string | undefined>;
  let configService: ConfigService;
  let service: AiChatProxyService;
  let controller: AiProxyController;

  beforeEach(() => {
    jest.clearAllMocks();
    configMap = {
      AI_SERVICE_URL: 'http://localhost:8000',
      AI_INTERNAL_AUTH_SECRET: VALID_INTERNAL_SECRET,
      JWT_SECRET: VALID_JWT_SECRET,
      JWT_REFRESH_SECRET: VALID_REFRESH_SECRET,
    };
    configService = {
      get: jest.fn((key: string, defaultVal?: string) => configMap[key] ?? defaultVal),
    } as unknown as ConfigService;

    service = new AiChatProxyService(configService);
    controller = new AiProxyController(service);
  });

  describe('validateInternalAuthSecret & createInternalServiceAssertion', () => {
    it('rejects missing, short, weak, or placeholder AI_INTERNAL_AUTH_SECRET', () => {
      expect(() => validateInternalAuthSecret('')).toThrow();
      expect(() => validateInternalAuthSecret('short-secret')).toThrow();
      expect(() => validateInternalAuthSecret('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')).toThrow();
      expect(() =>
        validateInternalAuthSecret('<REPLACE_WITH_DISTINCT_INTERNAL_SERVICE_SECRET_MIN_32_CHARS>'),
      ).toThrow();
    });

    it('rejects reusing JWT_SECRET or JWT_REFRESH_SECRET as AI_INTERNAL_AUTH_SECRET', () => {
      expect(() =>
        validateInternalAuthSecret(VALID_JWT_SECRET, VALID_JWT_SECRET, VALID_REFRESH_SECRET),
      ).toThrow(/distinct/);
      expect(() =>
        validateInternalAuthSecret(VALID_REFRESH_SECRET, VALID_JWT_SECRET, VALID_REFRESH_SECRET),
      ).toThrow(/distinct/);
    });

    it('mints a v1 HMAC-SHA256 assertion bound to sub, act, sid, iat, and exp', () => {
      const token = createInternalServiceAssertion({
        secret: VALID_INTERNAL_SECRET,
        jwtSecret: VALID_JWT_SECRET,
        jwtRefreshSecret: VALID_REFRESH_SECRET,
        userId: 'user-123',
        action: 'POST:/chat',
        sessionId: 'sess-abc',
        nowSeconds: 1700000000,
        ttlSeconds: 60,
      });

      const parts = token.split('.');
      expect(parts).toHaveLength(3);
      expect(parts[0]).toBe('v1');

      const payloadJson = Buffer.from(parts[1], 'base64url').toString('utf8');
      const payload = JSON.parse(payloadJson);
      expect(payload).toEqual({
        act: 'POST:/chat',
        aud: 'wanderai-ai-service',
        exp: 1700000060,
        iat: 1700000000,
        iss: 'wanderai-backend',
        sid: 'sess-abc',
        sub: 'user-123',
      });
    });
  });

  describe('AiProxyController & AiProxyService.chat', () => {
    it('rejects unauthenticated requests lacking user.id with 401', async () => {
      await expect(
        controller.chat({ message: 'Xin chào', session_id: 's1' }, null),
      ).rejects.toThrow(UnauthorizedException);

      await expect(service.chat('Xin chào', 's1', '')).rejects.toMatchObject({
        status: HttpStatus.UNAUTHORIZED,
      });
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });

    it('fails closed with 503 if AI_INTERNAL_AUTH_SECRET is missing or reuses JWT_SECRET', async () => {
      configMap.AI_INTERNAL_AUTH_SECRET = VALID_JWT_SECRET;
      await expect(service.chat('Xin chào', 's1', 'user-1')).rejects.toMatchObject({
        status: HttpStatus.SERVICE_UNAVAILABLE,
      });
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });

    it('attaches X-WanderAI-Internal-Assertion header and forwards authenticated user.id', async () => {
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          reply: 'Chào bạn!',
          session_id: 's1',
          sources: [],
          retrieval_status: 'empty',
        },
      } as any);

      const result = await controller.chat(
        { message: 'Xin chào', session_id: 's1' },
        { id: 'user-alice' },
      );

      expect(result.reply).toBe('Chào bạn!');
      expect(mockedAxios.post).toHaveBeenCalledTimes(1);
      const [url, body, reqConfig] = mockedAxios.post.mock.calls[0];
      expect(url).toBe('http://localhost:8000/chat');
      expect(body).toEqual({
        message: 'Xin chào',
        session_id: 's1',
        user_id: 'user-alice',
      });
      const assertion = reqConfig?.headers?.[INTERNAL_ASSERTION_HEADER];
      expect(typeof assertion).toBe('string');
      const decoded = JSON.parse(
        Buffer.from((assertion as string).split('.')[1], 'base64url').toString('utf8'),
      );
      expect(decoded.sub).toBe('user-alice');
      expect(decoded.act).toBe('POST:/chat');
      expect(decoded.sid).toBe('s1');
    });

    it.each([403, 429, 502, 503])(
      'propagates upstream HTTP %i with formatted string detail via formatUpstreamDetail',
      async (statusCode) => {
        const axiosErr = {
          isAxiosError: true,
          response: {
            status: statusCode,
            data: { detail: `Upstream error ${statusCode}` },
          },
        };
        mockedAxios.isAxiosError.mockReturnValue(true);
        mockedAxios.post.mockRejectedValueOnce(axiosErr);

        try {
          await service.chat('Xin chào', 's1', 'user-alice');
          fail('Expected service.chat to throw HttpException');
        } catch (err) {
          expect(err).toBeInstanceOf(HttpException);
          const httpErr = err as HttpException;
          expect(httpErr.getStatus()).toBe(statusCode);
          expect(httpErr.getResponse()).toBe(`Upstream error ${statusCode}`);
        }
      },
    );
  });

  describe('AiProxyController & AiProxyService.clearChatSession (DELETE /ai/chat/:sessionId)', () => {
    it('sends signed DELETE assertion bound to sessionId and userId', async () => {
      mockedAxios.delete.mockResolvedValueOnce({
        data: { message: 'Chat history cleared' },
      } as any);

      const res = await controller.clearChatSession('sess-99', { id: 'user-alice' });
      expect(res).toEqual({ message: 'Chat history cleared' });

      expect(mockedAxios.delete).toHaveBeenCalledTimes(1);
      const [url, reqConfig] = mockedAxios.delete.mock.calls[0];
      expect(url).toBe('http://localhost:8000/chat/sess-99');
      const assertion = reqConfig?.headers?.[INTERNAL_ASSERTION_HEADER];
      const decoded = JSON.parse(
        Buffer.from((assertion as string).split('.')[1], 'base64url').toString('utf8'),
      );
      expect(decoded.sub).toBe('user-alice');
      expect(decoded.act).toBe('DELETE:/chat/sess-99');
      expect(decoded.sid).toBe('sess-99');
    });

    it('propagates 403 Forbidden when attempting to delete another user session', async () => {
      const axiosErr = {
        isAxiosError: true,
        response: {
          status: 403,
          data: { detail: 'Không có quyền xóa phiên trò chuyện này.' },
        },
      };
      mockedAxios.isAxiosError.mockReturnValue(true);
      mockedAxios.delete.mockRejectedValueOnce(axiosErr);

      await expect(
        controller.clearChatSession('sess-alice', { id: 'user-bob' }),
      ).rejects.toMatchObject({
        status: 403,
        response: 'Không có quyền xóa phiên trò chuyện này.',
      });
    });
  });
});
