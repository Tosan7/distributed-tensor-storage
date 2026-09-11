import hashlib
import os
import sys
import time
import psycopg2
import redis

# Configuration (matches our docker & .env setup)
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "user": "storage_admin",
    "password": "storage_password123",
    "dbname": "tensor_storage",
}

REDIS_CONFIG = {"host": "127.0.0.1", "port": 6379}
STORAGE_DIR = "./storage_data/blobs"


def check_database():
    """Diagnoses PostgreSQL connection, latency, and catalog integrity"""
    print("\n[1] Diagnosing Relational Metadata Database (PostgreSQL)...")
    start = time.time()
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=3)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM access_telemetry;")
        telemetry_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM artifact_chunks;")
        chunk_count = cur.fetchone()[0]

        latency_ms = (time.time() - start) * 1000
        conn.close()

        print(f"    ✅ PostgreSQL: HEALTHY (Latency: {latency_ms:.2f}ms)")
        print(f"       Total Telemetry Logs: {telemetry_count}")
        print(f"       Indexed Chunks in DB: {chunk_count}")
        return True
    except Exception as e:
        print(f"    ❌ PostgreSQL: DEGRADED/FAILED ({e})")
        return False


def check_redis():
    """Diagnoses Redis cache connection, memory footprint, and latency"""
    print("\n[2] Diagnosing In-Memory Cache (Redis)...")
    start = time.time()
    try:
        r = redis.Redis(**REDIS_CONFIG, socket_timeout=2)
        r.ping()
        latency_ms = (time.time() - start) * 1000

        info = r.info("memory")
        used_memory_human = info.get("used_memory_human", "N/A")
        total_keys = r.dbsize()

        print(f"    ✅ Redis Cache: HEALTHY (Latency: {latency_ms:.2f}ms)")
        print(f"       RAM Memory In-Use: {used_memory_human}")
        print(f"       Cached Hot Chunks: {total_keys}")
        return True
    except Exception as e:
        print(f"    ❌ Redis Cache: DEGRADED/FAILED ({e})")
        return False


def scan_for_bit_rot():
    """Scans physical disk blobs and verifies cryptographic SHA-256 integrity"""
    print("\n[3] Scanning Physical Storage for Bit-Rot & Silent Corruption...")
    if not os.path.exists(STORAGE_DIR):
        print("    ⚠️  No physical blob directory found yet (empty storage).")
        return True

    scanned = 0
    corrupted = 0
    total_bytes = 0

    for root, _, files in os.walk(STORAGE_DIR):
        for f in files:
            if f.endswith(".bin"):
                scanned += 1
                expected_hash = f.replace(".bin", "")
                full_path = os.path.join(root, f)

                # Read raw bytes from disk and calculate SHA-256
                hasher = hashlib.sha256()
                with open(full_path, "rb") as fh:
                    while chunk := fh.read(64 * 1024):
                        hasher.update(chunk)
                        total_bytes += len(chunk)

                calculated_hash = hasher.hexdigest()

                # Integrity check
                if calculated_hash != expected_hash:
                    corrupted += 1
                    print(f"    🚨 CORRUPTED CHUNK DETECTED: {full_path}")
                    print(f"       Expected:   {expected_hash}")
                    print(f"       Calculated: {calculated_hash}")

    print(f"    Scanned {scanned} chunks ({total_bytes / (1024*1024):.2f} MB on physical disk)")

    if corrupted == 0:
        print(f"    ✅ Physical Storage Integrity: 100% HEALTHY (0 corrupted blocks)")
        return True
    else:
        print(f"    ❌ Physical Storage: {corrupted} CORRUPTED CHUNKS FOUND!")
        return False


def main():
    print("=" * 65)
    print("  NVIDIA Cloud Storage Infrastructure: System Diagnostic Suite")
    print("=" * 65)

    db_ok = check_database()
    redis_ok = check_redis()
    storage_ok = scan_for_bit_rot()

    print("\n" + "=" * 65)
    if db_ok and redis_ok and storage_ok:
        print("  OVERALL SYSTEM STATUS: ALL SUBSYSTEMS HEALTHY (GREEN)")
        print("=" * 65)
        sys.exit(0)
    else:
        print("  OVERALL SYSTEM STATUS: SYSTEM DEGRADED / ALERTS TRIGGERED (RED)")
        print("=" * 65)
        sys.exit(1)


if __name__ == "__main__":
    main()