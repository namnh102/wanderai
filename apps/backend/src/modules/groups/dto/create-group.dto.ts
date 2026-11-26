import { Transform } from 'class-transformer';
import { IsNotEmpty, IsOptional, IsString, IsUUID, MaxLength } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

function trimString(value: unknown): unknown {
  return typeof value === 'string' ? value.trim() : value;
}

function blankToUndefinedAndTrim(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  return trimmed.length === 0 ? undefined : trimmed;
}

export class CreateGroupDto {
  @ApiProperty({ description: 'Tên nhóm đồng hành', example: 'Nhóm Hạ Long 2N1Đ' })
  @Transform(({ value }) => trimString(value))
  @IsString({ message: 'Tên nhóm phải là chuỗi' })
  @IsNotEmpty({ message: 'Tên nhóm không được để trống' })
  @MaxLength(120, { message: 'Tên nhóm tối đa 120 ký tự' })
  name!: string;

  @ApiPropertyOptional({ description: 'Mô tả nhóm đồng hành' })
  @IsOptional()
  @Transform(({ value }) => blankToUndefinedAndTrim(value))
  @IsString({ message: 'Mô tả nhóm phải là chuỗi' })
  @MaxLength(1000, { message: 'Mô tả nhóm tối đa 1000 ký tự' })
  description?: string;

  @ApiPropertyOptional({ description: 'ID chuyến đi liên kết (tùy chọn)' })
  @IsOptional()
  @Transform(({ value }) => blankToUndefinedAndTrim(value))
  @IsUUID('all', { message: 'tripId phải là UUID hợp lệ' })
  tripId?: string;
}
