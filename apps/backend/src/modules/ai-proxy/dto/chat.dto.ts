import { IsNotEmpty, IsOptional, IsString, MaxLength } from 'class-validator';
import { Transform } from 'class-transformer';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class ChatDto {
  @ApiProperty({ description: 'Nội dung tin nhắn', example: 'Xin chào Wandy' })
  @Transform(({ value }) => (typeof value === 'string' ? value.trim() : value))
  @IsString({ message: 'message phải là chuỗi' })
  @IsNotEmpty({ message: 'message không được để trống' })
  @MaxLength(4000, { message: 'message tối đa 4000 ký tự' })
  message!: string;

  @ApiPropertyOptional({ description: 'ID phiên chat', example: 'ef94af53-3d73-4dc8-b9dc-101f95dd90af' })
  @IsOptional()
  @Transform(({ value }) => {
    if (typeof value !== 'string') return value;
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  })
  @IsString({ message: 'session_id phải là chuỗi' })
  @MaxLength(128, { message: 'session_id tối đa 128 ký tự' })
  session_id?: string;
}
