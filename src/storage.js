require('dotenv').config();
const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const crypto = require('crypto');
const { pipeline } = require('stream/promises');

// Base directory where raw chunk files are saved
const BASE_STORAGE_DIR = path.resolve(process.env.STORAGE_DIR || './storage_data');

/**
 * Computes sharded file path based on SHA-256 hash:
 * e.g., 'e3b0c442...' -> 'storage_data/blobs/e3/b0/e3b0c442....bin'
 */
const getBlobPath = (chunkHash) => {
  const prefix1 = chunkHash.slice(0, 2);
  const prefix2 = chunkHash.slice(2, 4);
  return path.join(BASE_STORAGE_DIR, 'blobs', prefix1, prefix2, `${chunkHash}.bin`);
};

/**
 * Checks if a chunk file already exists on physical disk
 */
const blobExists = async (chunkHash) => {
  try {
    const filePath = getBlobPath(chunkHash);
    await fsp.access(filePath);
    return true; // File exists
  } catch {
    return false; // File does not exist
  }
};

/**
 * Returns a readable stream for a chunk from disk (Zero RAM buffering)
 */
const readBlobStream = (chunkHash) => {
  const filePath = getBlobPath(chunkHash);
  return fs.createReadStream(filePath);
};

/**
 * Streams incoming bytes to a temp file while calculating SHA-256 in real-time.
 * If the calculated hash matches the expected hash -> moves to permanent sharded path.
 * If mismatch -> deletes temp file and throws error!
 */
const writeBlobStream = async (expectedHash, inputStream) => {
  // Ensure storage directories exist
  const finalPath = getBlobPath(expectedHash);
  const finalDir = path.dirname(finalPath);
  await fsp.mkdir(finalDir, { recursive: true });

  const tempPath = path.join(BASE_STORAGE_DIR, `temp_${expectedHash}_${Date.now()}.tmp`);
  await fsp.mkdir(BASE_STORAGE_DIR, { recursive: true });

  const fileWriteStream = fs.createWriteStream(tempPath);
  const hashStream = crypto.createHash('sha256');

  // Intercept bytes: calculate hash AND write to disk at the same time
  let totalBytes = 0;
  inputStream.on('data', (chunk) => {
    totalBytes += chunk.length;
    hashStream.update(chunk);
  });

  try {
    // Pipe input stream to file stream safely with backpressure handling
    await pipeline(inputStream, fileWriteStream);

    const calculatedHash = hashStream.digest('hex');

    // Integrity validation: Did any bit corrupt in transit?
    if (calculatedHash !== expectedHash) {
      // Data corruption detected! Clean up temp file
      await fsp.unlink(tempPath).catch(() => {});
      const error = new Error(`Checksum mismatch! Expected ${expectedHash}, calculated ${calculatedHash}`);
      error.statusCode = 422; // Unprocessable Entity
      throw error;
    }

    // Hash matches! Atomically move temp file to permanent CAS location
    await fsp.rename(tempPath, finalPath);

    return {
      chunkHash: expectedHash,
      byteLength: totalBytes,
      storagePath: finalPath,
    };
  } catch (err) {
    // Ensure temp file is cleaned up on any failure
    await fsp.unlink(tempPath).catch(() => {});
    throw err;
  }
};

module.exports = {
  getBlobPath,
  blobExists,
  readBlobStream,
  writeBlobStream,
};