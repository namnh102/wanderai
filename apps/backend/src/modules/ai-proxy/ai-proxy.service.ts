import {
  Injectable,
  HttpException,
  HttpStatus,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios from 'axios';
import {
  createInternalServiceAssertion,
  INTERNAL_ASSERTION_HEADER,
} from './internal-auth';

/**
 * Flatten a FastAPI `detail` (string | Pydantic error list | object) into a single
 * human-readable string so clients never receive raw objects or internals.
 */
export function formatUpstreamDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d: any) => {
        if (typeof d === 'string') return d;
        const field = Array.isArray(d?.loc)
          ? d.loc.filter((p: any) => p !== 'body').join('.')
          : '';
        const msg =
          typeof d?.msg === 'string' ? d.msg.replace(/^Value error, /, '') : '';
        return msg ? (field ? `${field}: ${msg}` : msg) : '';
      })
      .filter(Boolean);
    if (parts.length) return parts.join('; ');
  }
  return fallback;
}

@Injectable()
export class AiProxyService {
  private aiServiceUrl: string;

  constructor(private configService: ConfigService) {
    this.aiServiceUrl = this.configService.get(
      'AI_SERVICE_URL',
      'http://localhost:8000',
    );
  }

  private buildSignedInternalHeaders(
    userId: string,
    action: string,
    sessionId?: string,
  ): Record<string, string> {
    const trimmedUserId = typeof userId === 'string' ? userId.trim() : '';
    if (!trimmedUserId) {
      throw new HttpException(
        'Yêu cầu đăng nhập để sử dụng AI Chat.',
        HttpStatus.UNAUTHORIZED,
      );
    }

    let assertion: string;
    try {
      assertion = createInternalServiceAssertion({
        secret: this.configService.get<string>('AI_INTERNAL_AUTH_SECRET'),
        jwtSecret: this.configService.get<string>('JWT_SECRET'),
        jwtRefreshSecret: this.configService.get<string>('JWT_REFRESH_SECRET'),
        userId: trimmedUserId,
        action,
        sessionId,
      });
    } catch {
      throw new HttpException(
        'Dịch vụ AI chưa được cấu hình khóa xác thực nội bộ.',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }

    return {
      [INTERNAL_ASSERTION_HEADER]: assertion,
    };
  }

  // Forward chat message đến FastAPI AI service kèm signed internal assertion
  async chat(message: string, sessionId?: string, userId?: string) {
    const headers = this.buildSignedInternalHeaders(
      userId ?? '',
      'POST:/chat',
      sessionId,
    );

    try {
      const response = await axios.post(
        `${this.aiServiceUrl}/chat`,
        {
          message,
          session_id: sessionId,
          user_id: userId?.trim(),
        },
        {
          timeout: 30000,
          headers,
        },
      );

      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        const rawDetail =
          error.response.data?.detail ?? error.response.data?.message;
        throw new HttpException(
          formatUpstreamDetail(
            rawDetail,
            'Dịch vụ AI gặp sự cố khi xử lý tin nhắn.',
          ),
          error.response.status,
        );
      }
      throw new HttpException(
        'AI Service không phản hồi. Vui lòng thử lại.',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // Xóa lịch sử phiên chat của chính user đã xác thực
  async clearChatSession(sessionId: string, userId?: string) {
    const trimmedSessionId =
      typeof sessionId === 'string' ? sessionId.trim() : '';
    if (!trimmedSessionId) {
      throw new HttpException(
        'session_id không hợp lệ.',
        HttpStatus.BAD_REQUEST,
      );
    }

    const encodedSessionId = encodeURIComponent(trimmedSessionId);
    const headers = this.buildSignedInternalHeaders(
      userId ?? '',
      `DELETE:/chat/${encodedSessionId}`,
      trimmedSessionId,
    );

    try {
      const response = await axios.delete(
        `${this.aiServiceUrl}/chat/${encodedSessionId}`,
        {
          timeout: 10000,
          headers,
        },
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        const rawDetail =
          error.response.data?.detail ?? error.response.data?.message;
        throw new HttpException(
          formatUpstreamDetail(
            rawDetail,
            'Không thể xóa lịch sử phiên trò chuyện.',
          ),
          error.response.status,
        );
      }
      throw new HttpException(
        'AI Service không phản hồi. Vui lòng thử lại.',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // Forward trip plan request đến FastAPI
  async planTrip(
    destination: string,
    days: number,
    budget?: number,
    preferences?: string[],
  ) {
    try {
      const response = await axios.post(
        `${this.aiServiceUrl}/planner`,
        {
          destination,
          days,
          budget: budget ?? 3000000,
          style: 'adventure',
          interests: preferences ?? [],
        },
        { timeout: 60000 },
      );

      return response.data;
    } catch (error) {
      throw new HttpException(
        'AI Planner không phản hồi. Vui lòng thử lại.',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // Forward authoritative TripContext đến FastAPI AI Planner
  async planWithTripContext(context: {
    tripId?: string;
    destination: string;
    days: number;
    startDate?: string;
    endDate?: string;
    budget?: number;
    currency?: string;
    travelStyle?: string;
    interests?: string[];
    notes?: string;
  }) {
    try {
      const response = await axios.post(
        `${this.aiServiceUrl}/planner`,
        {
          trip_id: context.tripId,
          destination: context.destination,
          days: context.days,
          start_date: context.startDate,
          end_date: context.endDate,
          budget: context.budget,
          currency: context.currency || 'VND',
          travel_style: context.travelStyle,
          interests: context.interests || [],
          notes: context.notes,
        },
        { timeout: 60000 },
      );

      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        throw new HttpException(
          error.response.data?.detail || 'AI Service trả về lỗi',
          error.response.status,
        );
      }
      throw new HttpException(
        'AI Planner không phản hồi. Vui lòng thử lại.',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // Forward place recommendation request đến FastAPI AI service (REC-A)
  async getPlaceRecommendations(
    preferences?: any,
    destination?: string,
    topK: number = 10,
    model: string = 'rec-a1',
  ) {
    try {
      const response = await axios.post(
        `${this.aiServiceUrl}/recommendations/places`,
        {
          preferences: preferences || null,
          destination: destination || null,
          top_k: topK,
          model: model || 'rec-a1',
        },
        { timeout: 15000 },
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        throw new HttpException(
          formatUpstreamDetail(
            error.response.data?.detail,
            'Lỗi từ AI Recommendation Service',
          ),
          error.response.status,
        );
      }
      throw new HttpException(
        'AI Recommendation Service không phản hồi. Vui lòng thử lại sau.',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }
}
