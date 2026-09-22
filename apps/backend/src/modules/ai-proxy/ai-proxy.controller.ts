import { Controller, Post, Body, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { AiProxyService } from './ai-proxy.service';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';

@ApiTags('AI Integration')
@Controller('ai')
export class AiProxyController {
  constructor(private readonly aiProxyService: AiProxyService) {}

  @Post('chat')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Chat with AI assistant' })
  // Rate limiting could be applied here with @Throttle
  chat(@Body() payload: any) {
    return this.aiProxyService.chat(payload);
  }

  @Post('plan')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Generate a travel plan' })
  // Rate limiting could be applied here
  plan(@Body() payload: any) {
    return this.aiProxyService.plan(payload);
  }

  @Post('review-summary')
  @ApiOperation({ summary: 'Summarize reviews for a place' })
  reviewSummary(@Body() payload: any) {
    return this.aiProxyService.reviewSummary(payload);
  }
}
