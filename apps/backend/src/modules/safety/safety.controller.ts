import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  ParseUUIDPipe,
  Post,
  UseGuards,
} from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import {
  CreateEmergencyEventDto,
  CreateSafetyCheckinDto,
  CreateSafetyContactDto,
} from './dto/safety.dto';
import { SafetyService } from './safety.service';

@ApiTags('Safety (WP-SAFE-01)')
@UseGuards(JwtAuthGuard)
@ApiBearerAuth()
@Controller('safety')
export class SafetyController {
  constructor(private readonly safetyService: SafetyService) {}

  @Get('contacts')
  @ApiOperation({ summary: 'Danh sách người liên hệ tin cậy (tối đa 3)' })
  listContacts(@CurrentUser() user: { id: string }) {
    return this.safetyService.listContacts(user.id);
  }

  @Post('contacts')
  @ApiOperation({ summary: 'Thêm người liên hệ tin cậy (giới hạn tối đa 3)' })
  createContact(
    @CurrentUser() user: { id: string },
    @Body() dto: CreateSafetyContactDto,
  ) {
    return this.safetyService.createContact(user.id, dto);
  }

  @Delete('contacts/:id')
  @ApiOperation({ summary: 'Xóa người liên hệ tin cậy thuộc tài khoản hiện tại' })
  deleteContact(
    @CurrentUser() user: { id: string },
    @Param('id', new ParseUUIDPipe()) id: string,
  ) {
    return this.safetyService.deleteContact(user.id, id);
  }

  @Get('checkins')
  @ApiOperation({ summary: 'Lịch sử check-in an toàn cá nhân' })
  listCheckins(@CurrentUser() user: { id: string }) {
    return this.safetyService.listCheckins(user.id);
  }

  @Post('checkins')
  @ApiOperation({ summary: 'Ghi nhận một check-in an toàn lên máy chủ' })
  createCheckin(
    @CurrentUser() user: { id: string },
    @Body() dto: CreateSafetyCheckinDto,
  ) {
    return this.safetyService.createCheckin(user.id, dto);
  }

  @Get('emergency-events')
  @ApiOperation({ summary: 'Danh sách sự kiện khẩn cấp / kiểm thử của tài khoản' })
  listEmergencyEvents(@CurrentUser() user: { id: string }) {
    return this.safetyService.listEmergencyEvents(user.id);
  }

  @Post('emergency-events')
  @ApiOperation({
    summary: 'Ghi nhận sự kiện SOS / kiểm thử an toàn (hỗ trợ metadata isSandbox)',
  })
  createEmergencyEvent(
    @CurrentUser() user: { id: string },
    @Body() dto: CreateEmergencyEventDto,
  ) {
    return this.safetyService.createEmergencyEvent(user.id, dto);
  }
}
