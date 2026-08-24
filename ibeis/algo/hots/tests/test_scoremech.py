
def test_scoremech():
    import utool as ut
    from ibeis.tests import reset_testdbs

    base = {'query_rotation_heuristic': True, 'sv_on': False, 'K': 1}
    cfgdict1 = ut.dict_union(
        base, {'score_method': 'nsum', 'prescore_method': 'nsum'})
    cfgdict2 = ut.dict_union(
        base, {'score_method': 'csum', 'prescore_method': 'csum'})

    ibs = reset_testdbs.ensure_synthetic_match_db()
    aids = ibs.get_valid_aids()
    qaids = [aids[0]]
    daids = [aid for aid in aids[:36] if aid not in qaids]

    qreq1_ = ibs.new_query_request(qaids, daids, cfgdict=cfgdict1)
    qreq2_ = ibs.new_query_request(qaids, daids, cfgdict=cfgdict2)
    cm_list1 = qreq1_.execute()
    cm_list2 = qreq2_.execute()

    cm1, cm2 = cm_list1[0], cm_list2[0]

    ai1 = cm1.pandas_annot_info().set_index(['daid', 'dnid'], drop=True)
    ai2 = cm2.pandas_annot_info().set_index(['daid', 'dnid'], drop=True)
    ai1 = ai1.rename(columns={c: c + '1' for c in ai1.columns})
    ai2 = ai2.rename(columns={c: c + '2' for c in ai2.columns})
    assert list(ai1.index) == list(ai2.index)

    ni1 = cm1.pandas_name_info().set_index(['dnid'], drop=True)
    ni2 = cm2.pandas_name_info().set_index(['dnid'], drop=True)
    ni1 = ni1.rename(columns={c: c + '1' for c in ni1.columns})
    ni2 = ni2.rename(columns={c: c + '2' for c in ni2.columns})
    assert list(ni1.index) == list(ni2.index)

    from ibeis.algo.hots.chip_match import check_arrs_eq
    assert check_arrs_eq(cm1.fm_list, cm2.fm_list)
    assert check_arrs_eq(cm1.fsv_list, cm2.fsv_list)

    cm1.evaluate_nsum_name_score(qreq1_)
    cm1.evaluate_maxcsum_name_score(qreq1_)
    assert 'nsum' in cm1.algo_name_scores
    assert 'maxcsum' in cm1.algo_name_scores

    from ibeis.algo.hots import name_scoring
    name_scoring.compute_fmech_score(cm1, qreq_=qreq1_)
