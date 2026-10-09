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
          error.response.data?.detail || 'Lỗi từ AI Recommendation Service',
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
