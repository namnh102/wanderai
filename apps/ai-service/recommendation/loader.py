"""ViHoRec Dataset Loader and Cache Manager for Recommendation Research."""

import os
import urllib.request
import pandas as pd
from typing import Dict, Any, Optional, Tuple

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/MinhNguyenDS/ViHoRec/Master/release"

DATASET_FILES = {
    "interactions": f"{GITHUB_RAW_BASE}/interactions.csv",
    "hotels": f"{GITHUB_RAW_BASE}/hotels.csv",
    "users": f"{GITHUB_RAW_BASE}/users.csv",
    "train": f"{GITHUB_RAW_BASE}/benchmark/train.csv",
    "val": f"{GITHUB_RAW_BASE}/benchmark/val.csv",
    "test": f"{GITHUB_RAW_BASE}/benchmark/test.csv",
}


class ViHoRecLoader:
    """Manages acquisition, caching, and loading of the ViHoRec dataset."""

    def __init__(self, cache_dir: Optional[str] = None):
        # Default cache directory: data/restricted/vihorec/ in project workspace
        if cache_dir is None:
            # Locate wanderai root
            current = os.path.abspath(os.path.dirname(__file__))
            root = os.path.abspath(os.path.join(current, "..", "..", ".."))
            cache_dir = os.path.join(root, "data", "restricted", "vihorec")
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def download_if_missing(self) -> Dict[str, str]:
        """Download dataset files if not already cached locally."""
        paths = {}
        for name, url in DATASET_FILES.items():
            local_path = os.path.join(self.cache_dir, f"{name}.csv")
            if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
                req = urllib.request.Request(url, headers={"User-Agent": "WanderAI-Research/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    with open(local_path, "wb") as f:
                        f.write(resp.read())
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
        """Compute exact statistical metrics from the current release."""
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
            "release_branch": "Master",
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
