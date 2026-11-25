import {
  ArrayMaxSize,
  IsEnum,
  IsInt,
  IsNotEmpty,
  IsOptional,
  Max,
  MaxLength,
  Min,
  IsArray,
  IsString,
  IsIn,
} from 'class-validator';
import { Transform } from 'class-transformer';
import { ApiPropertyOptional } from '@nestjs/swagger';
import { TravelStyle, GroupSize } from '@prisma/client';

export const CANONICAL_INTERESTS = [
  'food_cuisine',
  'culture_history',
  'nature_outdoor',
  'coffee_culture',
  'beach_island',
  'shopping_local',
  'nightlife_entertainment',
] as const;

export type CanonicalInterest = (typeof CANONICAL_INTERESTS)[number];

const transformStringArray = ({ value }: { value: unknown }) =>
  Array.isArray(value)
    ? value.map((v) => (typeof v === 'string' ? v.trim() : v))
    : value;

export class UpdatePreferencesDto {
  @ApiPropertyOptional({
    description: 'Phong cách du lịch',
    enum: TravelStyle,
    example: TravelStyle.COMFORT,
  })
  @IsOptional()
  @IsEnum(TravelStyle, {
    message: 'travelStyle phải là một trong: BACKPACKER, BUDGET, COMFORT, LUXURY',
  })
  travelStyle?: TravelStyle;

  @ApiPropertyOptional({
    description: 'Ngân sách tối thiểu (VND)',
    example: 1000000,
  })
  @IsOptional()
  @IsInt({ message: 'budgetMin phải là số nguyên' })
  @Min(0, { message: 'budgetMin không được nhỏ hơn 0' })
  @Max(2147483647, { message: 'budgetMin vượt quá giới hạn cho phép' })
  budgetMin?: number;

  @ApiPropertyOptional({
    description: 'Ngân sách tối đa (VND)',
    example: 15000000,
  })
  @IsOptional()
  @IsInt({ message: 'budgetMax phải là số nguyên' })
  @Min(0, { message: 'budgetMax không được nhỏ hơn 0' })
  @Max(2147483647, { message: 'budgetMax vượt quá giới hạn cho phép' })
  budgetMax?: number;

  @ApiPropertyOptional({
    description: 'Quy mô nhóm ưu tiên',
    enum: GroupSize,
    example: GroupSize.SOLO,
  })
  @IsOptional()
  @IsEnum(GroupSize, {
    message: 'preferredGroup phải là một trong: SOLO, COUPLE, SMALL_GROUP, LARGE_GROUP, FAMILY',
  })
  preferredGroup?: GroupSize;

  @ApiPropertyOptional({
    description: 'Danh sách sở thích du lịch chuẩn hóa',
    example: ['food_cuisine', 'culture_history'],
  })
  @IsOptional()
  @Transform(transformStringArray)
  @IsArray({ message: 'interests phải là mảng chuỗi' })
  @ArrayMaxSize(20, { message: 'interests tối đa 20 mục' })
  @IsString({ each: true, message: 'Mỗi phần tử interests phải là chuỗi' })
  @IsNotEmpty({ each: true, message: 'Mỗi phần tử interests không được để trống' })
  @MaxLength(100, { each: true, message: 'Mỗi phần tử interests tối đa 100 ký tự' })
  @IsIn(CANONICAL_INTERESTS, {
    each: true,
    message: `Sở thích không hợp lệ. Các giá trị được chấp nhận: ${CANONICAL_INTERESTS.join(', ')}`,
  })
  interests?: string[];

  @ApiPropertyOptional({
    description: 'Những điều cần tránh khi du lịch',
    example: ['crowds', 'heights'],
  })
  @IsOptional()
  @Transform(transformStringArray)
  @IsArray({ message: 'avoidances phải là mảng chuỗi' })
  @ArrayMaxSize(30, { message: 'avoidances tối đa 30 mục' })
  @IsString({ each: true, message: 'Mỗi phần tử avoidances phải là chuỗi' })
  @IsNotEmpty({ each: true, message: 'Mỗi phần tử avoidances không được để trống' })
  @MaxLength(100, { each: true, message: 'Mỗi phần tử avoidances tối đa 100 ký tự' })
  avoidances?: string[];

  @ApiPropertyOptional({
    description: 'Nhu cầu ăn uống đặc biệt',
    example: ['vegetarian', 'halal'],
  })
  @IsOptional()
  @Transform(transformStringArray)
  @IsArray({ message: 'dietaryNeeds phải là mảng chuỗi' })
  @ArrayMaxSize(30, { message: 'dietaryNeeds tối đa 30 mục' })
  @IsString({ each: true, message: 'Mỗi phần tử dietaryNeeds phải là chuỗi' })
  @IsNotEmpty({ each: true, message: 'Mỗi phần tử dietaryNeeds không được để trống' })
  @MaxLength(100, { each: true, message: 'Mỗi phần tử dietaryNeeds tối đa 100 ký tự' })
  dietaryNeeds?: string[];
}

