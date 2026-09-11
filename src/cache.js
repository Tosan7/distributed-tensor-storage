require('dotenv').config();
const Redis = require('ioredis');

// Connect to the Redis container
const redis = new Redis({
  host: process.env.REDIS_HOST || 'localhost',
  port: parseInt(process.env.REDIS_PORT, 10) || 6379,
  maxRetriesPerRequest: 3,
  retryStrategy(times) {
    const delay = Math.min(times * 50, 2000);
    return delay; // Exponential backoff retry
  },
});

// Event listeners for connection diagnostics
redis.on('connect', () => {
  console.log('[REDIS] Connected to Redis cache successfully');
});

redis.on('error', (err) => {
  console.error('[REDIS ERROR] Redis connection error:', err.message);
});

/**
 * Cache-Aside Helper: Get raw binary tensor chunk from Redis
 * Uses getBuffer to prevent string/UTF-8 corruption of float arrays!
 */
const getChunk = async (chunkHash) => {
  const key = `chunk:${chunkHash}`;
  // Returns a raw Node.js Buffer or null
  return await redis.getBuffer(key);
};

/**
 * Cache-Aside Helper: Store raw binary tensor chunk in Redis with TTL
 * Default TTL: 3600 seconds (1 hour)
 */
const setChunk = async (chunkHash, chunkBuffer, ttlSeconds = 3600) => {
  const key = `chunk:${chunkHash}`;
  await redis.set(key, chunkBuffer, 'EX', ttlSeconds);
};

module.exports = {
  redis,
  getChunk,
  setChunk,
};