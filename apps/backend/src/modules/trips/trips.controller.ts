import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Body,
  Headers,
  Param,
  ParseUUIDPipe,
  UseGuards,
  HttpCode,
  HttpStatus,
  Optional,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { TripsService } from './trips.service';
import { TripInvitesService } from './trip-invites.service';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { CreateTripDto } from './dto/create-trip.dto';
import { UpdateTripDto } from './dto/update-trip.dto';
import { AddItineraryDto } from './dto/add-itinerary.dto';
import { BulkItineraryDto } from './dto/bulk-itinerary.dto';
import { ReorderItineraryDto } from './dto/reorder-itinerary.dto';
import { PlanTripDto } from './dto/plan-trip.dto';
import { Transform } from 'class-transformer';
import { IsEmail, IsNotEmpty, MaxLength } from 'class-validator';

class InviteMemberDto {
  @Transform(({ value }: { value: unknown }) =>
    typeof value === 'string' ? value.trim() : value,
  )
  @IsEmail({}, { message: 'Email không hợp lệ' })
  @IsNotEmpty()
  @MaxLength(255)
  email: string;
}

@ApiTags('Trips')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('trips')
export class TripsController {
  constructor(
    private readonly tripsService: TripsService,
    @Optional() private readonly tripInvitesService?: TripInvitesService,
  ) {}

  private get _invites(): TripInvitesService {
    if (!this.tripInvitesService) {
      throw new Error('TripInvitesService is not configured');
    }
    return this.tripInvitesService;
  }

  // GET /trips/invites/:inviteId — xem chi tiết lời mời tham gia chuyến đi
  @Get('invites/:inviteId')
  @ApiOperation({ summary: 'Chi tiết lời mời tham gia chuyến đi' })
  getInviteById(
    @Param('inviteId', new ParseUUIDPipe()) inviteId: string,
    @CurrentUser() user: { id: string },
  ) {
    return this._invites.getInviteById(inviteId, user.id);
  }

  // POST /trips/invites/:inviteId/accept — chấp nhận lời mời vào chuyến
  @Post('invites/:inviteId/accept')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Chấp nhận lời mời tham gia chuyến đi' })
  acceptInvite(
    @Param('inviteId', new ParseUUIDPipe()) inviteId: string,
    @CurrentUser() user: { id: string },
  ) {
    return this._invites.acceptInvite(inviteId, user.id);
  }

  // POST /trips/invites/:inviteId/decline — từ chối lời mời vào chuyến
  @Post('invites/:inviteId/decline')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Từ chối lời mời tham gia chuyến đi' })
  declineInvite(
    @Param('inviteId', new ParseUUIDPipe()) inviteId: string,
    @CurrentUser() user: { id: string },
  ) {
    return this._invites.declineInvite(inviteId, user.id);
  }

  // POST /trips/invites/:inviteId/revoke — thu hồi lời mời (chủ chuyến đi)
  @Post('invites/:inviteId/revoke')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Thu hồi lời mời tham gia chuyến đi' })
  revokeInviteDirect(
    @Param('inviteId', new ParseUUIDPipe()) inviteId: string,
    @CurrentUser() user: { id: string },
  ) {
    return this._invites.revokeInvite(inviteId, user.id);
  }

  // POST /trips
  @Post()
  @ApiOperation({ summary: 'Tạo chuyến đi mới' })
  create(@CurrentUser() user: any, @Body() dto: CreateTripDto) {
    return this.tripsService.create(user.id, dto);
  }

  // GET /trips
  @Get()
  @ApiOperation({ summary: 'Danh sách chuyến đi của tôi' })
  findAll(@CurrentUser() user: any) {
    return this.tripsService.findAll(user.id);
  }

  // GET /trips/:id
  @Get(':id')
  @ApiOperation({ summary: 'Chi tiết chuyến đi (+ lịch trình + thành viên)' })
  findById(@Param('id', new ParseUUIDPipe()) id: string, @CurrentUser() user: any) {
    return this.tripsService.findById(id, user.id);
  }

  // PUT /trips/:id
  @Put(':id')
  @ApiOperation({ summary: 'Cập nhật chuyến đi' })
  update(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: any,
    @Body() dto: UpdateTripDto,
  ) {
    return this.tripsService.update(id, user.id, dto);
  }

