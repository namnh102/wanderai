import { Controller, Post, Body, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { AiProxyService } from './ai-proxy.service';

@ApiTags('AI')
@Controller('ai')
export class AiProxyController {
  constructor(private readonly aiProxyService: AiProxyService) {}

  @Post('chat')
  @ApiOperation({ summary: 'Chat với AI Wandy' })
  async chat(@Body() body: { message: string; session_id?: string }) {
    return this.aiProxyService.chat(body.message, body.session_id);
  }

  @Post('plan')
  @ApiOperation({ summary: 'AI tạo lịch trình du lịch' })
  async plan(@Body() body: { destination: string; days: number; budget?: number }) {
    return this.aiProxyService.planTrip(body.destination, body.days, body.budget);
  }
}
