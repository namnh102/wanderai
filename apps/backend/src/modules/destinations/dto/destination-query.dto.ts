import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsIn, IsInt, IsNumber, IsOptional, IsString, Max, MaxLength, Min } from 'class-validator';

export const DESTINATION_LIST_LIMIT_DEFAULT = 20;
export const DESTINATION_LIST_LIMIT_MAX = 100;
export const DESTINATION_NEARBY_RADIUS_DEFAULT = 50;

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

const toStrictNumber = (def: number | undefined) => ({ value }: { value: unknown }) => {
  if (isBlank(value)) return def;
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && /^[+-]?(\d+\.?\d*|\.\d+)$/.test(value.trim())) {
    return Number(value.trim());
  }
  return value;
};

const blankToUndefined = ({ value }: { value: unknown }) =>
  isBlank(value) ? undefined : typeof value === 'string' ? value.trim() : value;

export class DestinationListQueryDto {
  @ApiPropertyOptional({ example: 1, default: 1, minimum: 1 })
  @Transform(toStrictInt(1))
  @IsInt({ message: 'page phải là số nguyên từ 1 trở lên' })
  @Min(1, { message: 'page phải là số nguyên từ 1 trở lên' })
  page: number = 1;

  @ApiPropertyOptional({ example: 20, default: DESTINATION_LIST_LIMIT_DEFAULT, minimum: 1, maximum: DESTINATION_LIST_LIMIT_MAX })
  @Transform(toStrictInt(DESTINATION_LIST_LIMIT_DEFAULT))
  @IsInt({ message: 'limit phải là số nguyên từ 1 đến 100' })
  @Min(1, { message: 'limit phải là số nguyên từ 1 đến 100' })
  @Max(DESTINATION_LIST_LIMIT_MAX, { message: 'limit phải là số nguyên từ 1 đến 100' })
  limit: number = DESTINATION_LIST_LIMIT_DEFAULT;

  @ApiPropertyOptional({ example: 'đà nẵng' })
  @IsOptional()
  @Transform(blankToUndefined)
  @IsString({ message: 'search phải là chuỗi' })
  @MaxLength(200, { message: 'search tối đa 200 ký tự' })
  search?: string;

  @ApiPropertyOptional({ enum: ['north', 'central', 'south'] })
  @IsOptional()
  @Transform(blankToUndefined)
  @IsIn(['north', 'central', 'south'], { message: 'region phải là north, central hoặc south' })
  region?: string;
}

export class DestinationPopularQueryDto {
  @ApiPropertyOptional({ example: 10, default: 10, minimum: 1, maximum: 50 })
  @Transform(toStrictInt(10))
  @IsInt({ message: 'limit phải là số nguyên từ 1 đến 50' })
  @Min(1, { message: 'limit phải là số nguyên từ 1 đến 50' })
  @Max(50, { message: 'limit phải là số nguyên từ 1 đến 50' })
  limit: number = 10;
}

export class DestinationNearbyQueryDto {
  @ApiProperty({ example: 16.0544, minimum: -90, maximum: 90 })
  @Transform(toStrictNumber(undefined))
  @IsNumber({ allowNaN: false, allowInfinity: false }, { message: 'lat là bắt buộc và phải là số trong khoảng -90 đến 90' })
  @Min(-90, { message: 'lat là bắt buộc và phải là số trong khoảng -90 đến 90' })
  @Max(90, { message: 'lat là bắt buộc và phải là số trong khoảng -90 đến 90' })
  lat!: number;

  @ApiProperty({ example: 108.2022, minimum: -180, maximum: 180 })
  @Transform(toStrictNumber(undefined))
  @IsNumber({ allowNaN: false, allowInfinity: false }, { message: 'lng là bắt buộc và phải là số trong khoảng -180 đến 180' })
  @Min(-180, { message: 'lng là bắt buộc và phải là số trong khoảng -180 đến 180' })
  @Max(180, { message: 'lng là bắt buộc và phải là số trong khoảng -180 đến 180' })
  lng!: number;

  @ApiPropertyOptional({ example: 50, default: DESTINATION_NEARBY_RADIUS_DEFAULT, description: 'Bán kính (km), > 0' })
  @Transform(toStrictNumber(DESTINATION_NEARBY_RADIUS_DEFAULT))
  @IsNumber({ allowNaN: false, allowInfinity: false }, { message: 'radius phải là số dương (km)' })
  @Min(0.001, { message: 'radius phải là số dương (km)' })
  @Max(1000, { message: 'radius tối đa 1000 km' })
  radius: number = DESTINATION_NEARBY_RADIUS_DEFAULT;
}
