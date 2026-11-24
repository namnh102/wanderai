import { ApiProperty, ApiPropertyOptional } from "@nestjs/swagger";
import { Transform, Type } from "class-transformer";
import {
  ArrayMaxSize,
  IsArray,
  IsIn,
  IsInt,
  IsISO8601,
  IsNotEmpty,
  IsNumber,
  IsOptional,
  IsString,
  IsUUID,
  Matches,
  Max,
  MaxLength,
  Min,
} from "class-validator";

export const YOUTUBE_VIDEO_ID_REGEX = /^[A-Za-z0-9_-]{11}$/;
export const EXPLICIT_TZ_ISO_REGEX = /(?:Z|[+-]\d{2}:\d{2})$/;

const trimStringValue = ({ value }: { value: unknown }) =>
  typeof value === "string" ? value.trim() : value;

const trimStringArray = ({ value }: { value: unknown }) =>
  Array.isArray(value)
    ? value.map((item) => (typeof item === "string" ? item.trim() : item))
    : value;

const transformOptionalCoordinate = ({ value }: { value: unknown }) => {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed.length === 0) {
      return undefined;
    }
    return Number(trimmed);
  }
  return Number.NaN;
};

export class IngestYoutubeEventDto {
  @ApiPropertyOptional({
    description:
      "Khóa định danh sự kiện tùy chọn (nếu bỏ trống, hệ thống suy dẫn khóa tất định từ videoId + sourceUpdatedAt/publishedAt)",
    example: "yt-feed-entry-thap-dong-ho-001",
  })
  @IsOptional()
  @Transform(trimStringValue)
  @IsString()
  @MaxLength(200)
  eventId?: string;

  @ApiProperty({
    description: "Mã video YouTube 11 ký tự chuẩn",
    example: "dQw4w9WgXcQ",
  })
  @Transform(trimStringValue)
  @IsString()
  @Matches(YOUTUBE_VIDEO_ID_REGEX, {
    message: "videoId must be a valid 11-character YouTube video ID",
  })
  videoId!: string;

  @ApiProperty({
    description: "Mã kênh YouTube phát hành video",
    example: "UC_x5XG1OV2P6uZZ5FSM9Ttw",
  })
  @Transform(trimStringValue)
  @IsString()
  @IsNotEmpty()
  @MaxLength(64)
  channelId!: string;

  @ApiPropertyOptional({
    description: "Tên hiển thị của kênh YouTube",
    example: "Quảng Ninh Travel Official",
  })
  @IsOptional()
  @Transform(trimStringValue)
  @IsString()
  @MaxLength(255)
  channelTitle?: string;

  @ApiProperty({
    description: "Tiêu đề bài đăng / video YouTube",
    example: "Check-in Tháp Đồng Hồ Hạ Long buổi tối rực rỡ",
  })
  @Transform(trimStringValue)
  @IsString()
  @IsNotEmpty()
  @MaxLength(500)
  title!: string;

  @ApiPropertyOptional({
    description: "Mô tả video YouTube",
    example:
      "Hành trình dạo quanh vòng xuyến Cột Đồng Hồ bên cạnh Vincom Plaza Hạ Long, Quảng Ninh.",
  })
  @IsOptional()
  @Transform(trimStringValue)
  @IsString()
  @MaxLength(10000)
  description?: string;

  @ApiPropertyOptional({
    description: "Danh sách thẻ (tags) đi kèm video",
    type: [String],
  })
  @IsOptional()
  @Transform(trimStringArray)
  @IsArray()
  @ArrayMaxSize(50)
  @IsString({ each: true })
  tags?: string[];

  @ApiProperty({
    description:
      "Giờ đăng gốc trên YouTube (ISO-8601 có múi giờ, lưu chuẩn UTC TIMESTAMPTZ)",
    example: "2026-11-24T13:30:00Z",
  })
  @IsISO8601({ strict: true })
  @Matches(EXPLICIT_TZ_ISO_REGEX, {
    message:
      "publishedAt must include an explicit timezone offset (Z or ±HH:MM)",
  })
  publishedAt!: string;

  @ApiPropertyOptional({
    description:
      "Thời điểm cập nhật bản tin từ YouTube feed (<updated>), nếu có",
    example: "2026-11-24T13:35:00Z",
  })
  @IsOptional()
  @IsISO8601({ strict: true })
  @Matches(EXPLICIT_TZ_ISO_REGEX, {
    message:
      "sourceUpdatedAt must include an explicit timezone offset (Z or ±HH:MM)",
  })
  sourceUpdatedAt?: string;

  @ApiPropertyOptional({
    description: "Vĩ độ GPS đính kèm metadata quay video (nếu có)",
    example: 20.95161,
  })
  @IsOptional()
  @Transform(transformOptionalCoordinate)
  @IsNumber()
  @Min(-90)
  @Max(90)
  latitude?: number;

  @ApiPropertyOptional({
    description: "Kinh độ GPS đính kèm metadata quay video (nếu có)",
    example: 107.0852,
  })
  @IsOptional()
  @Transform(transformOptionalCoordinate)
  @IsNumber()
  @Min(-180)
  @Max(180)
  longitude?: number;

  @ApiPropertyOptional({
    description:
      "UUID địa điểm gợi ý (vẫn bắt buộc vượt qua cổng kiểm chứng tên/vị trí/nguồn trước khi được gắn vào POI)",
    example: "65562a67-84ff-44a0-990d-31917a2a9bd0",
  })
  @IsOptional()
  @IsUUID()
  candidatePlaceId?: string;
}

export class YoutubePlaceUpdatesQueryDto {
  @ApiPropertyOptional({
    description: "Số lượng cập nhật YouTube tối đa trả về (1..50)",
    default: 10,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(50)
  limit: number = 10;
}

export class YoutubeDestinationUpdatesQueryDto extends YoutubePlaceUpdatesQueryDto {
  @ApiPropertyOptional({
    description: "Lọc theo phạm vi gắn (POI hoặc CITY)",
    enum: ["POI", "CITY"],
  })
  @IsOptional()
  @Transform(trimStringValue)
  @IsIn(["POI", "CITY"])
  scope?: "POI" | "CITY";
}
