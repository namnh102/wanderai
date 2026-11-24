import crypto from 'node:crypto';

function escapeXml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

export function buildYoutubeAtomFeed(entries) {
  const entryXml = entries
    .map((entry) => {
      const geoXml =
        typeof entry.latitude === 'number' && typeof entry.longitude === 'number'
          ? `    <georss:point>${entry.latitude} ${entry.longitude}</georss:point>\n`
          : '';
      const updatedXml = entry.sourceUpdatedAt
        ? `    <updated>${escapeXml(entry.sourceUpdatedAt)}</updated>\n`
        : '';
      const descXml = entry.description
        ? `    <media:description>${escapeXml(entry.description)}</media:description>\n`
        : '';
      const authorName = entry.channelTitle ?? 'WanderAI Hạ Long Travel';
      return [
        '  <entry>',
        `    <id>yt:video:${escapeXml(entry.videoId)}</id>`,
        `    <yt:videoId>${escapeXml(entry.videoId)}</yt:videoId>`,
        `    <yt:channelId>${escapeXml(entry.channelId)}</yt:channelId>`,
        `    <title>${escapeXml(entry.title)}</title>`,
        '    <author>',
        `      <name>${escapeXml(authorName)}</name>`,
        '    </author>',
        `    <published>${escapeXml(entry.publishedAt)}</published>`,
        updatedXml ? updatedXml.trimEnd() : null,
        descXml ? descXml.trimEnd() : null,
        geoXml ? geoXml.trimEnd() : null,
        '  </entry>',
      ]
        .filter(Boolean)
        .join('\n');
    })
    .join('\n');

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"',
    '      xmlns:media="http://search.yahoo.com/mrss/"',
    '      xmlns:georss="http://www.georss.org/georss"',
    '      xmlns="http://www.w3.org/2005/Atom">',
    '  <title>YouTube video feed</title>',
    entryXml,
    '</feed>',
    '',
  ].join('\n');
}

export function signWebSubBody(rawXml, secret, algorithm = 'sha256') {
  if (!secret) return undefined;
  const hex = crypto
    .createHmac(algorithm, secret)
    .update(rawXml, 'utf8')
    .digest('hex');
  return `${algorithm}=${hex}`;
}

export function isoWithOffsetSeconds(offsetMsFromNow, tzOffset = '+07:00') {
  const targetMs = Date.now() + offsetMsFromNow;
  if (tzOffset === 'Z') {
    return new Date(targetMs).toISOString();
  }
  const match = tzOffset.match(/^([+-])(\d{2}):(\d{2})$/);
  if (!match) {
    return new Date(targetMs).toISOString();
  }
  const sign = match[1] === '-' ? -1 : 1;
  const offsetMinutes = sign * (Number(match[2]) * 60 + Number(match[3]));
  const local = new Date(targetMs + offsetMinutes * 60000);
  const pad = (n, w = 2) => String(n).padStart(w, '0');
  return (
    `${local.getUTCFullYear()}-${pad(local.getUTCMonth() + 1)}-${pad(local.getUTCDate())}` +
    `T${pad(local.getUTCHours())}:${pad(local.getUTCMinutes())}:${pad(local.getUTCSeconds())}` +
    `.${pad(local.getUTCMilliseconds(), 3)}${tzOffset}`
  );
}

export function buildGroundedThapDongHoEvent(overrides = {}) {
  return {
    eventId: `evt-${crypto.randomUUID()}`,
    videoId: 'dQw4w9WgXcQ',
    channelId: 'UC_Halong_Travel_01',
    channelTitle: 'Hạ Long Review',
    title: 'Check-in Tháp Đồng Hồ Hạ Long buổi tối rực rỡ',
    description:
      'Dạo quanh Tháp Đồng Hồ tại trung tâm thành phố Hạ Long, Quảng Ninh. Nguồn OSM https://www.openstreetmap.org/way/674228542',
    tags: ['Tháp Đồng Hồ', 'Hạ Long', 'Quảng Ninh'],
    publishedAt: isoWithOffsetSeconds(-45_000, '+07:00'),
    latitude: 20.9516105,
    longitude: 107.0851999,
    candidatePlaceId: '65562a67-84ff-44a0-990d-31917a2a9bd0',
    ...overrides,
  };
}
