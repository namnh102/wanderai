import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { ExpenseCategory, SplitType } from '@prisma/client';
import { Transform, Type } from 'class-transformer';
import {
  ArrayMaxSize,
  ArrayMinSize,
  IsArray,
  IsDateString,
  IsEnum,
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  Max,
  MaxLength,
  Min,
  ValidateNested,
} from 'class-validator';

export class CustomSplitEntryDto {
  @ApiProperty({ description: 'UUID thành viên được chia chi phí' })
  @Transform(({ value }: { value: unknown }) =>
    typeof value === 'string' ? value.trim().toLowerCase() : value,
  )
  @IsUUID('all', { message: 'userId trong customSplits phải là UUID hợp lệ' })
  userId: string;

  @ApiProperty({ description: 'Phần tiền chia (số nguyên VND >= 0)', example: 50000 })
  @IsInt({ message: 'shareAmount phải là số nguyên VND' })
  @Min(0, { message: 'shareAmount không được âm' })
  @Max(2147483647, { message: 'shareAmount vượt quá giới hạn INT32' })
  shareAmount: number;
}

export class CreateExpenseDto {
  @ApiProperty({ description: 'Tên khoản chi', example: 'Bữa tối hải sản Hạ Long' })
  @Transform(({ value }: { value: unknown }) =>
    typeof value === 'string' ? value.trim() : value,
  )
  @IsString()
  @IsNotEmpty({ message: 'Tên khoản chi không được để trống' })
  @MaxLength(200, { message: 'Tên khoản chi tối đa 200 ký tự' })
  title: string;

  @ApiProperty({ description: 'Tổng số tiền nguyên VND (> 0)', example: 100000 })
  @IsInt({ message: 'Số tiền phải là số nguyên VND' })
  @Min(1, { message: 'Số tiền phải lớn hơn hoặc bằng 1 VND' })
  @Max(2147483647, { message: 'Số tiền vượt quá giới hạn INT32 (2.147.483.647 VND)' })
  amount: number;

  @ApiPropertyOptional({ description: 'UUID thành viên trả tiền (mặc định người tạo)' })
  @IsOptional()
  @Transform(({ value }: { value: unknown }) => {
    if (typeof value !== 'string') return value;
    const trimmed = value.trim().toLowerCase();
    return trimmed.length > 0 ? trimmed : undefined;
  })
  @IsUUID('all', { message: 'paidByUserId phải là UUID hợp lệ' })
  paidByUserId?: string;

  @ApiPropertyOptional({ enum: ExpenseCategory, default: ExpenseCategory.OTHER })
  @IsOptional()
  @IsEnum(ExpenseCategory, { message: 'category không hợp lệ' })
  category?: ExpenseCategory;

  @ApiPropertyOptional({ enum: SplitType, default: SplitType.EQUAL })
  @IsOptional()
  @IsEnum(SplitType, { message: 'splitType phải là EQUAL hoặc CUSTOM' })
  splitType?: SplitType;

  @ApiPropertyOptional({ description: 'Ngày chi tiêu (YYYY-MM-DD hoặc ISO8601)' })
  @IsOptional()
  @IsDateString({}, { message: 'expenseDate không đúng định dạng ngày' })
  expenseDate?: string;

  @ApiPropertyOptional({ description: 'Ghi chú khoản chi' })
  @IsOptional()
  @IsString()
  @MaxLength(1000, { message: 'Ghi chú tối đa 1000 ký tự' })
  notes?: string;

  @ApiPropertyOptional({
    description: 'Danh sách UUID thành viên tham gia chia đều (EQUAL)',
    type: [String],
  })
  @IsOptional()
  @IsArray()
  @ArrayMinSize(1, { message: 'Cần ít nhất 1 thành viên tham gia chia chi phí' })
  @ArrayMaxSize(100)
  @Transform(({ value }: { value: unknown }) =>
    Array.isArray(value)
      ? value.map((item) =>
          typeof item === 'string' ? item.trim().toLowerCase() : item,
        )
      : value,
  )
  @IsUUID('all', {
    each: true,
    message: 'Mỗi phần tử trong participantIds phải là UUID hợp lệ',
  })
  participantIds?: string[];

  @ApiPropertyOptional({
    description: 'Danh sách phần chia tùy chỉnh (CUSTOM)',
    type: [CustomSplitEntryDto],
  })
  @IsOptional()
  @IsArray()
  @ArrayMinSize(1, { message: 'customSplits cần ít nhất 1 phần tử' })
  @ArrayMaxSize(100)
  @ValidateNested({ each: true })
  @Type(() => CustomSplitEntryDto)
  customSplits?: CustomSplitEntryDto[];

  @ApiPropertyOptional({ description: 'Khóa idempotency chống ghi trùng' })
  @IsOptional()
  @Transform(({ value }: { value: unknown }) => {
    if (typeof value !== 'string') return value;
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  })
  @IsString()
  @MaxLength(128)
  clientRequestId?: string;
}

export class CreateSettlementDto {
  @ApiProperty({ description: 'UUID thành viên trả nợ (debtor)' })
  @Transform(({ value }: { value: unknown }) =>
    typeof value === 'string' ? value.trim().toLowerCase() : value,
  )
  @IsUUID('all', { message: 'debtorId phải là UUID hợp lệ' })
  debtorId: string;

  @ApiProperty({ description: 'UUID thành viên nhận tiền (creditor)' })
  @Transform(({ value }: { value: unknown }) =>
    typeof value === 'string' ? value.trim().toLowerCase() : value,
  )
  @IsUUID('all', { message: 'creditorId phải là UUID hợp lệ' })
  creditorId: string;

  @ApiProperty({ description: 'Số tiền hoàn trả nguyên VND (> 0)', example: 50000 })
  @IsInt({ message: 'Số tiền đối soát phải là số nguyên VND' })
  @Min(1, { message: 'Số tiền đối soát phải lớn hơn hoặc bằng 1 VND' })
  @Max(2147483647, { message: 'Số tiền đối soát vượt quá giới hạn INT32' })
  amount: number;

  @ApiPropertyOptional({ description: 'Ghi chú đối soát' })
  @IsOptional()
  @IsString()
  @MaxLength(500, { message: 'Ghi chú tối đa 500 ký tự' })
  notes?: string;

  @ApiPropertyOptional({ description: 'Thời điểm hoàn trả (ISO8601)' })
  @IsOptional()
  @IsDateString({}, { message: 'settledAt không đúng định dạng ngày giờ' })
  settledAt?: string;

  @ApiPropertyOptional({ description: 'Khóa idempotency chống xác nhận trùng' })
  @IsOptional()
  @Transform(({ value }: { value: unknown }) => {
    if (typeof value !== 'string') return value;
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  })
  @IsString()
  @MaxLength(128)
  clientRequestId?: string;
}