  // DELETE /trips/:id
  @Delete(':id')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Xóa chuyến đi (soft delete)' })
  delete(@Param('id', new ParseUUIDPipe()) id: string, @CurrentUser() user: any) {
    return this.tripsService.delete(id, user.id);
  }

  // POST /trips/:id/itinerary — thêm hoạt động
  @Post(':id/itinerary')
  @ApiOperation({ summary: 'Thêm hoạt động vào lịch trình' })
  addItinerary(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: any,
    @Body() dto: AddItineraryDto,
    @Headers('idempotency-key') idempotencyKey?: string,
  ) {
    return this.tripsService.addItineraryItem(id, user.id, dto, idempotencyKey);
  }

  // PUT /trips/:id/itinerary/reorder — kéo đổi thứ tự hoạt động và lưu bền vững (WP-TRIP-01)
  @Put(':id/itinerary/reorder')
  @ApiOperation({ summary: 'Sắp xếp lại thứ tự hoạt động trong lịch trình (atomic transaction)' })
  reorderItinerary(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: any,
    @Body() dto: ReorderItineraryDto,
  ) {
    return this.tripsService.reorderItineraryItems(id, user.id, dto);
  }

  // DELETE /trips/:id/itinerary/:itemId
  @Delete(':id/itinerary/:itemId')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Xóa hoạt động khỏi lịch trình' })
  removeItinerary(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Param('itemId', new ParseUUIDPipe()) itemId: string,
    @CurrentUser() user: any,
  ) {
    return this.tripsService.removeItineraryItem(id, itemId, user.id);
  }

  // POST /trips/:id/members — mời thành viên
  @Post(':id/members')
  @ApiOperation({ summary: 'Mời thành viên vào chuyến đi (bằng email)' })
  addMember(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: any,
    @Body() dto: InviteMemberDto,
  ) {
    return this.tripsService.addMember(id, user.id, dto.email);
  }

  // GET /trips/:id/invites — danh sách lời mời của chuyến đi (chủ chuyến)
  @Get(':id/invites')
  @ApiOperation({ summary: 'Danh sách lời mời tham gia chuyến đi (chủ chuyến)' })
  listTripInvites(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: { id: string },
  ) {
    return this._invites.listTripInvites(id, user.id);
  }

  // POST /trips/:id/invites — gửi lời mời tham gia chuyến đi (tạo TRIP_INVITE)
  @Post(':id/invites')
  @ApiOperation({ summary: 'Gửi lời mời tham gia chuyến đi (kèm thông báo TRIP_INVITE, chống trùng)' })
  createTripInvite(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: { id: string },
    @Body() dto: InviteMemberDto,
  ) {
    return this._invites.createInvite(id, user.id, dto.email);
  }

  // POST /trips/:id/invites/:inviteId/revoke — thu hồi lời mời theo chuyến
  @Post(':id/invites/:inviteId/revoke')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Thu hồi lời mời tham gia chuyến đi theo tripId' })
  revokeTripInvite(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Param('inviteId', new ParseUUIDPipe()) inviteId: string,
    @CurrentUser() user: { id: string },
  ) {
    return this._invites.revokeInvite(inviteId, user.id, id);
  }

  // POST /trips/:id/ai-plan — AI tạo lịch trình xem trước (không lưu DB)
  @Post(':id/ai-plan')
  @ApiOperation({ summary: 'AI tạo lịch trình xem trước dựa trên TripContext (không lưu DB)' })
  planWithAi(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: any,
    @Body() dto?: PlanTripDto,
    @Headers('x-request-id') requestId?: string,
  ) {
    return this.tripsService.planTripWithAi(id, user.id, dto, requestId);
  }

  // POST /trips/:id/itinerary/bulk — Lưu toàn bộ lịch trình vào DB (atomic transaction)
  @Post(':id/itinerary/bulk')
  @ApiOperation({ summary: 'Lưu toàn bộ lịch trình vào DB (atomic transaction)' })
  bulkSaveItinerary(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: any,
    @Body() dto: BulkItineraryDto,
    @Headers('idempotency-key') idempotencyKey?: string,
  ) {
    return this.tripsService.bulkSaveItinerary(id, user.id, dto, idempotencyKey);
  }
}
