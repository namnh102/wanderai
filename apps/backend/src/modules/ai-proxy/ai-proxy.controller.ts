import {
  Controller,
  Post,
  Delete,
  Body,
  Param,
  UseGuards,
  UnauthorizedException,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { AiChatProxyService } from './internal-auth';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { ChatDto } from './dto/chat.dto';

@ApiTags('AI')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('ai')
export class AiProxyController {
  constructor(private readonly aiProxyService: AiChatProxyService) {}

  @Post('chat')
  @ApiOperation({ summary: 'Chat với AI Wandy' })
  async chat(@Body() body: ChatDto, @CurrentUser() user: any) {
    if (!user?.id) {
      throw new UnauthorizedException('Yêu cầu đăng nhập để sử dụng AI Chat');
    }
    return this.aiProxyService.chat(body.message, body.session_id, user.id);
  }

  @Delete('chat/:sessionId')
  @ApiOperation({ summary: 'Xóa lịch sử phiên chat AI của người dùng hiện tại' })
  async clearChatSession(
    @Param('sessionId') sessionId: string,
    @CurrentUser() user: any,
  ) {
    if (!user?.id) {
      throw new UnauthorizedException('Yêu cầu đăng nhập để xóa phiên chat');
    }
    return this.aiProxyService.clearChatSession(sessionId, user.id);
  }

  @Post('plan')
  @ApiOperation({ summary: 'AI tạo lịch trình du lịch' })
  async plan(@Body() body: { destination: string; days: number; budget?: number }) {
    return this.aiProxyService.planTrip(body.destination, body.days, body.budget);
  }
}
