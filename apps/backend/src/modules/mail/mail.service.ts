import { Inject, Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  MAIL_TRANSPORT,
  MailTransport,
  SendMailResult,
} from './transports/mail-transport.interface';

export interface SendPasswordResetEmailInput {
  to: string;
  displayName?: string | null;
  rawToken: string;
  expiresInMinutes: number;
}

@Injectable()
export class MailService {
  constructor(
    @Inject(MAIL_TRANSPORT) private readonly mailTransport: MailTransport,
    private readonly configService: ConfigService,
  ) {}

  buildPasswordResetUrl(rawToken: string): string {
    const baseUrl =
      this.configService.get<string>('APP_RESET_PASSWORD_URL')?.trim() ||
      'http://localhost:3000/reset-password';

    try {
      const parsed = new URL(baseUrl);
      parsed.searchParams.set('token', rawToken);
      return parsed.toString();
    } catch {
      const separator = baseUrl.includes('?') ? '&' : '?';
      return `${baseUrl}${separator}token=${encodeURIComponent(rawToken)}`;
    }
  }

  async sendPasswordResetEmail(
    input: SendPasswordResetEmailInput,
  ): Promise<SendMailResult> {
    const resetUrl = this.buildPasswordResetUrl(input.rawToken);
    const greetingName = input.displayName?.trim() || 'bạn';
    const subject = 'WanderAI — Đặt lại mật khẩu tài khoản';

    const text = [
      `Xin chào ${greetingName},`,
      '',
      'Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản WanderAI của bạn.',
      `Vui lòng mở liên kết dưới đây trong vòng ${input.expiresInMinutes} phút:`,
      resetUrl,
      '',
      'Nếu bạn không yêu cầu thao tác này, hãy bỏ qua email này.',
    ].join('\n');

    const html = [
      `<p>Xin chào ${escapeHtml(greetingName)},</p>`,
      '<p>Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản WanderAI của bạn.</p>',
      `<p>Liên kết có hiệu lực trong vòng <strong>${input.expiresInMinutes} phút</strong>:</p>`,
      `<p><a href="${escapeHtml(resetUrl)}">Đặt lại mật khẩu</a></p>`,
      '<p>Nếu bạn không yêu cầu thao tác này, vui lòng bỏ qua email này.</p>',
    ].join('\n');

    return this.mailTransport.sendMail({
      to: input.to,
      subject,
      text,
      html,
    });
  }
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
