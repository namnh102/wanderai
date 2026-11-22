import {
  Body,
  Controller,
  Get,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import {
  CreateMatchRequestDto,
  MatchCandidatesQueryDto,
  RespondMatchDto,
} from './dto/match.dto';
import { MatchesService } from './matches.service';

@ApiTags('Matches (W08 Buddy Matching)')
@UseGuards(JwtAuthGuard)
@ApiBearerAuth()
@Controller('matches')
export class MatchesController {
  constructor(private readonly matchesService: MatchesService) {}

  @Get('candidates')
  @ApiOperation({
    summary: 'Tìm ứng viên bạn đồng hành phù hợp (tùy chọn opt-in, ẩn PII email/SĐT)',
  })
  listCandidates(@CurrentUser() user: { id: string }, @Query() query: MatchCandidatesQueryDto) {
    return this.matchesService.listCandidates(
      user.id,
      query.destinationId,
      query.limit,
    );
  }

  @Get()
  @ApiOperation({ summary: 'Danh sách kết nối bạn đồng hành đã gửi và đã nhận' })
  listMyMatches(@CurrentUser() user: { id: string }) {
    return this.matchesService.listMyMatches(user.id);
  }

  @Post('request')
  @ApiOperation({ summary: 'Gửi lời mời kết bạn đồng hành' })
  sendRequest(@CurrentUser() user: { id: string }, @Body() dto: CreateMatchRequestDto) {
    return this.matchesService.sendMatchRequest(user.id, dto.receiverId);
  }

  @Patch(':id/respond')
  @ApiOperation({ summary: 'Chấp nhận hoặc từ chối lời mời bạn đồng hành' })
  respond(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: { id: string },
    @Body() dto: RespondMatchDto,
  ) {
    return this.matchesService.respondToMatch(id, user.id, dto.action);
  }
}
