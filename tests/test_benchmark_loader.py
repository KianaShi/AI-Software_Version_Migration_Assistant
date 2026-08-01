from src.benchmark_loader import load_benchmark


def test_load_benchmark_returns_records():
    result = load_benchmark("benchmark")

    assert isinstance(result, list)
    assert len(result) > 0


def test_benchmark_record_contains_required_fields():
    result = load_benchmark("benchmark")
    first_record = result[0]

    required_fields = {
        "id",
        "play",
        "category",
        "difficulty",
        "question",
        "answer",
        "act",
        "scene",
    }

    assert required_fields.issubset(first_record.keys())


def test_load_benchmark_combines_multiple_plays():
    result = load_benchmark("benchmark")

    plays = {record["play"] for record in result}

    assert len(plays) >= 5