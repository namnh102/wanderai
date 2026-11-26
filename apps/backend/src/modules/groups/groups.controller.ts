import {
  Body,
  Controller,
  Delete,
  Get,
  Headers,
  HttpCode,
  HttpStatus,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
  Put,
  UseGuards,
} from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { ReorderItineraryDto } from '../trips/dto/reorder-itinerary.dto';
import { AddGroupMemberDto } from './dto/add-group-member.dto';
import { CreateGroupDto } from './dto/create-group.dto';
import {
  ProposeGroupItineraryItemDto,
  VoteItineraryItemDto,
} from './dto/group-itinerary.dto';
import { UpdateGroupDto } from './dto/update-group.dto';
import { GroupItineraryService } from './group-itinerary.service';
import { GroupsService } from './groups.service';

interface AuthenticatedUser {
  id: string;
}

@ApiTags('Groups')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('groups')
export class GroupsController {
  constructor(
    private readonly groupsService: GroupsService,
    private readonly groupItineraryService: GroupItineraryService,
  ) {}

  @Post()
  @ApiOperation({ summary: 'Tạo nhóm đồng hành mới' })
  create(
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: CreateGroupDto,
  ) {
    return this.groupsService.create(user.id, dto);
  }

  @Get()
  @ApiOperation({ summary: 'Danh sách nhóm đồng hành của tôi' })
  findAll(@CurrentUser() user: AuthenticatedUser) {
    return this.groupsService.findAll(user.id);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Chi tiết nhóm đồng hành và danh sách thành viên' })
  findById(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: AuthenticatedUser,
  ) {
    return this.groupsService.findById(id, user.id);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Cập nhật thông tin nhóm (chỉ admin)' })
  update(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: UpdateGroupDto,
  ) {
    return this.groupsService.update(id, user.id, dto);
  }

  @Post(':id/members')
  @ApiOperation({ summary: 'Thêm thành viên vào nhóm theo userId (chỉ admin)' })
  addMember(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: AddGroupMemberDto,
  ) {
    return this.groupsService.addMember(id, user.id, dto);
  }

  @Delete(':id/members/:userId')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Xóa thành viên khỏi nhóm (chỉ admin)' })
  removeMember(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Param('userId', new ParseUUIDPipe()) targetUserId: string,
    @CurrentUser() user: AuthenticatedUser,
  ) {
    return this.groupsService.removeMember(id, user.id, targetUserId);
  }

  // ============================================================
  // W10 WP-ITIN-01: Group Itinerary & Voting
  // ============================================================

  @Get(':id/itinerary')
  @ApiOperation({ summary: 'Xem lịch trình chung và điểm bình chọn của nhóm' })
  getItinerary(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: AuthenticatedUser,
  ) {
    return this.groupItineraryService.getItinerary(id, user.id);
  }

  @Post(':id/itinerary/items')
  @ApiOperation({ summary: 'Đề xuất hoạt động mới vào lịch trình nhóm' })
  proposeItineraryItem(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: ProposeGroupItineraryItemDto,
    @Headers('idempotency-key') idempotencyKey?: string,
  ) {
    return this.groupItineraryService.proposeItem(
      id,
      user.id,
      dto,
      idempotencyKey,
    );
  }

  @Delete(':id/itinerary/items/:itemId')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Xóa hoạt động lịch trình từ nhóm' })
  deleteItineraryItem(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Param('itemId', new ParseUUIDPipe()) itemId: string,
    @CurrentUser() user: AuthenticatedUser,
  ) {
    return this.groupItineraryService.deleteItem(id, itemId, user.id);
  }

  @Put(':id/itinerary/reorder')
  @ApiOperation({ summary: 'Đổi thứ tự lịch trình từ nhóm (chỉ chủ chuyến)' })
  reorderItineraryItems(
    @Param('id', new ParseUUIDPipe()) id: string,
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: ReorderItineraryDto,
  ) {
    return this.groupItineraryService.reorderItems(id, user.id, dto);
  }

  @Put(':id/itinerary/items/:itemId/vote')
  @ApiOperation({ summary: 'Bỏ phiếu hoặc đổi phiếu cho hoạt động lịch trình' })
  voteItineraryItem(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Param('itemId', new ParseUUIDPipe()) itemId: string,
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: VoteItineraryItemDto,
  ) {
    return this.groupItineraryService.voteItem(id, itemId, user.id, dto);
  }

  @Delete(':id/itinerary/items/:itemId/vote')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Rút phiếu bầu trên hoạt động lịch trình' })
  withdrawItineraryVote(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Param('itemId', new ParseUUIDPipe()) itemId: string,
    @CurrentUser() user: AuthenticatedUser,
  ) {
    return this.groupItineraryService.withdrawVote(id, itemId, user.id);
  }
}
