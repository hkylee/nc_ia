from scripts.check_manual_requirement_coverage import QUEUE_PATH, check_queue


def test_manual_authoring_requirement_coverage_is_complete():
    results = check_queue(QUEUE_PATH)

    assert results
    assert all(result.ok for result in results), [
        (result.module_id, result.topic, result.issues) for result in results if not result.ok
    ]
    assert sum(result.db_count for result in results) == sum(result.matched_count for result in results)
