require('dotenv').config();
const fastify = require('fastify')({
  logger: true,
  // Allow unlimited body size for tensor chunks
  bodyLimit: 100 * 1024 * 1024, // 100 MB max per chunk
});
const sensible = require('@fastify/sensible');
fastify.register(sensible);

const { pool, query } = require('./db');
const { getChunk, setChunk } = require('./cache');
const { blobExists, readBlobStream, writeBlobStream, getBlobPath } = require('./storage');
const fs = require('fs/promises');

// Enable raw binary streaming for PUT /chunks/:hash
// This passes the raw incoming network stream directly to our handler without buffering in RAM!
fastify.addContentTypeParser('application/octet-stream', (req, payload, done) => {
  done(null, payload);
});

// ============================================================================
// 1. Health Check Route
// ============================================================================
fastify.get('/health', async (request, reply) => {
  return { status: 'healthy', timestamp: new Date().toISOString() };
});

// ============================================================================
// 2. Chunk Upload (Content-Addressable Storage)
// ============================================================================
fastify.put('/api/v1/chunks/:hash', async (request, reply) => {
  const { hash } = request.params;
  const clientIp = request.ip;
  const startTime = Date.now();

  // Deduplication check: If chunk is already on disk, skip writing!
  const alreadyOnDisk = await blobExists(hash);
  if (alreadyOnDisk) {
    return reply.code(200).send({
      status: 'exists',
      chunkHash: hash,
      message: 'Chunk already exists (deduplicated)',
    });
  }

  // Stream raw request payload directly through SHA-256 verifier to disk
  try {
    const stream = request.raw;
    const result = await writeBlobStream(hash, stream);
    const duration = Date.now() - startTime;

    // Asynchronously warm up the Redis cache with the newly uploaded chunk
    const fileBytes = await fs.readFile(result.storagePath);
    await setChunk(hash, fileBytes, 3600);

    // Record WRITE telemetry in PostgreSQL
    await query(
      `INSERT INTO access_telemetry (client_ip, chunk_hash, operation, response_time_ms, cache_hit, bytes_transferred)
       VALUES ($1, $2, 'WRITE', $3, FALSE, $4)`,
      [clientIp, hash, duration, result.byteLength]
    );

    return reply.code(201).send({
      status: 'created',
      chunkHash: hash,
      bytes: result.byteLength,
      durationMs: duration,
    });
  } catch (err) {
    if (err.statusCode === 422) {
      return reply.code(422).send({ error: 'Corruption detected', message: err.message });
    }
    throw err;
  }
});

// ============================================================================
// 3. Chunk Download (Cache-Aside Flow: Redis -> Disk -> SQL Telemetry)
// ============================================================================
fastify.get('/api/v1/chunks/:hash', async (request, reply) => {
  const { hash } = request.params;
  const clientIp = request.ip;
  const startTime = Date.now();

  // Step A: Check Redis (The Fast Lane)
  const cachedChunk = await getChunk(hash);

  if (cachedChunk) {
    const duration = Date.now() - startTime;
    // Asynchronously log CACHE HIT to PostgreSQL
    query(
      `INSERT INTO access_telemetry (client_ip, chunk_hash, operation, response_time_ms, cache_hit, bytes_transferred)
       VALUES ($1, $2, 'READ', $3, TRUE, $4)`,
      [clientIp, hash, duration, cachedChunk.length]
    ).catch((err) => fastify.log.error('Telemetry log failed', err));

    return reply
      .header('Content-Type', 'application/octet-stream')
      .header('X-Cache', 'HIT')
      .send(cachedChunk);
  }

  // Step B: Cache MISS -> Fetch from physical disk
  const exists = await blobExists(hash);
  if (!exists) {
    return reply.code(404).send({ error: 'Chunk not found' });
  }

  const duration = Date.now() - startTime;

  // Asynchronously populate Redis cache with TTL so future reads are Cache HITS!
  fs.readFile(getBlobPath(hash)).then((buf) => {
    setChunk(hash, buf, 3600).catch(() => {});
  });

  // Asynchronously log CACHE MISS to PostgreSQL
  query(
    `INSERT INTO access_telemetry (client_ip, chunk_hash, operation, response_time_ms, cache_hit, bytes_transferred)
     VALUES ($1, $2, 'READ', $3, FALSE, $4)`,
    [clientIp, hash, duration, 0]
  ).catch((err) => fastify.log.error('Telemetry log failed', err));

  // Stream directly from disk to client
  reply
    .header('Content-Type', 'application/octet-stream')
    .header('X-Cache', 'MISS');

  return reply.send(readBlobStream(hash));
});

// ============================================================================
// 4. Analytics Endpoint (Runs our analytical SQL query!)
// ============================================================================
fastify.get('/api/v1/analytics/cache-hit-ratio', async (request, reply) => {
  const result = await query(`
    SELECT 
      chunk_hash,
      COUNT(id) AS total_requests,
      COUNT(id) FILTER (WHERE cache_hit = TRUE) AS cache_hits,
      COUNT(id) FILTER (WHERE cache_hit = FALSE) AS cache_misses,
      ROUND(
        100.0 * COUNT(id) FILTER (WHERE cache_hit = TRUE) / NULLIF(COUNT(id), 0), 
        2
      ) AS cache_hit_percentage
    FROM access_telemetry
    WHERE operation = 'READ'
    GROUP BY chunk_hash;
  `);

  return { cache_stats: result.rows };
});

// ============================================================================
// Start Server
// ============================================================================
const start = async () => {
  const port = parseInt(process.env.PORT, 10) || 3000;
  const host = process.env.HOST || '0.0.0.0';

  try {
    await fastify.listen({ port, host });
    console.log(`\n🚀 NVIDIA Storage Gateway running on http://${host}:${port}`);
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
};

start();