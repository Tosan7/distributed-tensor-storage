const { Readable } = require('stream');
const crypto = require('crypto');
const { writeBlobStream, blobExists, readBlobStream } = require('./src/storage');

async function test() {
  console.log('--- TEST 1: Valid Chunk Upload ---');
  const content = 'Hello NVIDIA Storage Gateway! This is a test tensor chunk.';
  const validHash = crypto.createHash('sha256').update(content).digest('hex');

  // Create a stream from the string
  const stream1 = Readable.from([content]);
  const result = await writeBlobStream(validHash, stream1);
  console.log('Chunk written successfully to:', result.storagePath);
  console.log('File exists on disk?', await blobExists(validHash));

  console.log('\n--- TEST 2: Corrupted Chunk Detection ---');
  const fakeCorruptHash = 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff';
  const stream2 = Readable.from([content]); // content doesn't match fakeCorruptHash!

  try {
    await writeBlobStream(fakeCorruptHash, stream2);
    console.error('ERROR: It should have failed!');
  } catch (err) {
    console.log('Successfully caught corruption!');
    console.log('Error message:', err.message);
  }

  process.exit(0);
}

test();