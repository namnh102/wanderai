import { Transform } from 'class-transformer';
import { IsNotEmpty, IsUUID } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class AddGroupMemberDto {
  @ApiProperty({ description: 'UUID người dùng cần thêm vào nhóm' })
  @Transform(({ value }) => (typeof value === 'string' ? value.trim() : value))
  @IsUUID('all', { message: 'userId phải là UUID hợp lệ' })
  @IsNotEmpty({ message: 'userId không được để trống' })
  userId!: string;
}
