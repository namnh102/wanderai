import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { HttpClient } from './http_client.mjs';
import { assertSuccessEnvelope } from './assertions.mjs';

export const EXPECTED_FREEZE_V2_SHA256 =
  'F7517938598E3923906763F8F31334A500EE88BC06232F2992D38E2FCB28A444';
export const EXPECTED_W07_KNOWLEDGE_SHA256 =
  '9B0ED36E060924057872A2E8FE9941940F7BC3455F2C9CAD21CDC9A9C1141FDA';

export function computeFileSha256(filePath) {
  assert.ok(fs.existsSync(filePath), `File does not exist for SHA-256 check: ${filePath}`);
  const hash = crypto.createHash('sha256');
  const buf = fs.readFileSync(filePath);
  hash.update(buf);
  return hash.digest('hex').toUpperCase();
}

export function verifyFreezeChecksum(repoRoot) {
  const freezePath = path.join(repoRoot, 'data', 'curated', 'gomate_places_freeze_v2.json');
  const w07KnowledgePath = path.join(
    repoRoot,
    'data',
    'curated',
    'w07',
    'poi_knowledge_acquired_v1.jsonl',
  );

  const actualFreezeSha = computeFileSha256(freezePath);
  assert.equal(
    actualFreezeSha,
    EXPECTED_FREEZE_V2_SHA256,
    `W07 freeze checksum mismatch for ${freezePath}`,
  );

  const actualKnowledgeSha = computeFileSha256(w07KnowledgePath);
  assert.equal(
    actualKnowledgeSha,
    EXPECTED_W07_KNOWLEDGE_SHA256,
    `W07 knowledge checksum mismatch for ${w07KnowledgePath}`,
  );

  return {
    freezePath,
    freezeSha256: actualFreezeSha,
    w07KnowledgePath,
    w07KnowledgeSha256: actualKnowledgeSha,
  };
}

export function verifyProtectedPathsClean(
  repoRoot,
  w07PrepDir,
  { requireW07Prep = false } = {},
) {
  const gitCheck = spawnSync(
    'git',
    [
      '-C',
      repoRoot,
      'status',
      '--porcelain',
      '--',
      'data/curated/gomate_places_freeze_v2.json',
      'data/curated/w07',
    ],
    { encoding: 'utf8' },
  );
  assert.equal(gitCheck.status, 0, `git status failed: ${gitCheck.stderr}`);
  const dirtyLines = gitCheck.stdout
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  assert.equal(
    dirtyLines.length,
    0,
    `Protected W07 paths must have zero modifications: ${dirtyLines.join('; ')}`,
  );

  const gitDiff = spawnSync(
    'git',
    [
      '-C',
      repoRoot,
      'diff',
      '--name-only',
      '--',
      'data/curated/gomate_places_freeze_v2.json',
      'data/curated/w07',
    ],
    { encoding: 'utf8' },
  );
  assert.equal(gitDiff.status, 0, `git diff failed: ${gitDiff.stderr}`);
  assert.equal(gitDiff.stdout.trim(), '', `Expected empty git diff on W07 paths`);

  if (requireW07Prep) {
    assert.ok(
      w07PrepDir && fs.existsSync(w07PrepDir),
      `Required w07_offline_retrieval_prep missing at ${w07PrepDir}`,
    );
  }

  let w07PrepVerified = false;
  let w07PrepEntries = [];
  if (w07PrepDir && fs.existsSync(w07PrepDir)) {
    w07PrepEntries = fs.readdirSync(w07PrepDir);
    assert.ok(
      w07PrepEntries.length > 0,
      `w07_offline_retrieval_prep exists at ${w07PrepDir} but is empty`,
    );
    const hasExpectedMarker =
      w07PrepEntries.includes('authorities_v0_2_2_tech_freeze') ||
      w07PrepEntries.includes('pyproject.toml');
    assert.ok(
      hasExpectedMarker,
      `w07_offline_retrieval_prep missing expected marker files: ${w07PrepEntries.join(', ')}`,
    );
    if (fs.existsSync(path.join(w07PrepDir, '.git'))) {
      const prepGit = spawnSync('git', ['-C', w07PrepDir, 'status', '--porcelain'], {
        encoding: 'utf8',
      });
      assert.equal(prepGit.status, 0, `git status failed on ${w07PrepDir}: ${prepGit.stderr}`);
      const prepDirty = prepGit.stdout
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter(Boolean);
      assert.equal(
        prepDirty.length,
        0,
        `w07_offline_retrieval_prep must have zero modifications: ${prepDirty.join('; ')}`,
      );
    }
    w07PrepVerified = true;
  }

  return {
    dirtyLines,
    w07PrepDir,
    w07PrepVerified,
    w07PrepEntriesCount: w07PrepEntries.length,
  };
}

