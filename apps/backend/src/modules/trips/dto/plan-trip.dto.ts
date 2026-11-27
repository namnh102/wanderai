import {
  ArrayMaxSize,
  IsArray,
  IsInt,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
} from 'class-validator';
import { ApiPropertyOptional } from '@nestjs/swagger';

export class PlanTripDto {
  @ApiPropertyOptional({
    description: 'Yêu cầu hoặc ghi chú bổ sung cho Wandy AI',
    example: 'Tập trung quán ăn vặt, bãi biển và các điểm check-in đẹp',
  })
  @IsOptional()
  @IsString()
  @MaxLength(1500)
  additionalPrompt?: string;

  @ApiPropertyOptional({
    description: 'Nhịp độ chuyến đi (relaxed, moderate, fast)',
    example: 'relaxed',
  })
  @IsOptional()
  @IsString()
  @MaxLength(32)
  preferredPace?: string;

  @ApiPropertyOptional({ description: 'Số người tham gia từ yêu cầu Wandy Chat', example: 2 })
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(100)
  partySize?: number;

  @ApiPropertyOptional({ description: 'Mô tả nhóm khách (VD: 2 người lớn)', example: '2 người lớn' })
  @IsOptional()
  @IsString()
  @MaxLength(120)
  partyDescription?: string;

  @ApiPropertyOptional({ description: 'Giờ bắt đầu khung lịch trong ngày (HH:MM)', example: '08:00' })
  @IsOptional()
  @IsString()
  @MaxLength(16)
  timeWindowStart?: string;

  @ApiPropertyOptional({ description: 'Giờ kết thúc khung lịch trong ngày (HH:MM)', example: '12:00' })
  @IsOptional()
  @IsString()
  @MaxLength(16)
  timeWindowEnd?: string;

  @ApiPropertyOptional({ description: 'Ngân sách tổng từ yêu cầu chat (VND)', example: 500000 })
  @IsOptional()
  @IsInt()
  @Min(0)
  @Max(2147483647)
  budgetOverride?: number;

  @ApiPropertyOptional({ description: 'Danh sách sở thích trích từ yêu cầu chat', type: [String] })
  @IsOptional()
  @IsArray()
  @ArrayMaxSize(20)
  @IsString({ each: true })
  @MaxLength(64, { each: true })
  interestsOverride?: string[];
}
