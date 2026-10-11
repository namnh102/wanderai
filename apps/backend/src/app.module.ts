import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './modules/auth/auth.module';
import { UsersModule } from './modules/users/users.module';
import { DestinationsModule } from './modules/destinations/destinations.module';
import { TripsModule } from './modules/trips/trips.module';
import { VideosModule } from './modules/videos/videos.module';
import { ReviewsModule } from './modules/reviews/reviews.module';
import { AiProxyModule } from './modules/ai-proxy/ai-proxy.module';
import { PlacesModule } from './modules/places/places.module';
import { HealthModule } from './modules/health/health.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    PrismaModule,
    HealthModule,
    AuthModule,
    UsersModule,
    DestinationsModule,
    PlacesModule,
    TripsModule,
    VideosModule,
    ReviewsModule,
    AiProxyModule,
  ],
  controllers: [],
  providers: [],
})
export class AppModule {}
