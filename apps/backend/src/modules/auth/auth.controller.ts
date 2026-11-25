import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Post,
  Query,
} from '@nestjs/common';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import { AuthService } from './auth.service';
import { FacebookOAuthDto } from './dto/facebook-oauth.dto';
import { ForgotPasswordDto } from './dto/forgot-password.dto';
import { GoogleOAuthDto } from './dto/google-oauth.dto';
import { LoginDto } from './dto/login.dto';
import { RefreshTokenDto } from './dto/refresh-token.dto';
import { RegisterDto } from './dto/register.dto';
import { ResetPasswordDto } from './dto/reset-password.dto';
import { OAuthService } from './oauth.service';
import { PasswordResetService } from './password-reset.service';

@ApiTags('Auth')
@Controller('auth')
export class AuthController {
  constructor(
    private readonly authService: AuthService,
    private readonly passwordResetService: PasswordResetService,
    private readonly oauthService: OAuthService,
  ) {}

  @Post('register')
  @ApiOperation({ summary: 'Đăng ký tài khoản mới' })
  @ApiResponse({ status: 201, description: 'Đăng ký thành công, trả về tokens' })
  @ApiResponse({
    status: 400,
    description: 'Email đã tồn tại hoặc dữ liệu không hợp lệ',
  })
  async register(@Body() dto: RegisterDto) {
    return this.authService.register(dto);
  }

  @Post('login')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Đăng nhập' })
  @ApiResponse({ status: 200, description: 'Đăng nhập thành công, trả về tokens' })
  @ApiResponse({ status: 401, description: 'Email hoặc mật khẩu không đúng' })
  async login(@Body() dto: LoginDto) {
    return this.authService.login(dto);
  }

  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Refresh access token' })
  @ApiResponse({ status: 200, description: 'Trả về tokens mới' })
  @ApiResponse({ status: 401, description: 'Refresh token không hợp lệ' })
  async refresh(@Body() dto: RefreshTokenDto) {
    return this.authService.refreshToken(dto.refresh_token);
  }

  @Post('forgot-password')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Yêu cầu gửi email đặt lại mật khẩu' })
  @ApiResponse({
    status: 200,
    description: 'Trả về phản hồi trung lập không lộ trạng thái tồn tại email',
  })
  async forgotPassword(@Body() dto: ForgotPasswordDto) {
    return this.passwordResetService.forgotPassword(dto);
  }

  @Get('reset-password/validate')
  @ApiOperation({ summary: 'Kiểm tra tính hợp lệ của token đặt lại mật khẩu' })
  @ApiResponse({ status: 200, description: 'Token hợp lệ' })
  @ApiResponse({
    status: 400,
    description: 'Token không hợp lệ, đã sử dụng hoặc đã hết hạn',
  })
  async validateResetToken(@Query('token') token?: string) {
    return this.passwordResetService.validateResetToken(token);
  }

  @Post('reset-password')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Đặt lại mật khẩu mới bằng token một lần' })
  @ApiResponse({ status: 200, description: 'Đặt lại mật khẩu thành công' })
  @ApiResponse({
    status: 400,
    description: 'Token không hợp lệ, đã sử dụng, hết hạn hoặc mật khẩu không đạt yêu cầu',
  })
  async resetPassword(@Body() dto: ResetPasswordDto) {
    return this.passwordResetService.resetPassword(dto);
  }

  @Post('oauth/google')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Đăng nhập hoặc liên kết tài khoản bằng Google ID Token' })
  @ApiResponse({ status: 200, description: 'Đăng nhập thành công, trả về tokens và user' })
  @ApiResponse({ status: 401, description: 'Google ID Token không hợp lệ' })
  async loginWithGoogle(@Body() dto: GoogleOAuthDto) {
    return this.oauthService.loginWithGoogle(dto.idToken);
  }

  @Post('oauth/facebook')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Đăng nhập hoặc liên kết tài khoản bằng Facebook Access Token' })
  @ApiResponse({ status: 200, description: 'Đăng nhập thành công, trả về tokens và user' })
  @ApiResponse({ status: 401, description: 'Facebook Access Token không hợp lệ' })
  async loginWithFacebook(@Body() dto: FacebookOAuthDto) {
    return this.oauthService.loginWithFacebook(dto.accessToken);
  }
}
