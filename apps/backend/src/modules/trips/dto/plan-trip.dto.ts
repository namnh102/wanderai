import { IsOptional, IsString, MaxLength } from 'class-validator';
import { ApiPropertyOptional } from '@nestjs/swagger';

export class PlanTripDto {
  @ApiPropertyOptional({
    description: 'Yêu cầu hoặc ghi chú bổ sung cho Wandy AI',
    example: 'Tập trung quán ăn vặt, bãi biển và các điểm check-in đẹp',
  })
  @IsOptional()
  @IsString()
  @MaxLength(1000)
  additionalPrompt?: string;

  @ApiPropertyOptional({
    description: 'Nhịp độ chuyến đi (relaxed, moderate, fast)',
    example: 'relaxed',
  })
  @IsOptional()
  @IsString()
  @MaxLength(32)
  preferredPace?: string;
}
