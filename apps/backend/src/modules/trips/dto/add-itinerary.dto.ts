import {
  IsString,
  IsNotEmpty,
  IsOptional,
  IsUUID,
  IsInt,
  Min,
} from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class AddItineraryDto {
  @ApiProperty({ description: 'Ngày thứ mấy của chuyến đi (bắt đầu từ 1)', example: 1 })
  @IsInt({ message: 'dayNumber phải là số nguyên' })
  @Min(1, { message: 'dayNumber phải lớn hơn hoặc bằng 1' })
  dayNumber: number;

  @ApiProperty({ description: 'Hoạt động cụ thể', example: 'Khám phá Đèo Mã Pí Lèng' })
  @IsString()
  @IsNotEmpty({ message: 'Hoạt động không được để trống' })
  activity: string;

  @ApiPropertyOptional({ description: 'Giờ bắt đầu', example: '08:30' })
  @IsOptional()
  @IsString()
  startTime?: string;

  @ApiPropertyOptional({ description: 'Giờ kết thúc', example: '11:00' })
  @IsOptional()
  @IsString()
  endTime?: string;

  @ApiPropertyOptional({ description: 'ID địa điểm tham quan' })
  @IsOptional()
  @IsUUID('all', { message: 'placeId phải là UUID hợp lệ' })
  placeId?: string;

  @ApiPropertyOptional({ description: 'Ghi chú cho hoạt động' })
  @IsOptional()
  @IsString()
  notes?: string;

  @ApiPropertyOptional({ description: 'Chi phí ước tính (VND)', example: 250000 })
  @IsOptional()
  @IsInt({ message: 'estimatedCost phải là số nguyên' })
  @Min(0, { message: 'Chi phí không được nhỏ hơn 0' })
  estimatedCost?: number;

  @ApiPropertyOptional({ description: 'Phương tiện di chuyển', example: 'motorbike' })
  @IsOptional()
  @IsString()
  transportMode?: string;
}
