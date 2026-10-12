import { Transform } from 'class-transformer';
import { IsBoolean, IsInt, IsNumber, IsOptional, IsString, IsUUID, Max, Min } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export const PLACE_LIST_LIMIT_DEFAULT = 20;
export const PLACE_LIST_LIMIT_MAX = 100;
export const NEARBY_RADIUS_KM_DEFAULT = 10;

const isBlank = (v: unknown) => v === undefined || v === null || (typeof v === 'string' && v.trim() === '');

/** Strict integer text -> number. Anything else stays a string so @IsInt rejects it (never NaN). */
const toStrictInt = (def: number) => ({ value }: { value: unknown }) => {
  if (isBlank(value)) return def;
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && /^[+-]?\d+$/.test(value.trim())) return Number(value.trim());
  return value;
};

/** Strict decimal text -> number. Anything else stays a string so @IsNumber rejects it (never NaN). */
const toStrictNumber = (def: number | undefined) => ({ value }: { value: unknown }) => {
  if (isBlank(value)) return def;
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && /^[+-]?(\d+\.?\d*|\.\d+)$/.test(value.trim())) return Number(value.trim());
  return value;
};

/** 'true' | 'false' only (case-insensitive); default true. Anything else fails @IsBoolean. */
const toStrictBoolean = ({ value }: { value: unknown }) => {
  if (isBlank(value)) return true;
  if (typeof value === 'boolean') return value;
  if (typeof value === 'string') {
    const v = value.trim().toLowerCase();
    if (v === 'true') return true;
    if (v === 'false') return false;
  }
  return value;
};

const blankToUndefined = ({ value }: { value: unknown }) => (isBlank(value) ? undefined : value);

export class PlaceListQueryDto {
  @ApiPropertyOptional({ example: 1, default: 1, minimum: 1 })
  @Transform(toStrictInt(1))
  @IsInt({ message: 'page phải là số nguyên từ 1 trở lên' })
  @Min(1, { message: 'page phải là số nguyên từ 1 trở lên' })
  page: number = 1;

  @ApiPropertyOptional({ example: 20, default: PLACE_LIST_LIMIT_DEFAULT, minimum: 1, maximum: PLACE_LIST_LIMIT_MAX })
  @Transform(toStrictInt(PLACE_LIST_LIMIT_DEFAULT))
  @IsInt({ message: 'limit phải là số nguyên từ 1 đến 100' })
  @Min(1, { message: 'limit phải là số nguyên từ 1 đến 100' })
  @Max(PLACE_LIST_LIMIT_MAX, { message: 'limit phải là số nguyên từ 1 đến 100' })
  limit: number = PLACE_LIST_LIMIT_DEFAULT;

  @ApiPropertyOptional({ example: 'Cầu Rồng' })
  @IsOptional()
  @Transform(blankToUndefined)
  @IsString({ message: 'search phải là chuỗi' })
  search?: string;

  @ApiPropertyOptional({ example: 'attraction' })
  @IsOptional()
  @Transform(blankToUndefined)
  @IsString({ message: 'category phải là chuỗi' })
  category?: string;

  @ApiPropertyOptional({ description: 'UUID của điểm đến' })
  @IsOptional()
  @Transform(blankToUndefined)
  @IsUUID('all', { message: 'destinationId phải là UUID hợp lệ' })
  destinationId?: string;

  @ApiPropertyOptional({
    example: true,
    default: true,
    description: 'Mặc định true: chỉ địa điểm đã kiểm chứng provenance. Chấp nhận true | false.',
  })
  @Transform(toStrictBoolean)
  @IsBoolean({ message: 'verifiedOnly phải là true hoặc false' })
  verifiedOnly: boolean = true;
}

export class NearbyQueryDto {
  @ApiProperty({ example: 16.0612, minimum: -90, maximum: 90 })
  @Transform(toStrictNumber(undefined))
  @IsNumber({ allowNaN: false, allowInfinity: false }, { message: 'lat là bắt buộc và phải là số trong khoảng -90 đến 90' })
  @Min(-90, { message: 'lat là bắt buộc và phải là số trong khoảng -90 đến 90' })
  @Max(90, { message: 'lat là bắt buộc và phải là số trong khoảng -90 đến 90' })
  lat!: number;

  @ApiProperty({ example: 108.2272, minimum: -180, maximum: 180 })
  @Transform(toStrictNumber(undefined))
  @IsNumber({ allowNaN: false, allowInfinity: false }, { message: 'lng là bắt buộc và phải là số trong khoảng -180 đến 180' })
  @Min(-180, { message: 'lng là bắt buộc và phải là số trong khoảng -180 đến 180' })
  @Max(180, { message: 'lng là bắt buộc và phải là số trong khoảng -180 đến 180' })
  lng!: number;

  @ApiPropertyOptional({ example: 10, default: NEARBY_RADIUS_KM_DEFAULT, description: 'Bán kính (km), > 0' })
  @Transform(toStrictNumber(NEARBY_RADIUS_KM_DEFAULT))
  @IsNumber({ allowNaN: false, allowInfinity: false }, { message: 'radius phải là số dương (km)' })
  @Min(0.001, { message: 'radius phải là số dương (km)' })
  radius: number = NEARBY_RADIUS_KM_DEFAULT;

  @ApiPropertyOptional({ example: 20, default: PLACE_LIST_LIMIT_DEFAULT, minimum: 1, maximum: PLACE_LIST_LIMIT_MAX })
  @Transform(toStrictInt(PLACE_LIST_LIMIT_DEFAULT))
  @IsInt({ message: 'limit phải là số nguyên từ 1 đến 100' })
  @Min(1, { message: 'limit phải là số nguyên từ 1 đến 100' })
  @Max(PLACE_LIST_LIMIT_MAX, { message: 'limit phải là số nguyên từ 1 đến 100' })
  limit: number = PLACE_LIST_LIMIT_DEFAULT;

  @ApiPropertyOptional({ example: true, default: true, description: 'Mặc định true. Chấp nhận true | false.' })
  @Transform(toStrictBoolean)
  @IsBoolean({ message: 'verifiedOnly phải là true hoặc false' })
  verifiedOnly: boolean = true;
}
