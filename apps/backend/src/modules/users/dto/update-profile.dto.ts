import { ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsNotEmpty, IsOptional, IsString, MaxLength } from 'class-validator';

const trimString = ({ value }: { value: unknown }) =>
  typeof value === 'string' ? value.trim() : value;

export class UpdateProfileDto {
  @ApiPropertyOptional({ description: 'Tên hiển thị', example: 'Nguyễn Văn A' })
  @IsOptional()
  @Transform(trimString)
  @IsString({ message: 'displayName phải là chuỗi' })
  @IsNotEmpty({ message: 'displayName không được để trống' })
  @MaxLength(120, { message: 'displayName tối đa 120 ký tự' })
  displayName?: string;

  @ApiPropertyOptional({ description: 'Giới thiệu bản thân', example: 'Yêu thích du lịch Hạ Long' })
  @IsOptional()
  @Transform(trimString)
  @IsString({ message: 'bio phải là chuỗi' })
  @MaxLength(500, { message: 'bio tối đa 500 ký tự' })
  bio?: string;

  @ApiPropertyOptional({ description: 'URL ảnh đại diện' })
  @IsOptional()
  @Transform(trimString)
  @IsString({ message: 'avatar phải là chuỗi' })
  @MaxLength(1000, { message: 'avatar tối đa 1000 ký tự' })
  avatar?: string;
}
