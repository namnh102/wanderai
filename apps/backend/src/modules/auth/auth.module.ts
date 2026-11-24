import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { JwtModule } from '@nestjs/jwt';
import { PassportModule } from '@nestjs/passport';
import { MailModule } from '../mail/mail.module';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';
import { getValidatedJwtConfig } from './jwt-config';
import { OAuthService } from './oauth.service';
import { PasswordResetService } from './password-reset.service';
import { JwtStrategy } from './strategies/jwt.strategy';
import { HttpFacebookOAuthVerifier } from './verifiers/facebook-oauth.verifier';
import { HttpGoogleOAuthVerifier } from './verifiers/google-oauth.verifier';
import {
  FACEBOOK_OAUTH_VERIFIER,
  GOOGLE_OAUTH_VERIFIER,
} from './verifiers/oauth-verifier.interface';

@Module({
  imports: [
    PassportModule,
    MailModule,
    JwtModule.registerAsync({
      imports: [ConfigModule],
      useFactory: async (configService: ConfigService) => {
        const { accessSecret } = getValidatedJwtConfig(configService);
        return {
          secret: accessSecret,
          signOptions: { expiresIn: '15m' },
        };
      },
      inject: [ConfigService],
    }),
  ],
  controllers: [AuthController],
  providers: [
    AuthService,
    PasswordResetService,
    OAuthService,
    JwtStrategy,
    HttpGoogleOAuthVerifier,
    HttpFacebookOAuthVerifier,
    {
      provide: GOOGLE_OAUTH_VERIFIER,
      useExisting: HttpGoogleOAuthVerifier,
    },
    {
      provide: FACEBOOK_OAUTH_VERIFIER,
      useExisting: HttpFacebookOAuthVerifier,
    },
  ],
  exports: [AuthService, PasswordResetService, OAuthService],
})
export class AuthModule {}
