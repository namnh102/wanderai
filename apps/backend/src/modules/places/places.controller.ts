import { Controller, Get, Param, ParseUUIDPipe, Query, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { PlacesService } from './places.service';
import { RecommendationQueryDto } from './dto/recommendation-query.dto';
import { NearbyQueryDto, PlaceListQueryDto } from './dto/place-query.dto';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { CurrentUser } from '../../common/decorators/current-user.decorator';

@ApiTags('Places')
@Controller('places')
export class PlacesController {
  constructor(private readonly placesService: PlacesService) {}

  @Get()
  @ApiOperation({ summary: 'Lấy danh sách địa điểm du lịch (hỗ trợ phân trang, tìm kiếm, lọc theo thể loại, điểm đến)' })
  async findAll(@Query() query: PlaceListQueryDto) {
    return this.placesService.findAll(
      query.page,
      query.limit,
      query.search,
      query.category,
      query.destinationId,
      query.verifiedOnly, // default: verified places only; ?verifiedOnly=false includes unsourced dev/test records
    );
  }

  @Get('nearby')
  @ApiOperation({ summary: 'Tìm kiếm địa điểm lân cận bằng tọa độ GPS (PostGIS)' })
  async findNearby(@Query() query: NearbyQueryDto) {
    return this.placesService.findNearby(query.lat, query.lng, query.radius, query.limit, query.verifiedOnly);
  }

  @Get('recommendations')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Lấy danh sách địa điểm gợi ý cá nhân hóa dựa trên sở thích du lịch (REC-A)' })
  async getRecommendations(
    @CurrentUser() user: any,
    @Query() query: RecommendationQueryDto,
  ) {
    return this.placesService.getRecommendations(
      user.id,
      query.destination,
      query.topK,
      query.model,
    );
  }

  @Get(':id')
  @ApiOperation({ summary: 'Xem chi tiết địa điểm, nguồn dữ liệu xác minh (provenance) và đánh giá' })
  async findById(@Param('id', new ParseUUIDPipe()) id: string) {
    return this.placesService.findById(id);
  }
}
