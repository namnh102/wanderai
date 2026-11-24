export const MAIL_TRANSPORT = Symbol('MAIL_TRANSPORT');

export interface SendMailPayload {
  to: string;
  subject: string;
  text: string;
  html?: string;
}

export interface SendMailResult {
  accepted: boolean;
  transport: 'smtp' | 'memory' | 'noop';
  messageId?: string;
}

export interface MailTransport {
  sendMail(payload: SendMailPayload): Promise<SendMailResult>;
}
