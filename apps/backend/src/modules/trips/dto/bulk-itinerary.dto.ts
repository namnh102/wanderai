import {
  IsString,
  IsNotEmpty,
  IsOptional,
  IsInt,
  Min,
  IsArray,
  ValidateNested,
  IsBoolean,
  IsDateString,
} from 'class-validator';
import { Type } from 'class-transformer';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class BulkItineraryItemDto {
  @ApiProperty({ description: 'Thứ tự hoạt động trong ngày', example: 1 })
  @IsInt()
  @Min(1)
  orderIndex: number;

  @ApiProperty({ description: 'Tên hoạt động hoặc địa điểm', example: 'Ăn sáng mì Quảng Bếp Trang' })
  @IsString()
  @IsNotEmpty({ message: 'Tên hoạt động không được để trống' })
  activity: string;

  @ApiPropertyOptional({ description: 'Giờ bắt đầu', example: '07:30' })
  @IsOptional()
  @IsString()
  startTime?: string;

  @ApiPropertyOptional({ description: 'Giờ kết thúc', example: '09:00' })
  @IsOptional()
  @IsString()
  endTime?: string;

  @ApiPropertyOptional({ description: 'Place UUID nếu liên kết với địa điểm trong DB' })
  @IsOptional()
  @IsString()
  placeId?: string;

  @ApiPropertyOptional({ description: 'Ghi chú hoặc lời khuyên', example: 'Nên đặt bàn trước' })
  @IsOptional()
  @IsString()
  notes?: string;

  @ApiPropertyOptional({ description: 'Chi phí ước tính VND', example: 50000 })
  @IsOptional()
  @IsInt()
  @Min(0)
  estimatedCost?: number;

  @ApiPropertyOptional({ description: 'Phương tiện di chuyển', example: 'motorbike' })
  @IsOptional()
  @IsString()
  transportMode?: string;
}

export class BulkItineraryDayDto {
  @ApiProperty({ description: 'Số thứ tự ngày (1, 2, ...)', example: 1 })
  @IsInt()
  @Min(1)
  dayNumber: number;

  @ApiPropertyOptional({ description: 'Ngày cụ thể dạng YYYY-MM-DD', example: '2026-10-15' })
  @IsOptional()
  @IsDateString({}, { message: 'Định dạng ngày không hợp lệ (YYYY-MM-DD)' })
  date?: string;

  @ApiPropertyOptional({ description: 'Tiêu đề ngày', example: 'Ngày 1: Biển Mỹ Khê & Bán đảo Sơn Trà' })
  @IsOptional()
  @IsString()
  title?: string;

  @ApiProperty({ description: 'Danh sách các hoạt động trong ngày', type: [BulkItineraryItemDto] })
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => BulkItineraryItemDto)
  items: BulkItineraryItemDto[];
}

export class BulkItineraryDto {
  @ApiPropertyOptional({
    description: 'Xóa toàn bộ lịch trình cũ trước khi lưu mới (mặc định true)',
    default: true,
  })
  @IsOptional()
  @IsBoolean()
  replaceExisting?: boolean = true;

  @ApiProperty({ description: 'Danh sách các ngày và hoạt động', type: [BulkItineraryDayDto] })
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => BulkItineraryDayDto)
  days: BulkItineraryDayDto[];
}
