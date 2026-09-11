import os
import subprocess
import sys
import time

STAGES = [
    ("1. Environment Sanity Check", ["node", "-v"]),
    (
        "2. Database Schema Validation",
        [
            "docker",
            "exec",
            "-i",
            "tensor_postgres",
            "psql",
            "-U",
            "storage_admin",
            "-d",
            "tensor_storage",
            "-c",
            "\\dt",
        ],
    ),
    (
        "3. Deep Learning Tensor Bit-for-Bit Validation",
        [sys.executable, "client/verify_tensor.py"],
    ),
    (
        "4. Multi-Worker Concurrency Benchmark (20 Workers)",
        [sys.executable, "client/benchmark.py"],
    ),
    (
        "5. Storage Diagnostics & Bit-Rot Integrity Scan",
        [sys.executable, "scripts/diagnose_storage.py"],
    ),
]


def run_pipeline():
    print("=" * 70)
    print("     🚀 NVIDIA STORAGE PLATFORM: AUTOMATED CI/CD PIPELINE")
    print("=" * 70)

    total_start = time.time()

    for idx, (stage_name, cmd) in enumerate(STAGES, 1):
        print(f"\n[STAGE {idx}/5] {stage_name}...")
        stage_start = time.time()

        try:
            # Run the command and stream output directly to console
            result = subprocess.run(cmd, check=True)
            elapsed = time.time() - stage_start
            print(f"--> STAGE {idx} PASSED ({elapsed:.2f}s) ✅")
        except subprocess.CalledProcessError as e:
            elapsed = time.time() - stage_start
            print(f"\n🚨 [PIPELINE FAILED] Stage '{stage_name}' exited with code {e.returncode} ({elapsed:.2f}s)")
            print("Pipeline aborted. Bad code or corrupted storage prevented from deployment.")
            sys.exit(1)

    total_time = time.time() - total_start

    # Verify build artifacts
    if os.path.exists("benchmark_report.json"):
        print(f"\n📦 [ARTIFACT ARCHIVED] benchmark_report.json ({os.path.getsize('benchmark_report.json')} bytes)")

    print("\n" + "=" * 70)
    print(f"  🎉 ALL CI/CD STAGES PASSED SUCCESSFULLY in {total_time:.2f}s!")
    print("  Status: READY FOR PRODUCTION DEPLOYMENT (GREEN)")
    print("=" * 70)


if __name__ == "__main__":
    run_pipeline()