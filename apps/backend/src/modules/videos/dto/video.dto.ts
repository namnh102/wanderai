import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import {
  ArrayMaxSize,
  IsArray,
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUrl,
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

const trimStringArray = ({ value }: { value: unknown }) =>
  Array.isArray(value)
    ? value.map((v) => (typeof v === 'string' ? v.trim() : v))
    : value;

export class VideoFeedQueryDto {
  @ApiPropertyOptional({ example: 1, default: 1, minimum: 1, maximum: 10000 })
  @Transform(toStrictInt(1))
  @IsInt({ message: 'page phải là số nguyên từ 1 đến 10000' })
  @Min(1, { message: 'page phải là số nguyên từ 1 đến 10000' })
  @Max(10000, { message: 'page phải là số nguyên từ 1 đến 10000' })
  page: number = 1;

  @ApiPropertyOptional({ example: 20, default: 20, minimum: 1, maximum: 50 })
  @Transform(toStrictInt(20))
  @IsInt({ message: 'limit phải là số nguyên từ 1 đến 50' })
  @Min(1, { message: 'limit phải là số nguyên từ 1 đến 50' })
  @Max(50, { message: 'limit phải là số nguyên từ 1 đến 50' })
  limit: number = 20;
}

export class CreateVideoDto {
  @ApiProperty({
    description: 'URL video (http/https)',
    example: 'https://cdn.example.com/videos/halong.mp4',
  })
  @Transform(trimString)
  @IsString({ message: 'videoUrl phải là chuỗi' })
  @IsNotEmpty({ message: 'videoUrl không được để trống' })
  @IsUrl(
    { protocols: ['http', 'https'], require_protocol: true },
    { message: 'videoUrl phải là URL http/https hợp lệ' },
  )
  @MaxLength(1000, { message: 'videoUrl tối đa 1000 ký tự' })
  videoUrl!: string;

  @ApiPropertyOptional({ description: 'Tiêu đề video', example: 'Hoàng hôn Hạ Long' })
  @IsOptional()
  @Transform(trimString)
  @IsString({ message: 'title phải là chuỗi' })
  @IsNotEmpty({ message: 'title không được để trống' })
  @MaxLength(200, { message: 'title tối đa 200 ký tự' })
  title?: string;

  @ApiPropertyOptional({ description: 'Mô tả ngắn cho video' })
  @IsOptional()
  @Transform(trimString)
  @IsString({ message: 'caption phải là chuỗi' })
  @MaxLength(2000, { message: 'caption tối đa 2000 ký tự' })
  caption?: string;

  @ApiPropertyOptional({
    description: 'URL ảnh thumbnail (http/https)',
    example: 'https://cdn.example.com/thumbs/halong.jpg',
  })
  @IsOptional()
  @Transform(trimString)
  @IsString({ message: 'thumbnailUrl phải là chuỗi' })
  @IsUrl(
    { protocols: ['http', 'https'], require_protocol: true },
    { message: 'thumbnailUrl phải là URL http/https hợp lệ' },
  )
  @MaxLength(1000, { message: 'thumbnailUrl tối đa 1000 ký tự' })
  thumbnailUrl?: string;

  @ApiPropertyOptional({ description: 'Thời lượng video (giây)', example: 45 })
  @IsOptional()
  @IsInt({ message: 'duration phải là số nguyên' })
  @Min(1, { message: 'duration phải lớn hơn hoặc bằng 1' })
  @Max(86400, { message: 'duration tối đa 86400 giây' })
  duration?: number;

  @ApiPropertyOptional({ description: 'Danh sách thẻ (tags)', example: ['halong', 'travel'] })
  @IsOptional()
  @IsArray({ message: 'tags phải là mảng' })
  @ArrayMaxSize(20, { message: 'tags tối đa 20 mục' })
  @Transform(trimStringArray)
  @IsString({ each: true, message: 'Mỗi tag phải là chuỗi' })
  @IsNotEmpty({ each: true, message: 'Tag không được để trống' })
  @MaxLength(64, { each: true, message: 'Mỗi tag tối đa 64 ký tự' })
  tags?: string[];
}
