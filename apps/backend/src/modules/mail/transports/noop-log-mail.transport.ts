import { Injectable, Logger } from '@nestjs/common';
import {
  MailTransport,
  SendMailPayload,
  SendMailResult,
} from './mail-transport.interface';

function maskEmail(email: string): string {
  const parts = email.split('@');
  if (parts.length !== 2) {
    return '***';
  }
  const [local, domain] = parts;
  const visibleLocal = local.length <= 2 ? '*' : `${local.slice(0, 2)}***`;
  return `${visibleLocal}@${domain}`;
}

@Injectable()
export class NoopLogMailTransport implements MailTransport {
  private readonly logger = new Logger(NoopLogMailTransport.name);

  async sendMail(payload: SendMailPayload): Promise<SendMailResult> {
    // Never log reset tokens, links, or full email body.
    this.logger.warn(
      `SMTP_HOST not configured; skipping email delivery to ${maskEmail(payload.to)} (subject="${payload.subject}").`,
    );
    return {
      accepted: true,
      transport: 'noop',
    };
  }
}
