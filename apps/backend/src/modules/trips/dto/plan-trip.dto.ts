import { IsOptional, IsString } from 'class-validator';
import { ApiPropertyOptional } from '@nestjs/swagger';

export class PlanTripDto {
  @ApiPropertyOptional({
    description: 'Yêu cầu hoặc ghi chú bổ sung cho Wandy AI',
    example: 'Tập trung quán ăn vặt, bãi biển và các điểm check-in đẹp',
  })
  @IsOptional()
  @IsString()
  additionalPrompt?: string;

  @ApiPropertyOptional({
    description: 'Nhịp độ chuyến đi (relaxed, moderate, fast)',
    example: 'relaxed',
  })
  @IsOptional()
  @IsString()
  preferredPace?: string;
}
