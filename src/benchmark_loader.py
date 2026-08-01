import json
from pathlib import Path


def load_benchmark(folder_path: str) -> list[dict]:
    """
    Load all JSON benchmark files from a folder.

    Args:
        folder_path: Path to the benchmark folder.

    Returns:
        A combined list of QA records.
    """
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"Benchmark folder not found: {folder_path}")

    benchmark_data = []

    for file_path in folder.glob("*.json"):
        with open(file_path, encoding="utf-8") as file:
            records = json.load(file)

        if not isinstance(records, list):
            raise ValueError(
                f"Expected a list in {file_path.name}, "
                f"but got {type(records).__name__}"
            )

        benchmark_data.extend(records)

    return benchmark_data
