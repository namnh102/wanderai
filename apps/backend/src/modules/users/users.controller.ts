import { Controller, Get, Put, Body, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { UsersService } from './users.service';
import { JwtAuthGuard } from '../../common/guards/jwt-auth.guard';
import { CurrentUser } from '../../common/decorators/current-user.decorator';

@ApiTags('Users')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Get('me')
  @ApiOperation({ summary: 'Lấy thông tin user hiện tại' })
  getProfile(@CurrentUser() user: any) {
    return this.usersService.findById(user.id);
  }

  @Put('me')
  @ApiOperation({ summary: 'Cập nhật profile' })
  updateProfile(@CurrentUser() user: any, @Body() data: { displayName?: string; bio?: string; avatar?: string }) {
    return this.usersService.updateProfile(user.id, data);
  }
}
