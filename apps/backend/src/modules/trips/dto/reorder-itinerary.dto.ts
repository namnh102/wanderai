import {
  ArrayMaxSize,
  ArrayMinSize,
  IsArray,
  IsInt,
  IsOptional,
  IsUUID,
  Max,
  Min,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class ReorderItineraryItemDto {
  @ApiProperty({
    description: 'UUID của hoạt động trong lịch trình',
    example: '94f73104-7bb8-457b-a023-8927663b50c1',
  })
  @IsUUID('all', { message: 'itemId phải là UUID hợp lệ' })
  itemId: string;

  @ApiProperty({
    description: 'Thứ tự hoạt động mới trong ngày (bắt đầu từ 1)',
    example: 1,
  })
  @IsInt({ message: 'orderIndex phải là số nguyên' })
  @Min(1, { message: 'orderIndex phải lớn hơn hoặc bằng 1' })
  @Max(200, { message: 'orderIndex tối đa 200' })
  orderIndex: number;
}

export class ReorderItineraryDto {
  @ApiPropertyOptional({
    description: 'Số thứ tự ngày nếu sắp xếp trong phạm vi một ngày cụ thể',
    example: 1,
  })
  @IsOptional()
  @IsInt({ message: 'dayNumber phải là số nguyên' })
  @Min(1, { message: 'dayNumber phải lớn hơn hoặc bằng 1' })
  @Max(60, { message: 'dayNumber tối đa 60' })
  dayNumber?: number;

  @ApiProperty({
    description: 'Danh sách thứ tự mới của các hoạt động',
    type: [ReorderItineraryItemDto],
  })
  @IsArray()
  @ArrayMinSize(1, { message: 'Danh sách hoạt động sắp xếp không được để trống' })
  @ArrayMaxSize(200, { message: 'Tối đa 200 hoạt động mỗi lần sắp xếp' })
  @ValidateNested({ each: true })
  @Type(() => ReorderItineraryItemDto)
  items: ReorderItineraryItemDto[];
}
