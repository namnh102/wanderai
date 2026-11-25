import {
  IsString,
  IsNotEmpty,
  IsOptional,
  IsUUID,
  IsInt,
  Min,
  Max,
  MaxLength,
} from 'class-validator';
import { Transform } from 'class-transformer';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class AddItineraryDto {
  @ApiProperty({ description: 'Ngày thứ mấy của chuyến đi (bắt đầu từ 1)', example: 1 })
  @IsInt({ message: 'dayNumber phải là số nguyên' })
  @Min(1, { message: 'dayNumber phải lớn hơn hoặc bằng 1' })
  @Max(60, { message: 'dayNumber tối đa 60' })
  dayNumber: number;

  @ApiProperty({ description: 'Hoạt động cụ thể', example: 'Khám phá Đèo Mã Pí Lèng' })
  @Transform(({ value }) => (typeof value === 'string' ? value.trim() : value))
  @IsString()
  @IsNotEmpty({ message: 'Hoạt động không được để trống' })
  @MaxLength(300, { message: 'Hoạt động tối đa 300 ký tự' })
  activity: string;

  @ApiPropertyOptional({ description: 'Giờ bắt đầu', example: '08:30' })
  @IsOptional()
  @IsString()
  @MaxLength(20)
  startTime?: string;

  @ApiPropertyOptional({ description: 'Giờ kết thúc', example: '11:00' })
  @IsOptional()
  @IsString()
  @MaxLength(20)
  endTime?: string;

  @ApiPropertyOptional({ description: 'ID địa điểm tham quan' })
  @IsOptional()
  @IsUUID('all', { message: 'placeId phải là UUID hợp lệ' })
  placeId?: string;

  @ApiPropertyOptional({ description: 'Ghi chú cho hoạt động' })
  @IsOptional()
  @IsString()
  @MaxLength(2000, { message: 'Ghi chú tối đa 2000 ký tự' })
  notes?: string;

  @ApiPropertyOptional({ description: 'Chi phí ước tính (VND)', example: 250000 })
  @IsOptional()
  @IsInt({ message: 'estimatedCost phải là số nguyên' })
  @Min(0, { message: 'Chi phí không được nhỏ hơn 0' })
  estimatedCost?: number;

  @ApiPropertyOptional({ description: 'Phương tiện di chuyển', example: 'motorbike' })
  @IsOptional()
  @IsString()
  @MaxLength(50)
  transportMode?: string;

  @ApiPropertyOptional({
    description: 'Khóa idempotency cho yêu cầu thêm hoạt động (chống trùng khi retry)',
  })
  @IsOptional()
  @Transform(({ value }) => {
    if (typeof value !== 'string') return value;
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  })
  @IsString()
  @MaxLength(128)
  clientRequestId?: string;
}
