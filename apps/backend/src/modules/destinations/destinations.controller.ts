import { Controller, Get, Param, ParseUUIDPipe, Query } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';
import { DestinationsService } from './destinations.service';
import {
  DestinationListQueryDto,
  DestinationNearbyQueryDto,
  DestinationPopularQueryDto,
} from './dto/destination-query.dto';

@ApiTags('Destinations')
@Controller('destinations')
export class DestinationsController {
  constructor(private destinationsService: DestinationsService) {}

  @Get()
  @ApiOperation({ summary: 'Lấy danh sách điểm đến' })
  async findAll(@Query() query: DestinationListQueryDto) {
    return this.destinationsService.findAll(
      query.page,
      query.limit,
      query.search,
      query.region,
    );
  }

  @Get('popular')
  @ApiOperation({ summary: 'Lấy điểm đến nổi bật' })
  async findPopular(@Query() query: DestinationPopularQueryDto) {
    return this.destinationsService.findPopular(query.limit);
  }

  @Get('nearby')
  @ApiOperation({ summary: 'Tìm điểm đến gần vị trí GPS' })
  async findNearby(@Query() query: DestinationNearbyQueryDto) {
    return this.destinationsService.findNearby(
      query.lat,
      query.lng,
      query.radius,
    );
  }

  @Get(':id')
  @ApiOperation({ summary: 'Chi tiết điểm đến + danh sách places' })
  async findById(@Param('id', new ParseUUIDPipe()) id: string) {
    return this.destinationsService.findById(id);
  }
}
