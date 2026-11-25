import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import {
  ArrayMaxSize,
  IsArray,
  IsInt,
  IsNotEmpty,
  IsNumber,
  IsOptional,
  IsString,
  IsUUID,
  Max,
  MaxLength,
  Min,
} from 'class-validator';

const isBlank = (v: unknown) =>
  v === undefined || v === null || (typeof v === 'string' && v.trim() === '');

const toStrictInt = (def: number) => ({ value }: { value: unknown }) => {
  if (isBlank(value)) return def;
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && /^[+-]?\d+$/.test(value.trim())) {
    return Number(value.trim());
  }
  return value;
};

const trimString = ({ value }: { value: unknown }) =>
  typeof value === 'string' ? value.trim() : value;

export class CreateReviewDto {
  @ApiProperty({ description: 'UUID địa điểm' })
  @IsUUID('all', { message: 'placeId phải là UUID hợp lệ' })
  placeId: string;

  @ApiProperty({ description: 'Điểm đánh giá (1-5)', example: 5 })
  @IsNumber({ allowNaN: false, allowInfinity: false })
  @Min(1)
  @Max(5)
  rating: number;

  @ApiProperty({ description: 'Nội dung đánh giá' })
  @Transform(trimString)
  @IsString()
  @IsNotEmpty({ message: 'Nội dung đánh giá không được để trống' })
  @MaxLength(2000, { message: 'Nội dung đánh giá tối đa 2000 ký tự' })
  content: string;

  @ApiPropertyOptional({ description: 'Ngày tham quan (YYYY-MM-DD)' })
  @IsOptional()
  @Transform(trimString)
  @IsString()
  @MaxLength(40)
  visitDate?: string;

  @ApiPropertyOptional({ description: 'Danh sách URL ảnh', type: [String] })
  @IsOptional()
  @IsArray()
  @ArrayMaxSize(10)
  @IsString({ each: true })
  @MaxLength(1000, { each: true })
  images?: string[];
}

export class ReviewListQueryDto {
  @ApiProperty({ description: 'UUID của Place' })
  @IsUUID('all', { message: 'placeId phải là UUID hợp lệ' })
  placeId: string;

  @ApiPropertyOptional({ default: 1, minimum: 1 })
  @Transform(toStrictInt(1))
  @IsInt({ message: 'page phải là số nguyên từ 1 trở lên' })
  @Min(1, { message: 'page phải là số nguyên từ 1 trở lên' })
  page: number = 1;

  @ApiPropertyOptional({ default: 20, minimum: 1, maximum: 100 })
  @Transform(toStrictInt(20))
  @IsInt({ message: 'limit phải là số nguyên từ 1 đến 100' })
  @Min(1, { message: 'limit phải là số nguyên từ 1 đến 100' })
  @Max(100, { message: 'limit phải là số nguyên từ 1 đến 100' })
  limit: number = 20;
}

export class ReviewMyQueryDto {
  @ApiPropertyOptional({ default: 1, minimum: 1 })
  @Transform(toStrictInt(1))
  @IsInt({ message: 'page phải là số nguyên từ 1 trở lên' })
  @Min(1, { message: 'page phải là số nguyên từ 1 trở lên' })
  page: number = 1;

  @ApiPropertyOptional({ default: 20, minimum: 1, maximum: 100 })
  @Transform(toStrictInt(20))
  @IsInt({ message: 'limit phải là số nguyên từ 1 đến 100' })
  @Min(1, { message: 'limit phải là số nguyên từ 1 đến 100' })
  @Max(100, { message: 'limit phải là số nguyên từ 1 đến 100' })
  limit: number = 20;
}
