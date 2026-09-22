import { Controller, Get, Param, Query, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery, ApiResponse } from '@nestjs/swagger';
import { DestinationsService } from './destinations.service';

@ApiTags('Destinations')
@Controller('destinations')
export class DestinationsController {
  constructor(private destinationsService: DestinationsService) {}

  @Get()
  @ApiOperation({ summary: 'Lấy danh sách điểm đến' })
  @ApiQuery({ name: 'page', required: false, type: Number, example: 1 })
  @ApiQuery({ name: 'limit', required: false, type: Number, example: 20 })
  @ApiQuery({ name: 'search', required: false, type: String, example: 'đà nẵng' })
  @ApiQuery({ name: 'region', required: false, enum: ['north', 'central', 'south'] })
  async findAll(
    @Query('page') page?: string,
    @Query('limit') limit?: string,
    @Query('search') search?: string,
    @Query('region') region?: string,
  ) {
    return this.destinationsService.findAll(
      Number(page) || 1,
      Number(limit) || 20,
      search,
      region,
    );
  }

  @Get('popular')
  @ApiOperation({ summary: 'Lấy điểm đến nổi bật' })
  async findPopular(@Query('limit') limit?: string) {
    return this.destinationsService.findPopular(Number(limit) || 10);
  }

  @Get('nearby')
  @ApiOperation({ summary: 'Tìm điểm đến gần vị trí GPS' })
  @ApiQuery({ name: 'lat', required: true, type: Number, example: 16.0544 })
  @ApiQuery({ name: 'lng', required: true, type: Number, example: 108.2022 })
  @ApiQuery({ name: 'radius', required: false, type: Number, example: 50 })
  async findNearby(
    @Query('lat') lat: string,
    @Query('lng') lng: string,
    @Query('radius') radius?: string,
  ) {
    return this.destinationsService.findNearby(
      Number(lat), Number(lng), Number(radius) || 50,
    );
  }

  @Get(':id')
  @ApiOperation({ summary: 'Chi tiết điểm đến + danh sách places' })
  async findById(@Param('id') id: string) {
    return this.destinationsService.findById(id);
  }
}
