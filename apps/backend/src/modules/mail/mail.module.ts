import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { MailService } from './mail.service';
import { MAIL_TRANSPORT, MailTransport } from './transports/mail-transport.interface';
import { InMemoryTestMailTransport } from './transports/in-memory-test-mail.transport';
import { NoopLogMailTransport } from './transports/noop-log-mail.transport';
import { SmtpMailTransport } from './transports/smtp-mail.transport';

@Module({
  providers: [
    InMemoryTestMailTransport,
    NoopLogMailTransport,
    {
      provide: MAIL_TRANSPORT,
      inject: [ConfigService, InMemoryTestMailTransport, NoopLogMailTransport],
      useFactory: (
        configService: ConfigService,
        inMemoryTransport: InMemoryTestMailTransport,
        noopTransport: NoopLogMailTransport,
      ): MailTransport => {
        const smtpHost = configService.get<string>('SMTP_HOST')?.trim();
        if (smtpHost) {
          return new SmtpMailTransport(configService);
        }

        const nodeEnv =
          configService.get<string>('NODE_ENV')?.trim() || process.env.NODE_ENV;
        if (nodeEnv === 'test') {
          return inMemoryTransport;
        }

        return noopTransport;
      },
    },
    MailService,
  ],
  exports: [MailService, MAIL_TRANSPORT, InMemoryTestMailTransport],
})
export class MailModule {}
