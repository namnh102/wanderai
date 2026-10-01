import {
  IsString,
  IsNotEmpty,
  IsOptional,
  IsUUID,
  IsDateString,
  IsInt,
  Min,
  IsIn,
  IsEnum,
  IsArray,
} from 'class-validator';
import { ApiPropertyOptional } from '@nestjs/swagger';
import { TravelStyle, TripStatus } from '@prisma/client';

export class UpdateTripDto {
  @ApiPropertyOptional({ description: 'Tên chuyến đi' })
  @IsOptional()
  @IsString()
  @IsNotEmpty({ message: 'Tên chuyến đi không được để trống' })
  title?: string;

  @ApiPropertyOptional({ description: 'ID điểm đến' })
  @IsOptional()
  @IsUUID('all', { message: 'destinationId phải là UUID hợp lệ' })
  destinationId?: string;

  @ApiPropertyOptional({ description: 'Ngày bắt đầu' })
  @IsOptional()
  @IsDateString({}, { message: 'startDate phải có định dạng ngày hợp lệ' })
  startDate?: string;

  @ApiPropertyOptional({ description: 'Ngày kết thúc' })
  @IsOptional()
  @IsDateString({}, { message: 'endDate phải có định dạng ngày hợp lệ' })
  endDate?: string;

  @ApiPropertyOptional({ description: 'Tổng ngân sách' })
  @IsOptional()
  @IsInt({ message: 'totalBudget phải là số nguyên' })
  @Min(0, { message: 'Ngân sách không được nhỏ hơn 0' })
  totalBudget?: number;

  @ApiPropertyOptional({ description: 'Đơn vị tiền tệ' })
  @IsOptional()
  @IsString()
  @IsIn(['VND', 'USD'], { message: 'Đơn vị tiền tệ phải là VND hoặc USD' })
  currency?: string;

  @ApiPropertyOptional({ description: 'Phong cách du lịch', enum: TravelStyle })
  @IsOptional()
  @IsEnum(TravelStyle, { message: 'Phong cách du lịch không hợp lệ' })
  travelStyle?: TravelStyle;

  @ApiPropertyOptional({ description: 'Sở thích du lịch' })
  @IsOptional()
  @IsArray({ message: 'interests phải là một danh sách' })
  @IsString({ each: true, message: 'Mỗi sở thích phải là chuỗi' })
  interests?: string[];

  @ApiPropertyOptional({ description: 'Mô tả chuyến đi' })
  @IsOptional()
  @IsString()
  description?: string;

  @ApiPropertyOptional({ description: 'Trạng thái chuyến đi', enum: TripStatus })
  @IsOptional()
  @IsEnum(TripStatus, { message: 'Trạng thái chuyến đi không hợp lệ' })
  status?: TripStatus;
}
