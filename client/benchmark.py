import concurrent.futures
import json
import time
import urllib.request
import numpy as np

GATEWAY_URL = "http://127.0.0.1:3000/api/v1/chunks"
NUM_WORKERS = 20  # Simulates 20 concurrent GPU training clients
REQUESTS_PER_WORKER = 5  # Each worker performs 5 chunk pulls (100 total requests)


def fetch_chunk(chunk_hash: str) -> tuple[float, int, str]:
    """Worker task: Fetches chunk, measures latency in ms, bytes, and cache state"""
    start_time = time.time()
    url = f"{GATEWAY_URL}/{chunk_hash}"
    req = urllib.request.Request(url, method="GET")

    with urllib.request.urlopen(req) as response:
        cache_state = response.headers.get("X-Cache", "UNKNOWN")
        data = response.read()
        latency_ms = (time.time() - start_time) * 1000
        return latency_ms, len(data), cache_state


def run_benchmark():
    print("=" * 65)
    print(f"  NVIDIA Storage Gateway: {NUM_WORKERS}-Worker Concurrency Benchmark")
    print("=" * 65)

    # 1. Prepare a test chunk in the Gateway (4 MB)
    print("\n[1] Seeding test 4 MB chunk to Gateway...")
    test_tensor = np.random.randn(1024, 1024).astype(np.float32)  # 4 MB
    chunk_bytes = test_tensor.tobytes()
    import hashlib

    test_hash = hashlib.sha256(chunk_bytes).hexdigest()

    # Upload test chunk
    upload_req = urllib.request.Request(
        f"{GATEWAY_URL}/{test_hash}",
        data=chunk_bytes,
        headers={"Content-Type": "application/octet-stream"},
        method="PUT",
    )
    with urllib.request.urlopen(upload_req) as resp:
        print(f"    Seeded test chunk -> Hash: {test_hash[:16]}... Status: {resp.status}")

    # 2. Launch concurrent workers using ThreadPoolExecutor
    total_requests = NUM_WORKERS * REQUESTS_PER_WORKER
    print(
        f"\n[2] Launching {NUM_WORKERS} concurrent worker threads ({total_requests} total requests)..."
    )

    latencies = []
    total_bytes_transferred = 0
    cache_hits = 0

    benchmark_start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        # Submit all worker tasks simultaneously
        futures = [
            executor.submit(fetch_chunk, test_hash)
            for _ in range(total_requests)
        ]

        for future in concurrent.futures.as_completed(futures):
            lat_ms, byte_count, cache_state = future.result()
            latencies.append(lat_ms)
            total_bytes_transferred += byte_count
            if cache_state == "HIT":
                cache_hits += 1

    total_time_sec = time.time() - benchmark_start

    # 3. Calculate Performance Metrics
    throughput_mb_s = (total_bytes_transferred / (1024 * 1024)) / total_time_sec
    p50_latency = np.percentile(latencies, 50)
    p95_latency = np.percentile(latencies, 95)
    p99_latency = np.percentile(latencies, 99)
    hit_rate = (cache_hits / total_requests) * 100

    # 4. Print Executive SLA Report
    print("\n" + "=" * 65)
    print("                PERFORMANCE BENCHMARK REPORT")
    print("=" * 65)
    print(
        f"  Concurrent Worker Nodes:  {NUM_WORKERS} threads ({REQUESTS_PER_WORKER} reqs/worker)"
    )
    print(f"  Total Requests Completed: {total_requests}")
    print(f"  Total Data Transferred:   {total_bytes_transferred / (1024 * 1024):.2f} MB")
    print(f"  Total Benchmark Time:     {total_time_sec:.2f} seconds")
    print("-" * 65)
    print(f"  ⚡ Throughput:             {throughput_mb_s:.2f} MB/s")
    print(f"  🎯 Cache Hit Ratio:       {hit_rate:.1f}%")
    print(f"  ⏱️  P50 Latency (Median):  {p50_latency:.2f} ms")
    print(f"  ⏱️  P95 Latency:          {p95_latency:.2f} ms")
    print(f"  ⏱️  P99 Latency (Tail):    {p99_latency:.2f} ms")
    print("=" * 65)

    # 5. Save JSON report for Jenkins CI/CD Artifact Archiving
    report_data = {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "concurrent_workers": NUM_WORKERS,
        "total_requests": total_requests,
        "throughput_mb_s": round(throughput_mb_s, 2),
        "cache_hit_rate_pct": round(hit_rate, 2),
        "latency_p50_ms": round(p50_latency, 2),
        "latency_p95_ms": round(p95_latency, 2),
        "latency_p99_ms": round(p99_latency, 2),
    }

    with open("benchmark_report.json", "w") as f:
        json.dump(report_data, f, indent=2)
    print("\n[SUCCESS] Benchmark report saved to 'benchmark_report.json'")


if __name__ == "__main__":
    run_benchmark()