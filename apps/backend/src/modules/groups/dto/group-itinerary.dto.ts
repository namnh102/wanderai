import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import {
  IsBoolean,
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  Max,
  MaxLength,
  Min,
} from 'class-validator';

export class ProposeGroupItineraryItemDto {
  @ApiProperty({ description: 'Ngày thứ mấy của chuyến đi (bắt đầu từ 1)', example: 1 })
  @IsInt({ message: 'dayNumber phải là số nguyên' })
  @Min(1, { message: 'dayNumber phải lớn hơn hoặc bằng 1' })
  @Max(60, { message: 'dayNumber tối đa 60' })
  dayNumber: number;

  @ApiProperty({ description: 'Hoạt động đề xuất', example: 'Tham quan Bảo tàng Quảng Ninh' })
  @Transform(({ value }: { value: unknown }) =>
    typeof value === 'string' ? value.trim() : value,
  )
  @IsString()
  @IsNotEmpty({ message: 'Hoạt động không được để trống' })
  @MaxLength(300, { message: 'Hoạt động tối đa 300 ký tự' })
  activity: string;

  @ApiPropertyOptional({ description: 'Giờ bắt đầu', example: '09:00' })
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
  @Transform(({ value }: { value: unknown }) => {
    if (typeof value !== 'string') return value;
    const trimmed = value.trim().toLowerCase();
    return trimmed.length > 0 ? trimmed : undefined;
  })
  @IsUUID('all', { message: 'placeId phải là UUID hợp lệ' })
  placeId?: string;

  @ApiPropertyOptional({ description: 'Ghi chú cho hoạt động' })
  @IsOptional()
  @IsString()
  @MaxLength(2000, { message: 'Ghi chú tối đa 2000 ký tự' })
  notes?: string;

  @ApiPropertyOptional({ description: 'Chi phí ước tính (VND)', example: 120000 })
  @IsOptional()
  @IsInt({ message: 'estimatedCost phải là số nguyên' })
  @Min(0, { message: 'Chi phí không được nhỏ hơn 0' })
  @Max(2147483647, { message: 'Chi phí vượt quá giới hạn cho phép' })
  estimatedCost?: number;

  @ApiPropertyOptional({ description: 'Phương tiện di chuyển', example: 'taxi' })
  @IsOptional()
  @IsString()
  @MaxLength(50)
  transportMode?: string;

  @ApiPropertyOptional({ description: 'Khóa idempotency chống tạo trùng khi retry' })
  @IsOptional()
  @Transform(({ value }: { value: unknown }) => {
    if (typeof value !== 'string') return value;
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  })
  @IsString()
  @MaxLength(128)
  clientRequestId?: string;
}

export class VoteItineraryItemDto {
  @ApiProperty({ description: 'true = tán thành (+1), false = không tán thành (-1)' })
  @IsBoolean({ message: 'vote phải là kiểu boolean (true hoặc false)' })
  vote: boolean;
}
