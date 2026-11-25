import {
  Controller,
  Get,
  Post,
  Delete,
  Param,
  ParseUUIDPipe,
  Query,
  Body,
  UseGuards,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { ReviewsService } from './reviews.service';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import {
  CreateReviewDto,
  ReviewListQueryDto,
  ReviewMyQueryDto,
} from './dto/review.dto';

@ApiTags('Reviews')
@Controller('reviews')
export class ReviewsController {
  constructor(private readonly reviewsService: ReviewsService) {}

  // GET /reviews?placeId=<id>&page=1
  @Get()
  @ApiOperation({ summary: 'Lấy reviews của một địa điểm' })
  findByPlace(@Query() query: ReviewListQueryDto) {
    return this.reviewsService.findByPlace(query.placeId, query.page, query.limit);
  }

  // GET /reviews/my
  @Get('my')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Lấy reviews của tôi' })
  findMyReviews(
    @CurrentUser() user: any,
    @Query() query: ReviewMyQueryDto,
  ) {
    return this.reviewsService.findMyReviews(user.id, query.page, query.limit);
  }

  // GET /reviews/:id
  @Get(':id')
  @ApiOperation({ summary: 'Lấy chi tiết một review' })
  findById(@Param('id', new ParseUUIDPipe()) id: string) {
    return this.reviewsService.findById(id);
  }

  // POST /reviews
  @Post()
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Tạo review mới (1-5 sao + nội dung)' })
  create(@CurrentUser() user: any, @Body() dto: CreateReviewDto) {
    return this.reviewsService.create(user.id, dto);
  }

  // DELETE /reviews/:id
  @Delete(':id')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Xóa review của mình' })
  delete(@Param('id', new ParseUUIDPipe()) id: string, @CurrentUser() user: any) {
    return this.reviewsService.delete(id, user.id);
  }
}
