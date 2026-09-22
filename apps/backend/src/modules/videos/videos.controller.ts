import { Controller, Get, Post, Param, Query, Body, UseGuards, DefaultValuePipe, ParseIntPipe, Request } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery, ApiBearerAuth } from '@nestjs/swagger';
import { VideosService } from './videos.service';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';

@ApiTags('Videos')
@Controller('videos')
export class VideosController {
  constructor(private readonly videosService: VideosService) {}

  @Get('feed')
  @ApiOperation({ summary: 'Get short videos feed' })
  @ApiQuery({ name: 'page', required: false })
  getFeed(@Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number) {
    return this.videosService.getFeed(page);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get video by id' })
  findById(@Param('id') id: string) {
    return this.videosService.findById(id);
  }

  @Post()
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Upload/create a video' })
  create(@Request() req, @Body() data: any) {
    return this.videosService.create(data, req.user?.id);
  }
}
