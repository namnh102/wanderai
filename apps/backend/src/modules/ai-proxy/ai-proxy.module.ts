import { Module } from '@nestjs/common';
import { AiProxyService } from './ai-proxy.service';
import { AiProxyController } from './ai-proxy.controller';
import { AiChatProxyService } from './internal-auth';

@Module({
  controllers: [AiProxyController],
  providers: [
    AiChatProxyService,
    {
      provide: AiProxyService,
      useExisting: AiChatProxyService,
    },
  ],
  exports: [AiProxyService, AiChatProxyService],
})
export class AiProxyModule {}
