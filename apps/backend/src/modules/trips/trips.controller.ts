import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Body,
  Param,
  UseGuards,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { IsString, IsOptional, IsNumber, IsDateString, IsEnum } from 'class-validator';
import { TripsService } from './trips.service';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { CurrentUser } from '../../common/decorators/current-user.decorator';

class CreateTripDto {
  @IsString() title: string;
  @IsOptional() @IsString() destinationId?: string;
  @IsOptional() @IsDateString() startDate?: string;
  @IsOptional() @IsDateString() endDate?: string;
  @IsOptional() @IsNumber() totalBudget?: number;
  @IsOptional() @IsString() description?: string;
}

class UpdateTripDto {
  @IsOptional() @IsString() title?: string;
  @IsOptional() @IsDateString() startDate?: string;
  @IsOptional() @IsDateString() endDate?: string;
  @IsOptional() @IsNumber() totalBudget?: number;
  @IsOptional() @IsString() description?: string;
  @IsOptional() @IsEnum(['DRAFT', 'PLANNED', 'ONGOING', 'COMPLETED', 'CANCELLED']) status?: string;
}

class AddItineraryDto {
  @IsNumber() dayNumber: number;
  @IsString() activity: string;         // Tên hoạt động (bắt buộc)
  @IsOptional() @IsString() startTime?: string;
  @IsOptional() @IsString() endTime?: string;
  @IsOptional() @IsString() placeId?: string;
  @IsOptional() @IsString() notes?: string;
  @IsOptional() @IsNumber() estimatedCost?: number;
  @IsOptional() @IsString() transportMode?: string;
}

class InviteMemberDto {
  @IsString() email: string;
}

@ApiTags('Trips')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('trips')
export class TripsController {
  constructor(private readonly tripsService: TripsService) {}

  // POST /trips
  @Post()
  @ApiOperation({ summary: 'Tạo chuyến đi mới' })
  create(@CurrentUser() user: any, @Body() dto: CreateTripDto) {
    return this.tripsService.create(user.id, dto);
  }

  // GET /trips
  @Get()
  @ApiOperation({ summary: 'Danh sách chuyến đi của tôi' })
  findAll(@CurrentUser() user: any) {
    return this.tripsService.findAll(user.id);
  }

  // GET /trips/:id
  @Get(':id')
  @ApiOperation({ summary: 'Chi tiết chuyến đi (+ lịch trình + thành viên)' })
  findById(@Param('id') id: string, @CurrentUser() user: any) {
    return this.tripsService.findById(id, user.id);
  }

  // PUT /trips/:id
  @Put(':id')
  @ApiOperation({ summary: 'Cập nhật chuyến đi' })
  update(@Param('id') id: string, @CurrentUser() user: any, @Body() dto: UpdateTripDto) {
    return this.tripsService.update(id, user.id, dto);
  }

  // DELETE /trips/:id
  @Delete(':id')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Xóa chuyến đi (soft delete)' })
  delete(@Param('id') id: string, @CurrentUser() user: any) {
    return this.tripsService.delete(id, user.id);
  }

  // POST /trips/:id/itinerary — thêm hoạt động
  @Post(':id/itinerary')
  @ApiOperation({ summary: 'Thêm hoạt động vào lịch trình' })
  addItinerary(
    @Param('id') id: string,
    @CurrentUser() user: any,
    @Body() dto: AddItineraryDto,
  ) {
    return this.tripsService.addItineraryItem(id, user.id, dto);
  }

  // DELETE /trips/:id/itinerary/:itemId
  @Delete(':id/itinerary/:itemId')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Xóa hoạt động khỏi lịch trình' })
  removeItinerary(
    @Param('id') id: string,
    @Param('itemId') itemId: string,
    @CurrentUser() user: any,
  ) {
    return this.tripsService.removeItineraryItem(id, itemId, user.id);
  }

  // POST /trips/:id/members — mời thành viên
  @Post(':id/members')
  @ApiOperation({ summary: 'Mời thành viên vào chuyến đi (bằng email)' })
  addMember(
    @Param('id') id: string,
    @CurrentUser() user: any,
    @Body() dto: InviteMemberDto,
  ) {
    return this.tripsService.addMember(id, user.id, dto.email);
  }
}
