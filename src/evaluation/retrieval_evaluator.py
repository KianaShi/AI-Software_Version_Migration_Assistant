def find_reference_rank(
    results: list[dict],
    expected_work: str,
    expected_act: int,
    expected_scene: int,
) -> int | None:
    for rank, result in enumerate(results, start=1):
        metadata = result["metadata"]

        retrieved_work = ...
        retrieved_act = ...
        retrieved_scene = ...

        if ...:
            return rank

    return None