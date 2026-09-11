import hashlib
import time
import urllib.request
import numpy as np

# Configuration
GATEWAY_URL = "http://localhost:3000/api/v1/chunks"
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB chunk size


def upload_chunk(chunk_bytes: bytes, chunk_hash: str):
    """Uploads a single binary chunk to the Node.js Storage Gateway via HTTP PUT"""
    url = f"{GATEWAY_URL}/{chunk_hash}"
    req = urllib.request.Request(
        url,
        data=chunk_bytes,
        headers={"Content-Type": "application/octet-stream"},
        method="PUT",
    )
    with urllib.request.urlopen(req) as response:
        return response.status


def download_chunk(chunk_hash: str) -> tuple[bytes, str]:
    """Downloads a binary chunk and inspects the X-Cache header"""
    url = f"{GATEWAY_URL}/{chunk_hash}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as response:
        cache_header = response.headers.get("X-Cache", "UNKNOWN")
        data = response.read()
        return data, cache_header


def main():
    print("=" * 60)
    print("  NVIDIA DL Validation Framework: Tensor Integrity Test")
    print("=" * 60)

    # 1. Generate synthetic deep learning tensor (FP32 weight matrix)
    # Shape: 2048 x 2048 floats = 4,194,304 floats * 4 bytes each = 16,777,216 bytes (16 MB)
    print("\n[1] Generating 16 MB synthetic FP32 tensor (2048x2048)...")
    original_weights = np.random.randn(2048, 2048).astype(np.float32)
    raw_bytes = original_weights.tobytes()
    total_bytes = len(raw_bytes)
    print(f"    Tensor memory size: {total_bytes / (1024 * 1024):.2f} MB")

    # 2. Slice into 4 MB chunks and compute SHA-256 hashes
    print(f"\n[2] Slicing tensor into {CHUNK_SIZE // (1024 * 1024)} MB chunks...")
    chunks = []
    for offset in range(0, total_bytes, CHUNK_SIZE):
        chunk_slice = raw_bytes[offset : offset + CHUNK_SIZE]
        chunk_hash = hashlib.sha256(chunk_slice).hexdigest()
        chunks.append((chunk_hash, chunk_slice))
        print(f"    Chunk {len(chunks)-1}: Hash={chunk_hash[:16]}... Size={len(chunk_slice)} bytes")

    # 3. Stream chunks to the Node.js Storage Gateway
    print(f"\n[3] Uploading {len(chunks)} chunks to Storage Gateway...")
    for idx, (c_hash, c_bytes) in enumerate(chunks):
        t0 = time.time()
        status = upload_chunk(c_bytes, c_hash)
        upload_time_ms = (time.time() - t0) * 1000
        print(f"    Uploaded chunk {idx} -> Status: {status} ({upload_time_ms:.1f}ms)")

    # 4. Download chunks back from Gateway
    print(f"\n[4] Downloading chunks back from Gateway...")
    downloaded_byte_segments = []
    for idx, (c_hash, _) in enumerate(chunks):
        t0 = time.time()
        chunk_data, cache_state = download_chunk(c_hash)
        download_time_ms = (time.time() - t0) * 1000
        downloaded_byte_segments.append(chunk_data)
        print(f"    Downloaded chunk {idx} -> Cache: [{cache_state}] ({download_time_ms:.1f}ms)")

    # 5. Reassemble binary stream and reconstruct NumPy tensor
    print(f"\n[5] Reassembling binary stream into NumPy array...")
    reassembled_bytes = b"".join(downloaded_byte_segments)
    reconstructed_weights = np.frombuffer(reassembled_bytes, dtype=np.float32).reshape(2048, 2048)

    # 6. MATHEMATICAL VERIFICATION: Bit-for-bit assertion
    print(f"\n[6] Asserting bit-for-bit mathematical equality...")
    are_identical = np.array_equal(original_weights, reconstructed_weights)

    if are_identical:
        print("    [SUCCESS] Weights are BIT-FOR-BIT IDENTICAL!")
        print("    Original shape:", original_weights.shape, "Dtype:", original_weights.dtype)
        print("    Reconstructed shape:", reconstructed_weights.shape, "Dtype:", reconstructed_weights.dtype)
    else:
        print("    [FAILURE] Mathematical mismatch detected! Tensor weights were corrupted.")
        exit(1)


if __name__ == "__main__":
    main()