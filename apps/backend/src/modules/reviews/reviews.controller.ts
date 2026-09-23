import {
  Controller,
  Get,
  Post,
  Delete,
  Param,
  Query,
  Body,
  UseGuards,
  DefaultValuePipe,
  ParseIntPipe,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery, ApiBearerAuth } from '@nestjs/swagger';
import { IsNumber, IsString, IsOptional, IsArray, Min, Max } from 'class-validator';
import { ReviewsService } from './reviews.service';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { CurrentUser } from '../../common/decorators/current-user.decorator';

class CreateReviewDto {
  @IsString() placeId: string;
  @IsNumber() @Min(1) @Max(5) rating: number;
  @IsString() content: string;
  @IsOptional() @IsString() visitDate?: string;
  @IsOptional() @IsArray() images?: string[];
}

@ApiTags('Reviews')
@Controller('reviews')
export class ReviewsController {
  constructor(private readonly reviewsService: ReviewsService) {}

  // GET /reviews?placeId=<id>&page=1
  @Get()
  @ApiOperation({ summary: 'Lấy reviews của một địa điểm' })
  @ApiQuery({ name: 'placeId', required: true, description: 'ID của Place' })
  @ApiQuery({ name: 'page', required: false })
  @ApiQuery({ name: 'limit', required: false })
  findByPlace(
    @Query('placeId') placeId: string,
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
    @Query('limit', new DefaultValuePipe(20), ParseIntPipe) limit: number,
  ) {
    return this.reviewsService.findByPlace(placeId, page, limit);
  }

  // GET /reviews/my
  @Get('my')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Lấy reviews của tôi' })
  findMyReviews(
    @CurrentUser() user: any,
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
    @Query('limit', new DefaultValuePipe(20), ParseIntPipe) limit: number,
  ) {
    return this.reviewsService.findMyReviews(user.id, page, limit);
  }

  // GET /reviews/:id
  @Get(':id')
  @ApiOperation({ summary: 'Lấy chi tiết một review' })
  findById(@Param('id') id: string) {
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
  delete(@Param('id') id: string, @CurrentUser() user: any) {
    return this.reviewsService.delete(id, user.id);
  }
}
