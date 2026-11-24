import { Injectable } from '@nestjs/common';
import { randomUUID } from 'crypto';
import {
  MailTransport,
  SendMailPayload,
  SendMailResult,
} from './mail-transport.interface';

export interface SentMailRecord extends SendMailPayload {
  messageId: string;
  sentAt: Date;
}

@Injectable()
export class InMemoryTestMailTransport implements MailTransport {
  private readonly messages: SentMailRecord[] = [];

  async sendMail(payload: SendMailPayload): Promise<SendMailResult> {
    const messageId = `mem-${randomUUID()}`;
    this.messages.push({
      ...payload,
      messageId,
      sentAt: new Date(),
    });
    return {
      accepted: true,
      transport: 'memory',
      messageId,
    };
  }

  getMessages(): SentMailRecord[] {
    return [...this.messages];
  }

  getLastMessageFor(email: string): SentMailRecord | undefined {
    const normalized = email.toLowerCase().trim();
    for (let i = this.messages.length - 1; i >= 0; i -= 1) {
      if (this.messages[i].to.toLowerCase().trim() === normalized) {
        return this.messages[i];
      }
    }
    return undefined;
  }

  clear(): void {
    this.messages.length = 0;
  }
}
