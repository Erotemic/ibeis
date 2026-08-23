def test_synthetic_match_contract_is_test_owned():
    from ibeis.tests import reset_testdbs

    spec = reset_testdbs.synthetic_match_spec()
    assert spec['dbname'] == 'synthetic_match'
    assert spec['num_names'] == 40
    assert spec['images_per_name'] == 3
    assert spec['num_annots'] == 120
    assert spec['num_annots'] == spec['num_names'] * spec['images_per_name']


def test_synthetic_match_is_distinct_from_pz_mtest():
    from ibeis.tests import reset_testdbs

    spec = reset_testdbs.synthetic_match_spec()
    assert spec['dbname'] != 'PZ_MTEST'


def test_ci_reset_uses_synthetic_match_by_default(monkeypatch, tmp_path):
    from ibeis.init import sysres
    from ibeis.tests import reset_testdbs

    calls = []
    monkeypatch.setattr(sysres, 'get_workdir', lambda: str(tmp_path))
    monkeypatch.setattr(
        reset_testdbs,
        'ensure_smaller_testingdbs',
        lambda: calls.append('small'),
    )
    monkeypatch.setattr(
        reset_testdbs,
        'ensure_synthetic_match_db',
        lambda reset=False: calls.append(('synthetic_match', reset)),
    )
    monkeypatch.setattr(
        sysres,
        'ensure_pz_mtest',
        lambda: calls.append('pz_mtest'),
    )

    reset_testdbs.reset_ci_testdbs()
    assert calls == ['small', ('synthetic_match', True)]
