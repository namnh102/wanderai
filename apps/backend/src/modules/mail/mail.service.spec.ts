import { ConfigModule, ConfigService } from '@nestjs/config';
import { Test } from '@nestjs/testing';
import * as nodemailer from 'nodemailer';
import { MailModule } from './mail.module';
import { MailService } from './mail.service';
import { InMemoryTestMailTransport } from './transports/in-memory-test-mail.transport';
import {
  MAIL_TRANSPORT,
  MailTransport,
} from './transports/mail-transport.interface';
import { NoopLogMailTransport } from './transports/noop-log-mail.transport';
import { SmtpMailTransport } from './transports/smtp-mail.transport';

describe('MailModule & MailService', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('selects InMemoryTestMailTransport when NODE_ENV=test and SMTP_HOST is unset', async () => {
    const moduleRef = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({
          isGlobal: true,
          ignoreEnvFile: true,
          load: [
            () => ({
              NODE_ENV: 'test',
              SMTP_HOST: '',
              APP_RESET_PASSWORD_URL: 'https://wanderai.app/reset-password?src=email',
            }),
          ],
        }),
        MailModule,
      ],
    }).compile();

    const transport = moduleRef.get<MailTransport>(MAIL_TRANSPORT);
    const inMemory = moduleRef.get(InMemoryTestMailTransport);
    const mailService = moduleRef.get(MailService);

    expect(transport).toBeInstanceOf(InMemoryTestMailTransport);

    const result = await mailService.sendPasswordResetEmail({
      to: 'traveler@wanderai.test',
      displayName: 'Minh <Wanderer>',
      rawToken: 'abc123rawtoken',
      expiresInMinutes: 30,
    });

    expect(result).toEqual(
      expect.objectContaining({
        accepted: true,
        transport: 'memory',
      }),
    );

    const sent = inMemory.getLastMessageFor('TRAVELER@wanderai.test');
    expect(sent).toBeDefined();
    expect(sent?.text).toContain(
      'https://wanderai.app/reset-password?src=email&token=abc123rawtoken',
    );
    expect(sent?.html).toContain('Minh &lt;Wanderer&gt;');

    await moduleRef.close();
  });

  it('selects NoopLogMailTransport when SMTP_HOST is unset and NODE_ENV is not test', async () => {
    const previousNodeEnv = process.env.NODE_ENV;
    const previousSmtpHost = process.env.SMTP_HOST;
    process.env.NODE_ENV = 'development';
    delete process.env.SMTP_HOST;

    try {
      const moduleRef = await Test.createTestingModule({
        imports: [
          ConfigModule.forRoot({
            isGlobal: true,
            ignoreEnvFile: true,
            load: [
              () => ({
                NODE_ENV: 'development',
                SMTP_HOST: '',
              }),
            ],
          }),
          MailModule,
        ],
      }).compile();

      const transport = moduleRef.get<MailTransport>(MAIL_TRANSPORT);
      expect(transport).toBeInstanceOf(NoopLogMailTransport);

      const loggerWarnSpy = jest
        .spyOn(
          (transport as unknown as { logger: { warn: (msg: string) => void } })
            .logger,
          'warn',
        )
        .mockImplementation(() => undefined);

      const mailService = moduleRef.get(MailService);
      const result = await mailService.sendPasswordResetEmail({
        to: 'secret.user@wanderai.test',
        rawToken: 'super-secret-reset-token-999',
        expiresInMinutes: 30,
      });

      expect(result).toEqual({ accepted: true, transport: 'noop' });
      expect(loggerWarnSpy).toHaveBeenCalledTimes(1);
      const loggedMessage = loggerWarnSpy.mock.calls[0][0];
      expect(loggedMessage).not.toContain('super-secret-reset-token-999');
      expect(loggedMessage).not.toContain('secret.user@wanderai.test');
      expect(loggedMessage).toContain('se***@wanderai.test');

      await moduleRef.close();
    } finally {
      if (previousNodeEnv === undefined) delete process.env.NODE_ENV;
      else process.env.NODE_ENV = previousNodeEnv;
      if (previousSmtpHost === undefined) delete process.env.SMTP_HOST;
      else process.env.SMTP_HOST = previousSmtpHost;
    }
  });

  it('selects SmtpMailTransport when SMTP_HOST is configured and delegates to nodemailer', async () => {
    const sendMailMock = jest.fn().mockResolvedValue({
      accepted: ['traveler@wanderai.test'],
      messageId: '<smtp-msg-1@wanderai.test>',
    });
    const createTransportSpy = jest
      .spyOn(nodemailer, 'createTransport')
      .mockReturnValue({
        sendMail: sendMailMock,
      } as unknown as nodemailer.Transporter);

    const moduleRef = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({
          isGlobal: true,
          ignoreEnvFile: true,
          load: [
            () => ({
              NODE_ENV: 'test',
              SMTP_HOST: 'smtp.example.com',
              SMTP_PORT: '465',
              SMTP_USER: 'mailer',
              SMTP_PASS: 'app-pass',
              SMTP_FROM: 'WanderAI <noreply@wanderai.example>',
            }),
          ],
        }),
        MailModule,
      ],
    }).compile();

    const transport = moduleRef.get<MailTransport>(MAIL_TRANSPORT);
    expect(transport).toBeInstanceOf(SmtpMailTransport);
    expect(createTransportSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        host: 'smtp.example.com',
        port: 465,
        secure: true,
        auth: { user: 'mailer', pass: 'app-pass' },
      }),
    );

    const mailService = moduleRef.get(MailService);
    const result = await mailService.sendPasswordResetEmail({
      to: 'traveler@wanderai.test',
      rawToken: 'raw-smtp-token',
      expiresInMinutes: 30,
    });

    expect(result).toEqual({
      accepted: true,
      transport: 'smtp',
      messageId: '<smtp-msg-1@wanderai.test>',
    });
    expect(sendMailMock).toHaveBeenCalledWith(
      expect.objectContaining({
        from: 'WanderAI <noreply@wanderai.example>',
        to: 'traveler@wanderai.test',
      }),
    );

    await moduleRef.close();
  });

  it('throws if SmtpMailTransport is constructed without SMTP_HOST', () => {
    const emptyConfig = new ConfigService({ SMTP_HOST: '   ' });
    expect(() => new SmtpMailTransport(emptyConfig)).toThrow(
      /SMTP_HOST is required/,
    );
  });
});
