import { Module } from '@nestjs/common';
import { TripsService } from './trips.service';
import { TripsController } from './trips.controller';
import { AiProxyModule } from '../ai-proxy/ai-proxy.module';

@Module({
  imports: [AiProxyModule],
  controllers: [TripsController],
  providers: [TripsService],
  exports: [TripsService],
})
export class TripsModule {}
