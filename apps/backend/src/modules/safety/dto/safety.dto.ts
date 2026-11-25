import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { EmergencyStatus } from '@prisma/client';
import { Transform } from 'class-transformer';
import {
  IsBoolean,
  IsEnum,
  IsIn,
  IsNotEmpty,
  IsNumber,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
} from 'class-validator';

export const ALLOWED_SAFETY_CONTACT_RELATIONS = [
  'family',
  'friend',
  'colleague',
  'embassy',
  'other',
] as const;

export class CreateSafetyContactDto {
  @ApiProperty({ description: 'Tên người liên hệ tin cậy', example: 'Nguyễn Văn A' })
  @Transform(({ value }) => (typeof value === 'string' ? value.trim() : value))
  @IsString()
  @IsNotEmpty({ message: 'Tên người liên hệ không được để trống' })
  @MaxLength(100, { message: 'Tên người liên hệ tối đa 100 ký tự' })
  name!: string;

  @ApiProperty({ description: 'Số điện thoại liên hệ', example: '0901234567' })
  @Transform(({ value }) => (typeof value === 'string' ? value.trim() : value))
  @IsString()
  @IsNotEmpty({ message: 'Số điện thoại không được để trống' })
  @MaxLength(30, { message: 'Số điện thoại tối đa 30 ký tự' })
  phone!: string;

  @ApiProperty({
    description: 'Mối quan hệ',
    enum: ALLOWED_SAFETY_CONTACT_RELATIONS,
    example: 'family',
  })
  @Transform(({ value }) =>
    typeof value === 'string' ? value.trim().toLowerCase() : value,
  )
  @IsString()
  @IsIn(ALLOWED_SAFETY_CONTACT_RELATIONS, {
    message: 'Mối quan hệ phải thuộc: family, friend, colleague, embassy, other',
  })
  relation!: string;
}

export class CreateSafetyCheckinDto {
  @ApiProperty({ description: 'Vĩ độ GPS', example: 20.9516105 })
  @IsNumber({}, { message: 'latitude phải là số hợp lệ' })
  @Min(-90, { message: 'latitude phải >= -90' })
  @Max(90, { message: 'latitude phải <= 90' })
  latitude!: number;

  @ApiProperty({ description: 'Kinh độ GPS', example: 107.0851999 })
  @IsNumber({}, { message: 'longitude phải là số hợp lệ' })
  @Min(-180, { message: 'longitude phải >= -180' })
  @Max(180, { message: 'longitude phải <= 180' })
  longitude!: number;

  @ApiPropertyOptional({ description: 'Ghi chú check-in an toàn' })
  @IsOptional()
  @Transform(({ value }) => (typeof value === 'string' ? value.trim() : value))
  @IsString()
  @MaxLength(500, { message: 'Ghi chú tối đa 500 ký tự' })
  note?: string;
}

export class CreateEmergencyEventDto {
  @ApiProperty({ description: 'Vĩ độ GPS', example: 20.9516105 })
  @IsNumber({}, { message: 'latitude phải là số hợp lệ' })
  @Min(-90, { message: 'latitude phải >= -90' })
  @Max(90, { message: 'latitude phải <= 90' })
  latitude!: number;

  @ApiProperty({ description: 'Kinh độ GPS', example: 107.0851999 })
  @IsNumber({}, { message: 'longitude phải là số hợp lệ' })
  @Min(-180, { message: 'longitude phải >= -180' })
  @Max(180, { message: 'longitude phải <= 180' })
  longitude!: number;

  @ApiPropertyOptional({ description: 'Nội dung cảnh báo / ngữ cảnh sự kiện' })
  @IsOptional()
  @Transform(({ value }) => (typeof value === 'string' ? value.trim() : value))
  @IsString()
  @MaxLength(500, { message: 'Thông điệp tối đa 500 ký tự' })
  message?: string;

  @ApiPropertyOptional({
    description: 'Trạng thái sự kiện khẩn cấp',
    enum: EmergencyStatus,
  })
  @IsOptional()
  @IsEnum(EmergencyStatus, { message: 'Trạng thái khẩn cấp không hợp lệ' })
  status?: EmergencyStatus;

  @ApiPropertyOptional({
    description: 'Đánh dấu sự kiện kiểm thử an toàn (Sandbox)',
    default: false,
  })
  @IsOptional()
  @IsBoolean({ message: 'isSandbox phải là boolean' })
  isSandbox?: boolean;
}
