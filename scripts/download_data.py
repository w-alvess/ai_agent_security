import shutil
from pathlib import Path

import kagglehub

DATASET = "muhammadahmerkhan/ai-agent-security-and-real-world-incidents-2024-26"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def main() -> None:
    cache_path = kagglehub.dataset_download(DATASET)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(cache_path, RAW_DIR, dirs_exist_ok=True)
    print(f"Dados em {RAW_DIR}")


if __name__ == "__main__":
    main()
