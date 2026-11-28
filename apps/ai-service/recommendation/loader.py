"""ViHoRec Dataset Loader and Cache Manager for Recommendation Research."""

import hashlib
import os
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

import pandas as pd

VIHOREC_UPSTREAM_REPO = "MinhDS/ViHoRec"
VIHOREC_PINNED_REVISION = "fd53fbb8903ac305f3a0daffa86bd1a4a997df63"
VIHOREC_RAW_BASE = (
    f"https://huggingface.co/datasets/{VIHOREC_UPSTREAM_REPO}/resolve/{VIHOREC_PINNED_REVISION}"
)

DATASET_FILES: Dict[str, str] = {
    "interactions": f"{VIHOREC_RAW_BASE}/data/interactions/train-00000-of-00001.csv",
    "hotels": f"{VIHOREC_RAW_BASE}/data/hotels/train-00000-of-00001.csv",
    "users": f"{VIHOREC_RAW_BASE}/data/users/train-00000-of-00001.csv",
    "train": f"{VIHOREC_RAW_BASE}/benchmark/train.csv",
    "val": f"{VIHOREC_RAW_BASE}/benchmark/val.csv",
    "test": f"{VIHOREC_RAW_BASE}/benchmark/test.csv",
}

EXPECTED_SHA256: Dict[str, str] = {
    "hotels": "64d4108855d1eec303253bcfae71596a8abc26733b7fade0dd33b9425b976b16",
    "interactions": "6461d3f3abc15a79615cd09c46950dee4750575b951c4471a98b5c11fe40feeb",
    "users": "02926a6e666c7fcc23ae40733bbd1fe0b4565a25001ed3d85c9f14308ad6fbb3",
    "train": "781a3b99e5a020179e8f1c427c2acf858d1035385040114f88e76ab1320c915e",
    "val": "dcaeba814337360e1c483be1e3d61201ecbfb587555938114ae907bf8a15b948",
    "test": "eb2d913269c597d986e242b65c53f7067f765c68915005054fae99426e97afbc",
}

_TRANSIENT_HTTP_CODES = frozenset({408, 429, 500, 502, 503, 504})


def _compute_file_sha256(path: str) -> str:
    for attempt in range(1, 6):
        try:
            digest = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    digest.update(chunk)
            return digest.hexdigest()
        except PermissionError:
            if attempt >= 5:
                raise
            time.sleep(0.01 * attempt)
    raise RuntimeError(f"Unreachable SHA-256 read retry exhaustion for {path}")


def _atomic_replace(tmp_path: str, local_path: str) -> None:
    for attempt in range(1, 11):
        try:
            os.replace(tmp_path, local_path)
            return
        except PermissionError:
            if attempt >= 10:
                raise
            time.sleep(0.01 * attempt)


