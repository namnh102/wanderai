import {
  Body,
  Controller,
  Get,
  Headers,
  HttpCode,
  HttpStatus,
  Param,
  ParseUUIDPipe,
  Post,
  Query,
  Req,
  Res,
  UseGuards,
} from "@nestjs/common";
import { ApiOperation, ApiResponse, ApiTags } from "@nestjs/swagger";
import { Request, Response } from "express";
import {
  IngestYoutubeEventDto,
  YoutubeDestinationUpdatesQueryDto,
  YoutubePlaceUpdatesQueryDto,
} from "./dto/youtube-update.dto";
import { YoutubeInternalSecretGuard } from "./guards/youtube-internal-secret.guard";
import { YoutubeService } from "./youtube.service";

export interface RawXmlRequest extends Request {
  rawBodyText?: string;
}

@ApiTags("YouTube Updates")
@Controller("youtube")
export class YoutubeController {
  constructor(private readonly youtubeService: YoutubeService) {}

  @Get("webhook")
  @ApiOperation({
    summary: "Xác minh đăng ký YouTube WebSub (PubSubHubbub hub.challenge)",
  })
  @ApiResponse({
    status: 200,
    description: "Trả về nguyên văn chuỗi hub.challenge dạng text/plain",
  })
  verifyWebSub(
    @Query() query: Record<string, string | undefined>,
    @Res() res: Response,
  ): void {
    const challenge = this.youtubeService.verifyWebSubHandshake(query);
    res.status(HttpStatus.OK).type("text/plain").send(challenge);
  }

  @Post("webhook")
  @HttpCode(HttpStatus.OK)
  @ApiOperation({
    summary:
      "Nhận đẩy cập nhật Atom XML từ YouTube WebSub, khử trùng lặp, lưu giờ đăng/giờ nhận và chỉ gắn POI/thành phố khi có căn cứ",
  })
  async receiveWebSubFeed(
    @Req() req: RawXmlRequest,
    @Headers("x-hub-signature") signatureHeader?: string,
    @Headers("x-hub-signature-256") signature256Header?: string,
  ) {
    const xmlBody =
      typeof req.rawBodyText === "string"
        ? req.rawBodyText
        : typeof req.body === "string"
          ? req.body
          : "";
    return this.youtubeService.ingestAtomWebhook(
      xmlBody,
      signatureHeader ?? signature256Header,
    );
  }

  @Post("events")
  @UseGuards(YoutubeInternalSecretGuard)
  @HttpCode(HttpStatus.OK)
  @ApiOperation({
    summary:
      "Nhận sự kiện cập nhật YouTube dạng JSON, khử trùng lặp sự kiện, lưu giờ đăng/giờ nhận UTC và kiểm chứng căn cứ gắn POI/thành phố",
  })
  async ingestEvent(@Body() dto: IngestYoutubeEventDto) {
    return this.youtubeService.ingestJsonEvent(dto);
  }

  @Get("places/:placeId/updates")
  @ApiOperation({
    summary:
      "Lấy danh sách bài/video YouTube đã xác minh căn cứ gắn với một POI",
  })
  async getUpdatesForPlace(
    @Param("placeId", new ParseUUIDPipe()) placeId: string,
    @Query() query: YoutubePlaceUpdatesQueryDto,
  ) {
    return this.youtubeService.listGroundedUpdatesForPlace(
      placeId,
      query.limit,
    );
  }

  @Get("destinations/:idOrSlug/updates")
  @ApiOperation({
    summary:
      "Lấy danh sách bài/video YouTube theo điểm đến (UUID hoặc slug, hỗ trợ fallback cấp thành phố)",
  })
  async getUpdatesForDestination(
    @Param("idOrSlug") idOrSlug: string,
    @Query() query: YoutubeDestinationUpdatesQueryDto,
  ) {
    return this.youtubeService.listGroundedUpdatesForDestination(
      idOrSlug,
      query.limit,
      query.scope,
    );
  }
}

@ApiTags("Places")
@Controller("places")
export class YoutubePlaceUpdatesController {
  constructor(private readonly youtubeService: YoutubeService) {}

  @Get(":id/youtube-updates")
  @ApiOperation({
    summary:
      "Lấy các cập nhật YouTube (tầng độ tươi xã hội) đã đủ căn cứ gắn với địa điểm xác minh",
  })
  async getPlaceYoutubeUpdates(
    @Param("id", new ParseUUIDPipe()) id: string,
    @Query() query: YoutubePlaceUpdatesQueryDto,
  ) {
    return this.youtubeService.listGroundedUpdatesForPlace(id, query.limit);
  }
}

@ApiTags("Destinations")
@Controller("destinations")
export class YoutubeDestinationUpdatesController {
  constructor(private readonly youtubeService: YoutubeService) {}

  @Get(":idOrSlug/youtube-updates")
  @ApiOperation({
    summary:
      "Lấy các cập nhật YouTube (tầng độ tươi xã hội) theo điểm đến hoặc thành phố",
  })
  async getDestinationYoutubeUpdates(
    @Param("idOrSlug") idOrSlug: string,
    @Query() query: YoutubeDestinationUpdatesQueryDto,
  ) {
    return this.youtubeService.listGroundedUpdatesForDestination(
      idOrSlug,
      query.limit,
      query.scope,
    );
  }
}
