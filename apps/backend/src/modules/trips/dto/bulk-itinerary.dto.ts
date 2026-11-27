import {
  IsString,
  IsNotEmpty,
  IsOptional,
  IsInt,
  Min,
  Max,
  MaxLength,
  IsArray,
  ArrayMinSize,
  ArrayMaxSize,
  ValidateNested,
  IsBoolean,
  IsDateString,
  IsUUID,
} from 'class-validator';
import { Transform, Type } from 'class-transformer';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

const trimString = ({ value }: { value: unknown }) =>
  typeof value === 'string' ? value.trim() : value;

export class BulkItineraryItemDto {
  @ApiProperty({ description: 'Thứ tự hoạt động trong ngày', example: 1 })
  @IsInt()
  @Min(1)
  @Max(200)
  orderIndex: number;

  @ApiProperty({ description: 'Tên hoạt động hoặc địa điểm', example: 'Ăn sáng mì Quảng Bếp Trang' })
  @Transform(trimString)
  @IsString()
  @IsNotEmpty({ message: 'Tên hoạt động không được để trống' })
  @MaxLength(300, { message: 'Tên hoạt động tối đa 300 ký tự' })
  activity: string;

  @ApiPropertyOptional({ description: 'Giờ bắt đầu', example: '07:30' })
  @IsOptional()
  @Transform(trimString)
  @IsString()
  @MaxLength(20)
  startTime?: string;

  @ApiPropertyOptional({ description: 'Giờ kết thúc', example: '09:00' })
  @IsOptional()
  @Transform(trimString)
  @IsString()
  @MaxLength(20)
  endTime?: string;

  @ApiPropertyOptional({ description: 'Place UUID nếu liên kết với địa điểm trong DB' })
  @IsOptional()
  @IsUUID('all', { message: 'placeId phải là UUID hợp lệ' })
  placeId?: string;

  @ApiPropertyOptional({ description: 'Ghi chú hoặc lời khuyên', example: 'Nên đặt bàn trước' })
  @IsOptional()
  @Transform(trimString)
  @IsString()
  @MaxLength(2000, { message: 'Ghi chú tối đa 2000 ký tự' })
  notes?: string;

  @ApiPropertyOptional({ description: 'Chi phí ước tính VND (null nếu chưa biết)', example: 50000, nullable: true })
  @IsOptional()
  @IsInt()
  @Min(0)
  @Max(2147483647)
  estimatedCost?: number | null;

  @ApiPropertyOptional({ description: 'Phương tiện di chuyển', example: 'motorbike' })
  @IsOptional()
  @Transform(trimString)
  @IsString()
  @MaxLength(50)
  transportMode?: string;
}

export class BulkItineraryDayDto {
  @ApiProperty({ description: 'Số thứ tự ngày (1, 2, ...)', example: 1 })
  @IsInt()
  @Min(1)
  @Max(60)
  dayNumber: number;

  @ApiPropertyOptional({ description: 'Ngày cụ thể dạng YYYY-MM-DD', example: '2026-10-15' })
  @IsOptional()
  @IsDateString({}, { message: 'Định dạng ngày không hợp lệ (YYYY-MM-DD)' })
  date?: string;

  @ApiPropertyOptional({ description: 'Tiêu đề ngày', example: 'Ngày 1: Biển Mỹ Khê & Bán đảo Sơn Trà' })
  @IsOptional()
  @Transform(trimString)
  @IsString()
  @MaxLength(200)
  title?: string;

  @ApiProperty({ description: 'Danh sách các hoạt động trong ngày', type: [BulkItineraryItemDto] })
  @IsArray()
  @ArrayMaxSize(100, { message: 'Mỗi ngày tối đa 100 hoạt động' })
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
  @ArrayMinSize(1, { message: 'Danh sách ngày lịch trình không được để trống' })
  @ArrayMaxSize(30, { message: 'Lịch trình tối đa 30 ngày' })
  @ValidateNested({ each: true })
  @Type(() => BulkItineraryDayDto)
  days: BulkItineraryDayDto[];
}
