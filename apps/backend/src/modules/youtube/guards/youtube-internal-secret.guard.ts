import {
  CanActivate,
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import * as crypto from "crypto";
import { Request } from "express";
import { YOUTUBE_ERROR_CODES } from "../../../common/constants/youtube-error-codes";

@Injectable()
export class YoutubeInternalSecretGuard implements CanActivate {
  constructor(private readonly configService: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const configuredSecret = this.configService
      .get<string>("YOUTUBE_EVENTS_INTERNAL_SECRET")
      ?.trim();
    if (!configuredSecret) {
      return true;
    }

    const request = context.switchToHttp().getRequest<Request>();
    const providedHeader = request.headers["x-youtube-internal-secret"];
    if (typeof providedHeader !== "string" || !providedHeader.trim()) {
      throw new UnauthorizedException({
        message: "Missing or invalid x-youtube-internal-secret header",
        errorCode: YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
      });
    }

    const expectedDigest = crypto
      .createHash("sha256")
      .update(configuredSecret, "utf8")
      .digest();
    const providedDigest = crypto
      .createHash("sha256")
      .update(providedHeader.trim(), "utf8")
      .digest();

    if (!crypto.timingSafeEqual(expectedDigest, providedDigest)) {
      throw new UnauthorizedException({
        message: "Invalid x-youtube-internal-secret header",
        errorCode: YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
      });
    }

    return true;
  }
}
