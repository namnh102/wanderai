import {
  Controller,
  Get,
  Post,
  Param,
  Query,
  Body,
  UseGuards,
  ParseUUIDPipe,
  UnauthorizedException,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { VideosService } from './videos.service';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { CreateVideoDto, VideoFeedQueryDto } from './dto/video.dto';

@ApiTags('Videos')
@Controller('videos')
export class VideosController {
  constructor(private readonly videosService: VideosService) {}

  @Get('feed')
  @ApiOperation({ summary: 'Get short videos feed' })
  getFeed(@Query() query: VideoFeedQueryDto) {
    return this.videosService.getFeed(query.page, query.limit);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get video by id' })
  findById(@Param('id', new ParseUUIDPipe()) id: string) {
    return this.videosService.findById(id);
  }

  @Post()
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Upload/create a video' })
  create(@CurrentUser() user: { id?: string } | undefined, @Body() data: CreateVideoDto) {
    if (!user?.id) {
      throw new UnauthorizedException('Yêu cầu đăng nhập để tạo video');
    }
    return this.videosService.create(data, user.id);
  }
}
