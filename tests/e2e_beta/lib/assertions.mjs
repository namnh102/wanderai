import assert from 'node:assert/strict';

const ISO_8601_TZ_RE =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;
const UTC_Z_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const UUID_V4_LIKE_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function assertIso8601WithTz(value, label = 'timestamp') {
  assert.equal(typeof value, 'string', `${label} must be a string, got ${typeof value}`);
  assert.match(value, ISO_8601_TZ_RE, `${label} must be ISO-8601 with TZ offset: ${value}`);
  const ms = Date.parse(value);
  assert.ok(Number.isFinite(ms), `${label} must parse to a finite date: ${value}`);
  return ms;
}

export function assertUtcIso8601(value, label = 'timestamp') {
  assert.equal(typeof value, 'string', `${label} must be a string, got ${typeof value}`);
  assert.match(value, UTC_Z_RE, `${label} must be UTC ISO-8601 ending in Z: ${value}`);
  const ms = Date.parse(value);
  assert.ok(Number.isFinite(ms), `${label} must parse to a finite date: ${value}`);
  return ms;
}

export function assertUuid(value, label = 'id') {
  assert.equal(typeof value, 'string', `${label} must be string`);
  assert.match(value, UUID_V4_LIKE_RE, `${label} must be a UUID, got: ${value}`);
}

export function assertSuccessEnvelope(res, expectedStatus = 200) {
  const allowed = Array.isArray(expectedStatus) ? expectedStatus : [expectedStatus];
  assert.ok(
    allowed.includes(res.status),
    `Expected HTTP ${allowed.join('/')} but got ${res.status}: ${res.text}`,
  );
  assert.ok(res.json && typeof res.json === 'object', `Response body must be JSON: ${res.text}`);
  assert.equal(res.json.success, true, `Expected success=true: ${res.text}`);
  assert.ok('data' in res.json, `Envelope missing "data" field: ${res.text}`);
  assertIso8601WithTz(res.json.timestamp, 'envelope.timestamp');
  return res.json.data;
}

export function assertErrorEnvelope(
  res,
  allowedStatuses,
  expectedErrorCode,
  expectedPathPrefix,
) {
  const allowed = Array.isArray(allowedStatuses) ? allowedStatuses : [allowedStatuses];
  assert.ok(
    allowed.includes(res.status),
    `Expected error status ${allowed.join('/')} but got ${res.status}: ${res.text}`,
  );
  assert.ok(res.json && typeof res.json === 'object', `Error body must be JSON: ${res.text}`);
  assert.equal(res.json.success, false, `Expected success=false: ${res.text}`);
  assert.equal(res.json.statusCode, res.status, `Envelope statusCode mismatch: ${res.text}`);
  if (expectedErrorCode !== undefined && expectedErrorCode !== null) {
    const allowedCodes = Array.isArray(expectedErrorCode)
      ? expectedErrorCode
      : [expectedErrorCode];
    assert.ok(
      allowedCodes.includes(res.json.errorCode),
      `Expected errorCode in [${allowedCodes.join(', ')}] but got "${res.json.errorCode}" (${res.text})`,
    );
  }
  assert.ok(
    res.json.message !== undefined && String(res.json.message).trim().length > 0,
    `Error envelope must contain non-empty message: ${res.text}`,
  );
  assertIso8601WithTz(res.json.timestamp, 'error.timestamp');
  if (expectedPathPrefix) {
    assert.equal(typeof res.json.path, 'string', `Error envelope missing path: ${res.text}`);
    assert.ok(
      res.json.path.startsWith(expectedPathPrefix),
      `Expected error.path to start with "${expectedPathPrefix}", got "${res.json.path}"`,
    );
  }
  return res.json;
}

export function assertYoutubeContainerContract(data) {
  assert.ok(data && typeof data === 'object', 'YouTube payload must be an object');
  assert.equal(
    data.governanceRole,
    'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
    `Expected governanceRole=DYNAMIC_SOCIAL_FRESHNESS_LAYER, got ${data.governanceRole}`,
  );
  assert.equal(
    data.notPrimaryFactualCorpus,
    true,
    'notPrimaryFactualCorpus must be true',
  );
  assert.equal(
    data.realtimeSlaMaxLatencyMs,
    300000,
    'realtimeSlaMaxLatencyMs must be 300000 (5 minutes)',
  );
  assertUtcIso8601(data.serverDeliveredAt, 'serverDeliveredAt');
  assert.ok(Array.isArray(data.items), 'items must be an array');
}

export function assertYoutubeFiveFields(
  item,
  expectedScope,
  { maxIngestLatencyMs = null } = {},
) {
  assert.ok(item && typeof item === 'object', 'YouTube item must be an object');
  assert.ok('placeId' in item, 'YouTube item missing mandated field "placeId"');
  if (expectedScope === 'CITY') {
    assert.equal(item.placeId, null, 'CITY-scoped YouTube item must have placeId === null');
  } else if (expectedScope === 'POI') {
    assertUuid(item.placeId, 'item.placeId');
  }
  if (expectedScope) {
    assert.equal(item.scope, expectedScope, `Expected item.scope="${expectedScope}"`);
  }
  assert.equal(item.source, 'youtube', `Expected item.source="youtube", got "${item.source}"`);
  const publishedMs = assertUtcIso8601(item.publishedAt, 'item.publishedAt');
  const receivedMs = assertUtcIso8601(item.receivedAt, 'item.receivedAt');
  const updatedMs = assertUtcIso8601(item.updatedAt, 'item.updatedAt');
  assert.ok(
    typeof item.ingestLatencyMs === 'number' && item.ingestLatencyMs >= 0,
    `ingestLatencyMs must be >= 0, got ${item.ingestLatencyMs}`,
  );
  if (maxIngestLatencyMs !== null) {
    assert.ok(
      item.ingestLatencyMs <= maxIngestLatencyMs,
      `ingestLatencyMs=${item.ingestLatencyMs} exceeded SLA max ${maxIngestLatencyMs}ms`,
    );
  }
  return { publishedMs, receivedMs, updatedMs };
}
