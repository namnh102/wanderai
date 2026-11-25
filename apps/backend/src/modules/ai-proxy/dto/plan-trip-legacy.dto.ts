import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import {
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
} from 'class-validator';

export class PlanTripLegacyDto {
  @ApiProperty({ description: 'Điểm đến du lịch', example: 'Hạ Long' })
  @Transform(({ value }) => (typeof value === 'string' ? value.trim() : value))
  @IsString({ message: 'destination phải là chuỗi' })
  @IsNotEmpty({ message: 'destination không được để trống' })
  @MaxLength(200, { message: 'destination tối đa 200 ký tự' })
  destination!: string;

  @ApiProperty({ description: 'Số ngày chuyến đi (1-14)', example: 3 })
  @IsInt({ message: 'days phải là số nguyên' })
  @Min(1, { message: 'days phải từ 1 đến 14' })
  @Max(14, { message: 'days tối đa 14' })
  days!: number;

  @ApiPropertyOptional({ description: 'Ngân sách dự kiến (VND)', example: 5000000 })
  @IsOptional()
  @IsInt({ message: 'budget phải là số nguyên' })
  @Min(0, { message: 'budget không được nhỏ hơn 0' })
  @Max(2147483647, { message: 'budget vượt quá giới hạn cho phép' })
  budget?: number;
}