class ViHoRecLoader:
    """Manages acquisition, SHA-256 verification, caching, and loading of ViHoRec."""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        verify_checksums: bool = True,
        max_download_attempts: int = 3,
    ):
        # Default cache directory: data/restricted/vihorec/ in project workspace
        if cache_dir is None:
            env_cache_dir = os.environ.get("VIHOREC_CACHE_DIR", "").strip()
            if env_cache_dir:
                cache_dir = env_cache_dir
            else:
                current = os.path.abspath(os.path.dirname(__file__))
                root = os.path.abspath(os.path.join(current, "..", "..", ".."))
                cache_dir = os.path.join(root, "data", "restricted", "vihorec")
        self.cache_dir = cache_dir
        self.verify_checksums = verify_checksums
        self.max_download_attempts = max(1, int(max_download_attempts))
        os.makedirs(self.cache_dir, exist_ok=True)

    def _download_bytes_with_retry(self, url: str) -> bytes:
        last_exc: Optional[ BaseException] = None
        for attempt in range(1, self.max_download_attempts + 1):
            req = urllib.request.Request(url, headers={"User-Agent": "WanderAI-Research/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code not in _TRANSIENT_HTTP_CODES or attempt >= self.max_download_attempts:
                    raise
            except urllib.error.URLError as exc:
                last_exc = exc
                if attempt >= self.max_download_attempts:
                    raise
            time.sleep(0.5 * attempt)
        assert last_exc is not None
        raise last_exc

    def download_if_missing(self) -> Dict[str, str]:
        """Ensure dataset CSVs exist locally and match pinned SHA-256 digests."""
        paths: Dict[str, str] = {}
        for name, url in DATASET_FILES.items():
            local_path = os.path.join(self.cache_dir, f"{name}.csv")
            expected_sha = EXPECTED_SHA256[name]

            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                if self.verify_checksums:
                    actual_sha = _compute_file_sha256(local_path)
                    if actual_sha != expected_sha:
                        raise ValueError(
                            f"Cached ViHoRec {name}.csv SHA-256 mismatch: "
                            f"expected {expected_sha}, got {actual_sha}"
                        )
                paths[name] = local_path
                continue

            payload = self._download_bytes_with_retry(url)
            if not payload:
                raise ValueError(f"Downloaded empty payload for ViHoRec {name}.csv from {url}")

            fd, tmp_path = tempfile.mkstemp(
                prefix=f".{name}.",
                suffix=".tmp",
                dir=self.cache_dir,
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(payload)
                    f.flush()

                if self.verify_checksums:
                    actual_sha = _compute_file_sha256(tmp_path)
                    if actual_sha != expected_sha:
                        raise ValueError(
                            f"Downloaded ViHoRec {name}.csv SHA-256 mismatch from {url}: "
                            f"expected {expected_sha}, got {actual_sha}"
                        )

                _atomic_replace(tmp_path, local_path)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

            paths[name] = local_path
        return paths

    def load_dataset(self) -> Dict[str, pd.DataFrame]:
        """Load all ViHoRec tables into pandas DataFrames with normalized column names."""
        paths = self.download_if_missing()
        dfs = {
            "interactions": pd.read_csv(paths["interactions"]),
            "hotels": pd.read_csv(paths["hotels"]),
            "users": pd.read_csv(paths["users"]),
            "train": pd.read_csv(paths["train"]),
            "val": pd.read_csv(paths["val"]),
            "test": pd.read_csv(paths["test"]),
        }
        # Normalize column names across benchmark splits
        for split in ["train", "val", "test"]:
            dfs[split].rename(columns={"userID": "user_id", "itemID": "hotel_id"}, inplace=True)
        if "location" in dfs["hotels"].columns and "city" not in dfs["hotels"].columns:
            dfs["hotels"]["city"] = dfs["hotels"]["location"]
        return dfs

    def get_audit_statistics(self) -> Dict[str, Any]:
        """Compute exact statistical metrics from the pinned official release."""
        dfs = self.load_dataset()
        df_inter = dfs["interactions"]
        df_train = dfs["train"]
        df_val = dfs["val"]
        df_test = dfs["test"]
        df_hotels = dfs["hotels"]
        df_users = dfs["users"]

        total_interactions = len(df_inter)
        num_users = df_inter["user_id"].nunique()
        num_hotels = df_inter["hotel_id"].nunique()
        matrix_size = num_users * num_hotels
        sparsity = (1.0 - (total_interactions / matrix_size)) * 100.0 if matrix_size > 0 else 0.0

        user_counts = df_inter.groupby("user_id").size()
        single_interaction_users = (user_counts == 1).sum()
        cold_start_ratio = (single_interaction_users / num_users) * 100.0 if num_users > 0 else 0.0

        return {
            "dataset_name": "ViHoRec",
            "upstream_repo": VIHOREC_UPSTREAM_REPO,
            "pinned_revision": VIHOREC_PINNED_REVISION,
            "license": "CC BY-NC 4.0",
            "total_interactions": int(total_interactions),
            "unique_users": int(num_users),
            "unique_hotels": int(num_hotels),
            "hotels_in_metadata": int(len(df_hotels)),
            "users_in_metadata": int(len(df_users)),
            "matrix_sparsity_percent": round(sparsity, 2),
            "cold_start_users_percent": round(cold_start_ratio, 2),
            "benchmark_split": {
                "train_records": int(len(df_train)),
                "val_records": int(len(df_val)),
                "test_records": int(len(df_test)),
                "test_users": int(df_test["user_id"].nunique()),
            },
            "platforms": df_inter["source"].value_counts().to_dict() if "source" in df_inter else {},
            "date_range": {
                "min": str(df_inter["date"].min()) if "date" in df_inter else None,
                "max": str(df_inter["date"].max()) if "date" in df_inter else None,
            },
        }

