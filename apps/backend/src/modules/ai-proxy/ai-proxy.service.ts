import { Injectable, HttpException, HttpStatus } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios from 'axios';

@Injectable()
export class AiProxyService {
  private aiServiceUrl: string;

  constructor(private configService: ConfigService) {
    this.aiServiceUrl = this.configService.get('AI_SERVICE_URL', 'http://localhost:8000');
  }

  // Forward chat message đến FastAPI AI service
  async chat(message: string, sessionId?: string, userId?: string) {
    try {
      const response = await axios.post(`${this.aiServiceUrl}/chat`, {
        message,
        session_id: sessionId,
        user_id: userId,
      }, { timeout: 30000 });

      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        throw new HttpException(error.response.data, error.response.status);
      }
      throw new HttpException(
        'AI Service không phản hồi. Vui lòng thử lại.',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // Forward trip plan request đến FastAPI
  async planTrip(destination: string, days: number, budget?: number, preferences?: string[]) {
    try {
      const response = await axios.post(`${this.aiServiceUrl}/planner`, {
        destination,
        days,
        budget: budget ?? 3000000,
        style: 'adventure',
        interests: preferences ?? [],
      }, { timeout: 60000 });

      return response.data;
    } catch (error) {
      throw new HttpException(
        'AI Planner không phản hồi. Vui lòng thử lại.',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }
}
