import { Module } from "@nestjs/common";
import { ConfigModule } from "@nestjs/config";
import { PrismaModule } from "./prisma/prisma.module";
import { AuthModule } from "./modules/auth/auth.module";
import { validateEnvironmentJwtConfig } from "./modules/auth/jwt-config";
import { UsersModule } from "./modules/users/users.module";
import { DestinationsModule } from "./modules/destinations/destinations.module";
import { TripsModule } from "./modules/trips/trips.module";
import { VideosModule } from "./modules/videos/videos.module";
import { ReviewsModule } from "./modules/reviews/reviews.module";
import { AiProxyModule } from "./modules/ai-proxy/ai-proxy.module";
import { PlacesModule } from "./modules/places/places.module";
import { HealthModule } from "./modules/health/health.module";
import { MailModule } from "./modules/mail/mail.module";
import { MatchesModule } from "./modules/matches/matches.module";
import { YoutubeModule } from "./modules/youtube/youtube.module";
import { SafetyModule } from "./modules/safety/safety.module";

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      validate: validateEnvironmentJwtConfig,
    }),
    PrismaModule,
    MailModule,
    HealthModule,
    AuthModule,
    UsersModule,
    DestinationsModule,
    PlacesModule,
    TripsModule,
    VideosModule,
    ReviewsModule,
    MatchesModule,
    YoutubeModule,
    SafetyModule,
    AiProxyModule,
  ],
  controllers: [],
  providers: [],
})
export class AppModule {}
