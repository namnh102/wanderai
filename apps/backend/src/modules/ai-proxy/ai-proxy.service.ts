import { Injectable, InternalServerErrorException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios from 'axios';

@Injectable()
export class AiProxyService {
  private readonly aiServiceUrl: string;

  constructor(private configService: ConfigService) {
    this.aiServiceUrl = this.configService.get<string>('AI_SERVICE_URL') || 'http://localhost:8000';
  }

  async chat(payload: any) {
    try {
      const response = await axios.post(`${this.aiServiceUrl}/chat`, payload);
      return response.data;
    } catch (error) {
      throw new InternalServerErrorException('AI Service Error (Chat)');
    }
  }

  async plan(payload: any) {
    try {
      const response = await axios.post(`${this.aiServiceUrl}/plan`, payload);
      return response.data;
    } catch (error) {
      throw new InternalServerErrorException('AI Service Error (Plan)');
    }
  }

  async reviewSummary(payload: any) {
    try {
      const response = await axios.post(`${this.aiServiceUrl}/review-summary`, payload);
      return response.data;
    } catch (error) {
      throw new InternalServerErrorException('AI Service Error (Review Summary)');
    }
  }
}
