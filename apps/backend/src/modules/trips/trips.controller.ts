import { Controller, Get, Post, Put, Delete, Body, Param, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { TripsService } from './trips.service';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { CurrentUser } from '../../common/decorators/current-user.decorator';

@ApiTags('Trips')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('trips')
export class TripsController {
  constructor(private readonly tripsService: TripsService) {}

  @Post()
  @ApiOperation({ summary: 'Create a new trip' })
  create(@CurrentUser() user: any, @Body() data: any) {
    return this.tripsService.create(user.id, data);
  }

  @Get()
  @ApiOperation({ summary: 'Get all trips for current user' })
  findAll(@CurrentUser() user: any) {
    return this.tripsService.findAll(user.id);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get trip by id' })
  findById(@Param('id') id: string, @CurrentUser() user: any) {
    return this.tripsService.findById(id, user.id);
  }

  @Put(':id')
  @ApiOperation({ summary: 'Update trip' })
  update(@Param('id') id: string, @CurrentUser() user: any, @Body() data: any) {
    return this.tripsService.update(id, user.id, data);
  }

  @Delete(':id')
  @ApiOperation({ summary: 'Delete trip (soft delete)' })
  delete(@Param('id') id: string, @CurrentUser() user: any) {
    return this.tripsService.delete(id, user.id);
  }

  @Post(':id/itinerary')
  @ApiOperation({ summary: 'Add an itinerary item to a trip' })
  addItinerary(@Param('id') id: string, @CurrentUser() user: any, @Body() data: any) {
    return this.tripsService.addItinerary(id, user.id, data);
  }
}
