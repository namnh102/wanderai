import { Controller, Get, Param, Query, ParseIntPipe, DefaultValuePipe, ParseFloatPipe } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiQuery } from '@nestjs/swagger';
import { DestinationsService } from './destinations.service';

@ApiTags('Destinations')
@Controller('destinations')
export class DestinationsController {
  constructor(private readonly destinationsService: DestinationsService) {}

  @Get()
  @ApiOperation({ summary: 'Get destinations with pagination and search' })
  @ApiQuery({ name: 'page', required: false })
  @ApiQuery({ name: 'limit', required: false })
  @ApiQuery({ name: 'search', required: false })
  findAll(
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
    @Query('limit', new DefaultValuePipe(20), ParseIntPipe) limit: number,
    @Query('search') search?: string,
  ) {
    return this.destinationsService.findAll(page, limit, search);
  }

  @Get('nearby')
  @ApiOperation({ summary: 'Find nearby destinations using coordinates' })
  @ApiQuery({ name: 'lat' })
  @ApiQuery({ name: 'lng' })
  @ApiQuery({ name: 'radius', required: false })
  findNearby(
    @Query('lat', ParseFloatPipe) lat: number,
    @Query('lng', ParseFloatPipe) lng: number,
    @Query('radius', new DefaultValuePipe(10), ParseFloatPipe) radius: number,
  ) {
    return this.destinationsService.findNearby(lat, lng, radius);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get destination by id' })
  findById(@Param('id') id: string) {
    return this.destinationsService.findById(id);
  }
}
