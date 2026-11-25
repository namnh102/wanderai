import {
  IsString,
  IsNotEmpty,
  IsOptional,
  IsUUID,
  IsDateString,
  IsInt,
  Min,
  Max,
  MaxLength,
  IsIn,
  IsEnum,
  IsArray,
  ArrayMaxSize,
} from 'class-validator';
import { Transform } from 'class-transformer';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { TravelStyle } from '@prisma/client';

export class CreateTripDto {
  @ApiProperty({ description: 'Tên chuyến đi', example: 'Khám phá Hà Giang' })
  @Transform(({ value }) => (typeof value === 'string' ? value.trim() : value))
  @IsString()
  @IsNotEmpty({ message: 'Tên chuyến đi không được để trống' })
  @MaxLength(200, { message: 'Tên chuyến đi tối đa 200 ký tự' })
  title: string;

  @ApiPropertyOptional({ description: 'ID điểm đến', example: '123e4567-e89b-12d3-a456-426614174000' })
  @IsOptional()
  @IsUUID('all', { message: 'destinationId phải là UUID hợp lệ' })
  destinationId?: string;

  @ApiPropertyOptional({ description: 'Ngày bắt đầu (YYYY-MM-DD)', example: '2026-10-10' })
  @IsOptional()
  @IsDateString({}, { message: 'startDate phải có định dạng ngày hợp lệ' })
  startDate?: string;

  @ApiPropertyOptional({ description: 'Ngày kết thúc (YYYY-MM-DD)', example: '2026-10-15' })
  @IsOptional()
  @IsDateString({}, { message: 'endDate phải có định dạng ngày hợp lệ' })
  endDate?: string;

  @ApiPropertyOptional({ description: 'Tổng ngân sách (VND)', example: 5000000 })
  @IsOptional()
  @IsInt({ message: 'totalBudget phải là số nguyên' })
  @Min(0, { message: 'Ngân sách không được nhỏ hơn 0' })
  @Max(2147483647, { message: 'Ngân sách vượt quá giới hạn cho phép' })
  totalBudget?: number;

  @ApiPropertyOptional({ description: 'Đơn vị tiền tệ', example: 'VND', default: 'VND' })
  @IsOptional()
  @IsString()
  @IsIn(['VND', 'USD'], { message: 'Đơn vị tiền tệ phải là VND hoặc USD' })
  currency?: string;

  @ApiPropertyOptional({ description: 'Phong cách du lịch', enum: TravelStyle })
  @IsOptional()
  @IsEnum(TravelStyle, { message: 'Phong cách du lịch không hợp lệ' })
  travelStyle?: TravelStyle;

  @ApiPropertyOptional({ description: 'Sở thích du lịch', example: ['nature', 'food'] })
  @IsOptional()
  @IsArray({ message: 'interests phải là một danh sách' })
  @ArrayMaxSize(20, { message: 'interests tối đa 20 mục' })
  @IsString({ each: true, message: 'Mỗi sở thích phải là chuỗi' })
  @MaxLength(64, { each: true, message: 'Mỗi sở thích tối đa 64 ký tự' })
  interests?: string[];

  @ApiPropertyOptional({ description: 'Mô tả chuyến đi' })
  @IsOptional()
  @IsString()
  @MaxLength(2000, { message: 'Mô tả chuyến đi tối đa 2000 ký tự' })
  description?: string;
}
