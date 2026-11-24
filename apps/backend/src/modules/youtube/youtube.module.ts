import {
  MiddlewareConsumer,
  Module,
  NestModule,
  RequestMethod,
} from "@nestjs/common";
import * as express from "express";
import { PrismaModule } from "../../prisma/prisma.module";
import {
  RawXmlRequest,
  YoutubeController,
  YoutubePlaceUpdatesController,
} from "./youtube.controller";
import { YoutubeService } from "./youtube.service";

@Module({
  imports: [PrismaModule],
  controllers: [YoutubeController, YoutubePlaceUpdatesController],
  providers: [YoutubeService],
  exports: [YoutubeService],
})
export class YoutubeModule implements NestModule {
  configure(consumer: MiddlewareConsumer): void {
    consumer
      .apply(
        express.text({
          type: ["application/atom+xml", "application/xml", "text/xml"],
          limit: "256kb",
          verify: (req, _res, buf) => {
            (req as RawXmlRequest).rawBodyText = buf.toString("utf8");
          },
        }),
      )
      .forRoutes({ path: "youtube/webhook", method: RequestMethod.POST });
  }
}
