from library.search import exclude_duplicate_results


def test_exclude_duplicate_results():
    results = [
        {'id': 1, 'type': 'question'},
        {'id': 1, 'type': 'question'},
        {'id': 1, 'type': 'policy'},
    ]

    result = exclude_duplicate_results(results)

    assert 2 == len(result)
    assert 'question' == result[0].get('type')
    assert 'policy' == result[1].get('type')
