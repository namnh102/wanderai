import http from 'node:http';
import { HttpClient } from './http_client.mjs';

/**
 * Ephemeral local HTTP reverse proxy for injecting real HTTP 503 faults
 * against either the self-test mock server or a live backend (--base-url),
 * followed by genuine HTTP retry forwarding.
 */
export async function withFaultProxy(upstreamBaseUrl, rules, fn) {
  if (!upstreamBaseUrl) {
    throw new Error('withFaultProxy requires a non-empty upstreamBaseUrl');
  }
  const activeRules = (rules || []).map((r) => ({
    method: String(r.method || 'GET').toUpperCase(),
    pathPrefix: String(r.pathPrefix || '/'),
    status: Number(r.status || 503),
    errorCode: r.errorCode || 'SERVICE_UNAVAILABLE',
    message: r.message || 'Simulated transient upstream 503',
    remaining: Number.isFinite(r.remaining) ? r.remaining : 1,
  }));

  let interceptedCount = 0;
  let forwardedCount = 0;

  const server = http.createServer(async (req, res) => {
    try {
      const reqUrl = new URL(req.url || '/', 'http://127.0.0.1');
      const method = String(req.method || 'GET').toUpperCase();
      const chunks = [];
      for await (const chunk of req) {
        chunks.push(chunk);
      }
      const bodyBuf = Buffer.concat(chunks);

      const matchedRule = activeRules.find(
        (rule) =>
          rule.remaining > 0 &&
          rule.method === method &&
          reqUrl.pathname.startsWith(rule.pathPrefix),
      );

      if (matchedRule) {
        matchedRule.remaining -= 1;
        interceptedCount += 1;
        const payload = JSON.stringify({
          success: false,
          statusCode: matchedRule.status,
          errorCode: matchedRule.errorCode,
          message: matchedRule.message,
          timestamp: new Date().toISOString(),
          path: reqUrl.pathname + reqUrl.search,
        });
        res.writeHead(matchedRule.status, {
          'Content-Type': 'application/json; charset=utf-8',
          'Content-Length': Buffer.byteLength(payload),
        });
        res.end(payload);
        return;
      }

      forwardedCount += 1;
      const forwardHeaders = {};
      for (const [k, v] of Object.entries(req.headers)) {
        const lower = k.toLowerCase();
        if (lower === 'host' || lower === 'content-length' || lower === 'connection') {
          continue;
        }
        if (v !== undefined) {
          forwardHeaders[k] = Array.isArray(v) ? v.join(', ') : String(v);
        }
      }

      const upstreamUrl = new URL(reqUrl.pathname + reqUrl.search, upstreamBaseUrl);
      const fetchOpts = {
        method,
        headers: forwardHeaders,
      };
      if (method !== 'GET' && method !== 'HEAD' && bodyBuf.length > 0) {
        fetchOpts.body = bodyBuf;
      }

      const upstreamRes = await fetch(upstreamUrl, fetchOpts);
      const upstreamBody = Buffer.from(await upstreamRes.arrayBuffer());
      const respHeaders = {
        'Content-Length': upstreamBody.length,
      };
      const ct = upstreamRes.headers.get('content-type');
      if (ct) {
        respHeaders['Content-Type'] = ct;
      }
      res.writeHead(upstreamRes.status, respHeaders);
      res.end(upstreamBody);
    } catch (err) {
      const errBody = JSON.stringify({
        success: false,
        statusCode: 502,
        errorCode: 'PROXY_UPSTREAM_ERROR',
        message: err?.message || 'Fault proxy upstream error',
        timestamp: new Date().toISOString(),
        path: req.url || '/',
      });
      res.writeHead(502, {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Length': Buffer.byteLength(errBody),
      });
      res.end(errBody);
    }
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const addr = server.address();
  const proxyBaseUrl = `http://127.0.0.1:${addr.port}`;
  const proxyClient = new HttpClient(proxyBaseUrl);

  try {
    return await fn({
      proxyBaseUrl,
      proxyClient,
      getStats: () => ({ interceptedCount, forwardedCount }),
    });
  } finally {
    await new Promise((resolve, reject) =>
      server.close((err) => (err ? reject(err) : resolve())),
    );
  }
}
