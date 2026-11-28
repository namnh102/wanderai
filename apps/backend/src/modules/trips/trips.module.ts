import { Module } from '@nestjs/common';
import { TripsService } from './trips.service';
import { TripInvitesService } from './trip-invites.service';
import { TripsController } from './trips.controller';
import { AiProxyModule } from '../ai-proxy/ai-proxy.module';

@Module({
  imports: [AiProxyModule],
  controllers: [TripsController],
  providers: [TripsService, TripInvitesService],
  exports: [TripsService, TripInvitesService],
})
export class TripsModule {}
