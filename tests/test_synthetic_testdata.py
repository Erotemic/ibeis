def test_synthetic_mtest_contract_is_test_owned():
    from ibeis.tests import reset_testdbs

    spec = reset_testdbs.synthetic_mtest_spec()
    assert spec['num_names'] == 40
    assert spec['images_per_name'] == 3
    assert spec['num_annots'] == 120
    assert spec['num_annots'] == spec['num_names'] * spec['images_per_name']


def test_pz_name_is_only_a_compatibility_locator():
    from ibeis.tests import reset_testdbs

    spec = reset_testdbs.synthetic_mtest_spec()
    assert spec['dbname'] == 'PZ_MTEST'
    assert (spec['num_names'], spec['num_annots']) != (41, 119)


def test_ci_reset_uses_synthetic_mtest_by_default(monkeypatch, tmp_path):
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
        'ensure_synthetic_mtest',
        lambda reset=False: calls.append(('synthetic_mtest', reset)),
    )

    reset_testdbs.reset_ci_testdbs()
    assert calls == ['small', ('synthetic_mtest', True)]
