def test_lnbnn():
    from ibeis.tests import reset_testdbs

    ibs = reset_testdbs.ensure_synthetic_match_db()
    aids = ibs.get_valid_aids()
    qaids = aids[:3]
    daids = aids[:18]
    qreq = ibs.new_query_request(qaids, daids)
    cm_list = qreq.execute(use_cache=False)
    assert len(cm_list) == len(qaids)
