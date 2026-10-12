import { Transform } from 'class-transformer';
import { IsIn, IsInt, IsOptional, Max, Min } from 'class-validator';
import { ApiPropertyOptional } from '@nestjs/swagger';

/** MVP destinations supported by the REC-A runtime (Dataset Freeze V2 core). */
export const SUPPORTED_RECOMMENDATION_DESTINATIONS = ['ha-noi', 'da-nang', 'ha-long'] as const;
export type RecommendationDestination = (typeof SUPPORTED_RECOMMENDATION_DESTINATIONS)[number];

/** REC-A baselines exposed publicly. */
export const SUPPORTED_RECOMMENDATION_MODELS = ['rec-a0', 'rec-a1'] as const;

export const RECOMMENDATION_TOP_K_DEFAULT = 10;
export const RECOMMENDATION_TOP_K_MIN = 1;
export const RECOMMENDATION_TOP_K_MAX = 50;

/**
 * Aliases mirror apps/ai-service/recommendation/reca/contract.py DESTINATION_SLUG_MAP.
 * The FastAPI service still validates independently; this is the public contract.
 */
const DESTINATION_ALIASES: Record<string, RecommendationDestination> = {
  'ha-noi': 'ha-noi',
  hanoi: 'ha-noi',
  'hà nội': 'ha-noi',
  ha_noi: 'ha-noi',
  hn: 'ha-noi',
  'da-nang': 'da-nang',
  danang: 'da-nang',
  'đà nẵng': 'da-nang',
  da_nang: 'da-nang',
  dn: 'da-nang',
  'ha-long': 'ha-long',
  halong: 'ha-long',
  'hạ long': 'ha-long',
  ha_long: 'ha-long',
  hl: 'ha-long',
};

function stripDiacritics(s: string): string {
  return s
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .join(' ');
}

/** Returns the canonical destination slug, or undefined when unsupported. */
export function normalizeRecommendationDestination(raw: string): RecommendationDestination | undefined {
  const lowered = raw.trim().toLowerCase();
  return DESTINATION_ALIASES[lowered] ?? DESTINATION_ALIASES[stripDiacritics(lowered)];
}

const toCanonicalDestination = ({ value }: { value: unknown }) => {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== 'string') return value; // fails @IsIn below
  if (value.trim() === '') return undefined; // empty param == not provided
  return normalizeRecommendationDestination(value) ?? value.trim();
};

const toStrictInteger = ({ value }: { value: unknown }) => {
  if (value === undefined || value === null || value === '') return RECOMMENDATION_TOP_K_DEFAULT;
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && /^-?\d+$/.test(value.trim())) return Number(value.trim());
  return value; // non-integer text stays a string and fails @IsInt (never NaN)
};

const toModel = ({ value }: { value: unknown }) => {
  if (value === undefined || value === null || value === '') return 'rec-a1';
  return typeof value === 'string' ? value.trim().toLowerCase() : value;
};

export class RecommendationQueryDto {
  @ApiPropertyOptional({
    description: 'Điểm đến MVP được hỗ trợ (ha-noi, da-nang, ha-long hoặc tên tiếng Việt tương ứng)',
    example: 'da-nang',
  })
  @IsOptional()
  @Transform(toCanonicalDestination)
  @IsIn(SUPPORTED_RECOMMENDATION_DESTINATIONS as unknown as string[], {
    message: 'Điểm đến không được hỗ trợ. Chỉ hỗ trợ: Hà Nội (ha-noi), Đà Nẵng (da-nang), Hạ Long (ha-long)',
  })
  destination?: string;

  @ApiPropertyOptional({ description: 'Số gợi ý tối đa (1-50)', example: 10, default: RECOMMENDATION_TOP_K_DEFAULT })
  @Transform(toStrictInteger)
  @IsInt({ message: 'topK phải là số nguyên từ 1 đến 50' })
  @Min(RECOMMENDATION_TOP_K_MIN, { message: 'topK phải là số nguyên từ 1 đến 50' })
  @Max(RECOMMENDATION_TOP_K_MAX, { message: 'topK phải là số nguyên từ 1 đến 50' })
  topK: number = RECOMMENDATION_TOP_K_DEFAULT;

  @ApiPropertyOptional({ description: 'Mô hình REC-A', enum: SUPPORTED_RECOMMENDATION_MODELS, default: 'rec-a1' })
  @Transform(toModel)
  @IsIn(SUPPORTED_RECOMMENDATION_MODELS as unknown as string[], {
    message: 'model không hợp lệ. Giá trị hợp lệ: rec-a0, rec-a1',
  })
  model: string = 'rec-a1';
}
