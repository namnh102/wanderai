import { Controller, Get, Param, Query } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery } from '@nestjs/swagger';
import { PlacesService } from './places.service';

@ApiTags('Places')
@Controller('places')
export class PlacesController {
  constructor(private readonly placesService: PlacesService) {}

  @Get()
  @ApiOperation({ summary: 'Lấy danh sách địa điểm du lịch (hỗ trợ phân trang, tìm kiếm, lọc theo thể loại, điểm đến)' })
  @ApiQuery({ name: 'page', required: false, type: Number, example: 1 })
  @ApiQuery({ name: 'limit', required: false, type: Number, example: 20 })
  @ApiQuery({ name: 'search', required: false, type: String, example: 'Cầu Rồng' })
  @ApiQuery({ name: 'category', required: false, type: String, example: 'attraction' })
  @ApiQuery({ name: 'destinationId', required: false, type: String })
  @ApiQuery({ name: 'verifiedOnly', required: false, type: Boolean, example: true, description: 'Mặc định true: chỉ trả về địa điểm đã kiểm chứng provenance (OSM canonical). Truyền false để gồm cả bản ghi dev/test chưa có nguồn' })
  async findAll(
    @Query('page') page?: string,
    @Query('limit') limit?: string,
    @Query('search') search?: string,
    @Query('category') category?: string,
    @Query('destinationId') destinationId?: string,
    @Query('verifiedOnly') verifiedOnly?: string,
  ) {
    return this.placesService.findAll(
      page ? Number(page) : 1,
      limit ? Number(limit) : 20,
      search,
      category,
      destinationId,
      verifiedOnly !== 'false', // default: verified places only; ?verifiedOnly=false includes unsourced dev/test records
    );
  }

  @Get('nearby')
  @ApiOperation({ summary: 'Tìm kiếm địa điểm lân cận bằng tọa độ GPS (PostGIS)' })
  @ApiQuery({ name: 'lat', required: true, type: Number, example: 16.0612 })
  @ApiQuery({ name: 'lng', required: true, type: Number, example: 108.2272 })
  @ApiQuery({ name: 'radius', required: false, type: Number, example: 10, description: 'Bán kính tính bằng km' })
  @ApiQuery({ name: 'limit', required: false, type: Number, example: 20 })
  @ApiQuery({ name: 'verifiedOnly', required: false, type: Boolean, example: true, description: 'Mặc định true. Truyền false để gồm cả bản ghi dev/test chưa có nguồn' })
  async findNearby(
    @Query('lat') lat: string,
    @Query('lng') lng: string,
    @Query('radius') radius?: string,
    @Query('limit') limit?: string,
    @Query('verifiedOnly') verifiedOnly?: string,
  ) {
    return this.placesService.findNearby(
      Number(lat),
      Number(lng),
      radius ? Number(radius) : 10,
      limit ? Number(limit) : 20,
      verifiedOnly !== 'false', // default: verified places only; ?verifiedOnly=false includes unsourced dev/test records
    );
  }

  @Get(':id')
  @ApiOperation({ summary: 'Xem chi tiết địa điểm, nguồn dữ liệu xác minh (provenance) và đánh giá' })
  async findById(@Param('id') id: string) {
    return this.placesService.findById(id);
  }
}
