const { getChunk, setChunk, redis } = require('./src/cache');

async function test() {
  const fakeHash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
  
  // Create a simulated 4-byte binary buffer: [0xDE, 0xAD, 0xBE, 0xEF]
  const fakeTensorBytes = Buffer.from([0xDE, 0xAD, 0xBE, 0xEF]);

  console.log('Writing raw binary chunk to Redis cache...');
  await setChunk(fakeHash, fakeTensorBytes, 60); // 60 seconds TTL

  console.log('Reading chunk back from Redis cache...');
  const retrievedBuffer = await getChunk(fakeHash);

  console.log('Retrieved buffer:', retrievedBuffer);
  console.log('Bytes match perfectly?', fakeTensorBytes.equals(retrievedBuffer));

  await redis.quit(); // Disconnect cleanly
  process.exit(0);
}

test();