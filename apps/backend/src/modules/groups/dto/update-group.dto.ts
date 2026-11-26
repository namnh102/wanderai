import { Transform } from 'class-transformer';
import {
  IsNotEmpty,
  IsOptional,
  IsString,
  MaxLength,
  ValidateIf,
} from 'class-validator';
import { ApiPropertyOptional } from '@nestjs/swagger';

function trimString(value: unknown): unknown {
  return typeof value === 'string' ? value.trim() : value;
}

function trimOrNullIfEmpty(value: unknown): unknown {
  if (value === null) return null;
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  return trimmed.length === 0 ? null : trimmed;
}

export class UpdateGroupDto {
  @ApiPropertyOptional({ description: 'Tên nhóm đồng hành mới' })
  @ValidateIf((o) => o.name !== undefined)
  @Transform(({ value }) => trimString(value))
  @IsString({ message: 'Tên nhóm phải là chuỗi' })
  @IsNotEmpty({ message: 'Tên nhóm không được để trống' })
  @MaxLength(120, { message: 'Tên nhóm tối đa 120 ký tự' })
  name?: string;

  @ApiPropertyOptional({ description: 'Mô tả nhóm đồng hành mới', nullable: true })
  @IsOptional()
  @Transform(({ value }) => trimOrNullIfEmpty(value))
  @IsString({ message: 'Mô tả nhóm phải là chuỗi' })
  @MaxLength(1000, { message: 'Mô tả nhóm tối đa 1000 ký tự' })
  description?: string | null;
}
