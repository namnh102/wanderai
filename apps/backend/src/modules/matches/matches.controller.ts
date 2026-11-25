import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
  Query,
  UseGuards,
} from "@nestjs/common";
import { ApiBearerAuth, ApiOperation, ApiTags } from "@nestjs/swagger";
import { CurrentUser } from "../../common/decorators/current-user.decorator";
import { JwtAuthGuard } from "../../common/guards/jwt-auth.guard";
import {
  BlockBuddyDto,
  CreateMatchRequestDto,
  MatchCandidatesQueryDto,
  RespondMatchDto,
  UpdateDiscoveryConsentDto,
} from "./dto/match.dto";
import { MatchesService } from "./matches.service";

@ApiTags("Matches (W08 Buddy Matching)")
@UseGuards(JwtAuthGuard)
@ApiBearerAuth()
@Controller("matches")
export class MatchesController {
  constructor(private readonly matchesService: MatchesService) {}

  @Get("discovery")
  @ApiOperation({
    summary: "Xem trạng thái bật/tắt đồng thuận tìm bạn đồng hành của bản thân",
  })
  getDiscoveryStatus(@CurrentUser() user: { id: string }) {
    return this.matchesService.getDiscoveryConsent(user.id);
  }

  @Patch("discovery")
  @ApiOperation({
    summary:
      "Bật hoặc tắt đồng thuận hiển thị hồ sơ rút gọn để tìm bạn đồng hành",
  })
  updateDiscoveryStatus(
    @CurrentUser() user: { id: string },
    @Body() dto: UpdateDiscoveryConsentDto,
  ) {
    return this.matchesService.updateDiscoveryConsent(
      user.id,
      dto.isDiscoverable,
    );
  }

  @Get("candidates")
  @ApiOperation({
    summary:
      "Tìm ứng viên bạn đồng hành phù hợp (chỉ hiển thị người bật opt-in, loại trừ chặn hai chiều, ẩn PII)",
  })
  listCandidates(
    @CurrentUser() user: { id: string },
    @Query() query: MatchCandidatesQueryDto,
  ) {
    return this.matchesService.listCandidates(
      user.id,
      query.destinationId,
      query.limit,
    );
  }

  @Get("peers/:peerId")
  @ApiOperation({
    summary:
      "Mở hồ sơ rút gọn đã che thông tin nhạy cảm (email, SĐT, tọa độ, danh bạ khẩn cấp)",
  })
  getMaskedProfile(
    @CurrentUser() user: { id: string },
    @Param("peerId", new ParseUUIDPipe()) peerId: string,
  ) {
    return this.matchesService.getMaskedPeerProfile(user.id, peerId);
  }

  @Get("blocks")
  @ApiOperation({
    summary: "Danh sách người dùng đang bị chặn bởi tài khoản này",
  })
  listBlocks(@CurrentUser() user: { id: string }) {
    return this.matchesService.listBlockedUsers(user.id);
  }

  @Post("blocks")
  @ApiOperation({
    summary: "Chặn hai chiều một người dùng và hủy mọi lời mời/kết nối đang mở",
  })
  blockUser(@CurrentUser() user: { id: string }, @Body() dto: BlockBuddyDto) {
    return this.matchesService.blockUser(user.id, dto.blockedUserId);
  }

  @Delete("blocks/:blockedUserId")
  @ApiOperation({ summary: "Gỡ chặn người dùng" })
  unblockUser(
    @CurrentUser() user: { id: string },
    @Param("blockedUserId", new ParseUUIDPipe()) blockedUserId: string,
  ) {
    return this.matchesService.unblockUser(user.id, blockedUserId);
  }

  @Get()
  @ApiOperation({
    summary: "Danh sách kết nối bạn đồng hành đã gửi và đã nhận",
  })
  listMyMatches(@CurrentUser() user: { id: string }) {
    return this.matchesService.listMyMatches(user.id);
  }

  @Post("request")
  @ApiOperation({ summary: "Gửi lời mời kết bạn đồng hành" })
  sendRequest(
    @CurrentUser() user: { id: string },
    @Body() dto: CreateMatchRequestDto,
  ) {
    return this.matchesService.sendMatchRequest(user.id, dto.receiverId);
  }

  @Patch(":id/withdraw")
  @ApiOperation({
    summary:
      "Người gửi rút lại lời mời đang ở trạng thái PENDING trước khi chấp nhận",
  })
  withdraw(
    @Param("id", new ParseUUIDPipe()) id: string,
    @CurrentUser() user: { id: string },
  ) {
    return this.matchesService.withdrawMatchRequest(id, user.id);
  }

  @Patch(":id/respond")
  @ApiOperation({
    summary:
      "Người nhận chấp nhận hoặc từ chối lời mời (kiểm tra lại đồng thuận hai phía và trạng thái chặn)",
  })
  respond(
    @Param("id", new ParseUUIDPipe()) id: string,
    @CurrentUser() user: { id: string },
    @Body() dto: RespondMatchDto,
  ) {
    return this.matchesService.respondToMatch(id, user.id, dto.action);
  }
}
