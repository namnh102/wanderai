import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as nodemailer from 'nodemailer';
import type { Transporter } from 'nodemailer';
import {
  MailTransport,
  SendMailPayload,
  SendMailResult,
} from './mail-transport.interface';

@Injectable()
export class SmtpMailTransport implements MailTransport {
  private readonly transporter: Transporter;
  private readonly fromAddress: string;

  constructor(private readonly configService: ConfigService) {
    const host = this.configService.get<string>('SMTP_HOST')?.trim();
    if (!host) {
      throw new Error('SMTP_HOST is required when initializing SmtpMailTransport.');
    }

    const rawPort = this.configService.get<string>('SMTP_PORT');
    const parsedPort = rawPort ? Number(rawPort) : 587;
    const port = Number.isFinite(parsedPort) && parsedPort > 0 ? parsedPort : 587;

    const rawSecure = this.configService.get<string>('SMTP_SECURE');
    const secure =
      rawSecure !== undefined
        ? rawSecure.toLowerCase().trim() === 'true'
        : port === 465;

    const user = this.configService.get<string>('SMTP_USER')?.trim();
    const pass = this.configService.get<string>('SMTP_PASS');

    this.fromAddress =
      this.configService.get<string>('SMTP_FROM')?.trim() ||
      'WanderAI <no-reply@wanderai.local>';

    this.transporter = nodemailer.createTransport({
      host,
      port,
      secure,
      auth: user ? { user, pass: pass ?? '' } : undefined,
      connectionTimeout: 10_000,
      greetingTimeout: 10_000,
      socketTimeout: 15_000,
    });
  }

  async sendMail(payload: SendMailPayload): Promise<SendMailResult> {
    const info = await this.transporter.sendMail({
      from: this.fromAddress,
      to: payload.to,
      subject: payload.subject,
      text: payload.text,
      html: payload.html,
    });

    const acceptedCount = Array.isArray(info.accepted) ? info.accepted.length : 1;
    return {
      accepted: acceptedCount > 0,
      transport: 'smtp',
      messageId: info.messageId,
    };
  }
}
