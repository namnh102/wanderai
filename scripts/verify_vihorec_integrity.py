#!/usr/bin/env python3
"""ViHoRec Checksum & Integrity Verifier.

Verifies that the 6 files in data/restricted/vihorec/ match the known
upstream official cryptographic hashes.
"""

import hashlib
import sys
from pathlib import Path

EXPECTED_HASHES = {
    "hotels.csv": "64d4108855d1eec303253bcfae71596a8abc26733b7fade0dd33b9425b976b16",
    "interactions.csv": "6461d3f3abc15a79615cd09c46950dee4750575b951c4471a98b5c11fe40feeb",
    "users.csv": "02926a6e666c7fcc23ae40733bbd1fe0b4565a25001ed3d85c9f14308ad6fbb3",
    "train.csv": "781a3b99e5a020179e8f1c427c2acf858d1035385040114f88e76ab1320c915e",
    "val.csv": "dcaeba814337360e1c483be1e3d61201ecbfb587555938114ae907bf8a15b948",
    "test.csv": "eb2d913269c597d986e242b65c53f7067f765c68915005054fae99426e97afbc",
}

def verify_vihorec(base_dir: Path) -> bool:
    vihorec_dir = base_dir / "data" / "restricted" / "vihorec"
    if not vihorec_dir.exists():
        print(f"[FAIL] Directory not found: {vihorec_dir}")
        return False

    all_passed = True
    print("=" * 70)
    print("VERIFYING VIHOREC 6-FILE CRYPTOGRAPHIC INTEGRITY (READ ONLY)")
    print("=" * 70)

    for filename, expected_sha in EXPECTED_HASHES.items():
        file_path = vihorec_dir / filename
        if not file_path.exists():
            print(f"[FAIL] Missing file: {filename}")
            all_passed = False
            continue

        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        actual_sha = h.hexdigest()

        if actual_sha == expected_sha:
            print(f"[PASS] {filename:<18} SHA-256: {actual_sha}")
        else:
            print(f"[FAIL] {filename:<18}")
            print(f"       Expected: {expected_sha}")
            print(f"       Actual:   {actual_sha}")
            all_passed = False

    print("=" * 70)
    if all_passed:
        print("VIHOREC INTEGRITY VERIFICATION RESULT: PASS")
        return True
    else:
        print("VIHOREC INTEGRITY VERIFICATION RESULT: FAIL")
        return False

if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    success = verify_vihorec(repo_root)
    sys.exit(0 if success else 1)
