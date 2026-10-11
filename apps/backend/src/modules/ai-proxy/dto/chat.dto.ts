import { IsNotEmpty, IsOptional, IsString } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class ChatDto {
  @ApiProperty({ description: 'Nội dung tin nhắn', example: 'Xin chào Wandy' })
  @IsString()
  @IsNotEmpty()
  message: string;

  @ApiPropertyOptional({ description: 'ID phiên chat', example: 'ef94af53-3d73-4dc8-b9dc-101f95dd90af' })
  @IsOptional()
  @IsString()
  session_id?: string;
}
