import { Controller, Get, Post, Param, Query, Body, UseGuards, DefaultValuePipe, ParseIntPipe, Request } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery, ApiBearerAuth } from '@nestjs/swagger';
import { ReviewsService } from './reviews.service';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';

@ApiTags('Reviews')
@Controller('reviews')
export class ReviewsController {
  constructor(private readonly reviewsService: ReviewsService) {}

  @Get()
  @ApiOperation({ summary: 'Get reviews by place id' })
  @ApiQuery({ name: 'placeId' })
  @ApiQuery({ name: 'page', required: false })
  findByPlace(
    @Query('placeId') placeId: string,
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
  ) {
    return this.reviewsService.findByPlace(placeId, page);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get review by id' })
  findById(@Param('id') id: string) {
    return this.reviewsService.findById(id);
  }

  @Post()
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Create a new review' })
  create(@Request() req, @Body() data: any) {
    return this.reviewsService.create(req.user.id, data);
  }
}