export async function fetchDbStats(client, cfg) {
  if (cfg.mode === 'self-test') {
    return assertSuccessEnvelope(await client.get('/_test/db-stats'), 200);
  }
  const dbStatsUrl = process.env.E2E_DB_STATS_URL;
  if (!dbStatsUrl) {
    throw new Error(
      'Live mode R4 DB isolation test requires E2E_DB_STATS_URL returning { documentsCount, placeSourcesCount }',
    );
  }
  const res = await new HttpClient(dbStatsUrl).get('');
  assert.equal(
    res.status,
    200,
    `E2E_DB_STATS_URL failed (${res.status}): ${res.text}`,
  );
  const stats =
    res.json?.success === true && res.json?.data ? res.json.data : res.json;
  assert.ok(
    stats && typeof stats === 'object',
    `E2E_DB_STATS_URL must return JSON object: ${res.text}`,
  );
  assert.equal(
    typeof stats.documentsCount,
    'number',
    `E2E_DB_STATS_URL missing numeric documentsCount: ${res.text}`,
  );
  assert.equal(
    typeof stats.placeSourcesCount,
    'number',
    `E2E_DB_STATS_URL missing numeric placeSourcesCount: ${res.text}`,
  );
  return stats;
}

export function verifyFactualPlaceUnchanged(beforePlace, afterPlace) {
  assert.ok(beforePlace && afterPlace, 'Both beforePlace and afterPlace must exist');
  assert.equal(afterPlace.id, beforePlace.id);
  assert.equal(afterPlace.name, beforePlace.name);
  assert.equal(afterPlace.latitude, beforePlace.latitude);
  assert.equal(afterPlace.longitude, beforePlace.longitude);
  assert.equal(afterPlace.address ?? null, beforePlace.address ?? null);
  assert.equal(afterPlace.description ?? null, beforePlace.description ?? null);
  assert.deepEqual(afterPlace.source ?? null, beforePlace.source ?? null);

  const beforeSources = Array.isArray(beforePlace.placeSources)
    ? beforePlace.placeSources
    : [];
  const afterSources = Array.isArray(afterPlace.placeSources)
    ? afterPlace.placeSources
    : [];
  assert.equal(
    afterSources.length,
    beforeSources.length,
    'placeSources count must remain identical before and after YouTube ingestion',
  );
  assert.ok(
    !afterSources.some((s) => String(s.sourceName || '').toLowerCase() === 'youtube'),
    'youtube must NEVER be written into place_sources',
  );
}

export function verifyDbStatsIsolation(beforeStats, afterStats) {
  assert.ok(beforeStats && afterStats, 'DB stats snapshots required');
  assert.equal(
    afterStats.documentsCount,
    beforeStats.documentsCount,
    `documents table count changed (${beforeStats.documentsCount} -> ${afterStats.documentsCount})`,
  );
  assert.equal(
    afterStats.placeSourcesCount,
    beforeStats.placeSourcesCount,
    `place_sources table count changed (${beforeStats.placeSourcesCount} -> ${afterStats.placeSourcesCount})`,
  );
}
