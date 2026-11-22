import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsIn, IsInt, IsOptional, IsUUID, Max, Min } from 'class-validator';

const blankToUndefined = ({ value }: { value: unknown }) =>
  value === undefined || value === null || (typeof value === 'string' && value.trim() === '')
    ? undefined
    : value;

const toStrictInt = (def: number) => ({ value }: { value: unknown }) => {
  if (value === undefined || value === null || (typeof value === 'string' && value.trim() === '')) return def;
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && /^[+-]?\d+$/.test(value.trim())) return Number(value.trim());
  return value;
};

export class MatchCandidatesQueryDto {
  @ApiPropertyOptional({ description: 'Lọc ứng viên có lịch trình tới điểm đến (UUID)' })
  @IsOptional()
  @Transform(blankToUndefined)
  @IsUUID('all', { message: 'destinationId phải là UUID hợp lệ' })
  destinationId?: string;

  @ApiPropertyOptional({ default: 20, minimum: 1, maximum: 50 })
  @Transform(toStrictInt(20))
  @IsInt({ message: 'limit phải là số nguyên từ 1 đến 50' })
  @Min(1, { message: 'limit phải là số nguyên từ 1 đến 50' })
  @Max(50, { message: 'limit phải là số nguyên từ 1 đến 50' })
  limit: number = 20;
}

export class CreateMatchRequestDto {
  @ApiProperty({ description: 'UUID người nhận lời mời kết bạn đồng hành' })
  @IsUUID('all', { message: 'receiverId phải là UUID hợp lệ' })
  receiverId!: string;
}

export class RespondMatchDto {
  @ApiProperty({ enum: ['ACCEPTED', 'REJECTED'] })
  @IsIn(['ACCEPTED', 'REJECTED'], {
    message: 'action chỉ chấp nhận ACCEPTED hoặc REJECTED',
  })
  action!: 'ACCEPTED' | 'REJECTED';
}
