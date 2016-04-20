# -*- coding: utf-8 -*-
"""
TODO: DEPRICATE

handles the "special" more complex vs-one re-ranked query

# Write some alias for ourselves
python -c "import utool as ut; ut.write_modscript_alias( 'Tinc.sh', 'ibeis.algo.hots.qt_inc_automatch')"
python -c "import utool as ut; ut.write_modscript_alias('pTinc.sh', 'ibeis.algo.hots.qt_inc_automatch', 'utprof.py')"

# PROFILE PZ_Master0 With lots of preadded data
sh pTinc.sh --test-test_inc_query:3 --num-init 7500 --test-title "ProfileIncPZMaster0"

sh pTinc.sh --test-test_inc_query:3 --num-init 8690
sh pTinc.sh --test-test_inc_query:0
sh pTinc.sh --test-test_inc_query:3 --num-init 5000 --devcache --vsone-errs


sh Tinc.sh --test-test_inc_query:2 --num-init 100 --devcache --vsone-errs

# Interactive GZ Test
sh Tinc.sh --test-test_inc_query:2 --num-init 100 --devcache --no-normcache --vsone-errs --ia 10  --test-title "GZ_Inc_Errors"

# Automatic GZ Test
sh Tinc.sh --test-test_inc_query:2 --num-init 100 --devcache --no-normcache --vsone-errs  --test-title "GZ_Inc_Errors"

# AUTOMATIC PZ_MTEST
sh Tinc.sh --test-test_inc_query:1 --num-init 0 --devcache --no-normcache --vsone-errs  --test-title "PZ_Inc_Errors"
# No testing
sh Tinc.sh --test-test_inc_query:1 --num-init 0 --no-normcache --test-title "PZ_Inc_Errors"



# Automatic GZ Test Small
sh Tinc.sh --test-test_inc_query:2 --num-init 0 --devcache --no-normcache --vsone-errs --test-title "GZ_DEV" --gzdev --ninit 34 --naac --interupt-case
sh Tinc.sh --test-test_inc_query:2 --num-init 0 --devcache --no-normcache --vsone-errs --test-title "GZ_DEV" --gzdev --ninit 47 --naac --interupt-case

"""
from __future__ import absolute_import, division, print_function
import six
import utool as ut
import numpy as np
import vtool as vt
from ibeis.algo.hots import hstypes
from ibeis.algo.hots import match_chips4 as mc4
from ibeis.algo.hots import distinctiveness_normalizer
from ibeis.algo.hots import automated_params
from six.moves import filter
print, print_, printDBG, rrr, profile = ut.inject(__name__, '[special_query]')


# hack for tests
if ut.in_main_process():
    test_title = ut.get_argval('--test-title', type_=str, default=None)
    if test_title is not None:
        ut.change_term_title(test_title)


USE_VSMANY_HACK = ut.get_argflag('--vsmany-hack')
TEST_VSONE_ERRORS = ut.get_argflag(('--test-vsone-errors', '--vsone-errs'))


TestTup = ut.namedtuple(
    'TestTup', (
        'qaid_t', 'qaid', 'vsmany_rank', 'vsone_rank'))


def testdata_special_query(dbname=None):
    """ test data for special query doctests """
    import ibeis
    if dbname is None:
        dbname = 'testdb1'
    # build test data
    ibs = ibeis.opendb(dbname)
    #ibs = ibeis.opendb('PZ_MTEST')
    valid_aids = ibs.get_valid_aids(species='zebra_plains')
    return ibs, valid_aids


@profile
def query_vsone_verified(ibs, qaids, daids, qreq_vsmany__=None, incinfo=None):
    """
    main special query entry point

    A hacked in vsone-reranked pipeline
    Actually just two calls to the pipeline

    Args:
        ibs (IBEISController):  ibeis controller object
        qaids (list):  query annotation ids
        daids (list):  database annotation ids
        qreq_vsmany_ (QueryRequest):  used for persitant QueryRequest objects
            if None creates new query request otherwise

    Returns:
        tuple: qaid2_qres, qreq_

    CommandLine:
        python -m ibeis.algo.hots.special_query --test-query_vsone_verified

    Example:
        >>> # SLOW_DOCTEST
        >>> from ibeis.algo.hots.special_query import *  # NOQA
        >>> ibs, valid_aids = testdata_special_query('PZ_MTEST')
        >>> qaids = valid_aids[0:1]
        >>> daids = valid_aids[1:]
        >>> qaid = qaids[0]
        >>> # execute function
        >>> qaid2_qres, qreq_, qreq_vsmany_ = query_vsone_verified(ibs, qaids, daids)
        >>> cm = qaid2_qres[qaid]

    Ignore:
        from ibeis.algo.hots import score_normalization

        cm = qaid2_qres_vsmany[qaid]

        ibs.delete_qres_cache()
        cm = qaid2_qres[qaid]
        cm.show_top(ibs, update=True, name_scoring=True)

        qres_vsmany = qaid2_qres_vsmany[qaid]
        qres_vsmany.show_top(ibs, update=True, name_scoring=True)

        qres_vsone = qaid2_qres_vsone[qaid]
        qres_vsone.show_top(ibs, update=True, name_scoring=True)
    """
    if len(daids) == 0:
        print('[special_query.X] no daids... returning empty query')
        qaid2_qres, qreq_ = mc4.empty_query(ibs, qaids)
        return qaid2_qres, qreq_, None
    #use_cache = True
    use_cache = False
    save_qcache = False

    # vs-many initial scoring
    print('[special_query.1] issue vsmany query')
    qaid2_qres_vsmany, qreq_vsmany_ = query_vsmany_initial(
        ibs, qaids, daids, use_cache=use_cache, save_qcache=save_qcache,
        qreq_vsmany_=qreq_vsmany__)

    # HACK TO JUST USE VSMANY
    # this can ensure that the baseline system is not out of wack
    if USE_VSMANY_HACK:
        print('[special_query.X] vsmany hack on... returning vsmany result')
        qaid2_qres = qaid2_qres_vsmany
        qreq_ = qreq_vsmany_
        return qaid2_qres, qreq_, qreq_vsmany_

    # build vs one list
    print('[special_query.2] finished vsmany query... building vsone pairs')
    vsone_query_pairs = build_vsone_shortlist(ibs, qaid2_qres_vsmany)

    # vs-one reranking
    print('[special_query.3] issue vsone queries')
    qaid2_qres_vsone, qreq_vsone_ = query_vsone_pairs(ibs, vsone_query_pairs, use_cache)

    # hack in score normalization
    if qreq_vsone_.qparams.score_normalization:
        qreq_vsone_.load_score_normalizer()

    # Augment vsone queries with vsmany distinctiveness
    print('[special_query.4] augmenting vsone queries')
    augment_vsone_with_vsmany(vsone_query_pairs, qaid2_qres_vsone, qaid2_qres_vsmany, qreq_vsone_)

    if ut.VERBOSE:
        verbose_report_results(ibs, qaids, qaid2_qres_vsone, qaid2_qres_vsmany)

    print('[special_query.5] finished vsone query... checking results')

    # FIXME: returns the last qreq_. There should be a notion of a query
    # request for a vsone reranked query
    qaid2_qres = qaid2_qres_vsone
    qreq_ = qreq_vsone_
    all_failed_qres = all([cm is None for cm in six.itervalues(qaid2_qres)])
    any_failed_qres = any([cm is None for cm in six.itervalues(qaid2_qres)])
    if any_failed_qres:
        assert all_failed_qres, "Needs to finish implemetation"
        print('[special_query.X] failed vsone qreq... returning empty query')
        qaid2_qres, qreq_ = mc4.empty_query(ibs, qaids)
        return qaid2_qres, qreq_, None

    if TEST_VSONE_ERRORS and incinfo is not None and 'metatup' in incinfo:
        test_vsone_errors(ibs, daids, qaid2_qres_vsmany, qaid2_qres_vsone, incinfo)

    print('[special_query.5] finished special query')
    return qaid2_qres, qreq_, qreq_vsmany_


def test_vsone_errors(ibs, daids, qaid2_qres_vsmany, qaid2_qres_vsone, incinfo):
    """
    ibs1 = ibs_gt
    ibs2 = ibs (the current test database, sorry for the backwardness)
    aid1_to_aid2 - maps annots from ibs1 to ibs2
    """
    WASH                = 'wash'
    BOTH_FAIL           = 'both_fail'
    SINGLETON           = 'singleton'
    VSMANY_OUTPERFORMED = 'vsmany_outperformed'
    VSMANY_DOMINATES    = 'vsmany_dominates'
    VSMANY_WINS         = 'vsmany_wins'
    VSONE_WINS          = 'vsone_wins'
    if 'testcases' not in incinfo:
        testcases = {}
        for case in [WASH, BOTH_FAIL, SINGLETON, VSMANY_OUTPERFORMED,
                     VSMANY_DOMINATES, VSMANY_WINS, VSONE_WINS]:
            testcases[case] = []
        incinfo['testcases'] = testcases
    testcases = incinfo['testcases']

    def append_case(case, testtup):
        print('APPENDED NEW TESTCASE: case=%r' % (case,))
        print('* testup = %r' % (testtup,))
        print('* vuuid = %r' % (ibs_gt.get_annot_visual_uuids(testtup.qaid_t),))
        if ut.get_argflag('--interupt-case') and case in [VSMANY_WINS, VSMANY_DOMINATES]:
            incinfo['interactive'] = True
            incinfo['use_oracle'] = False
            incinfo['STOP'] = True
            if ut.is_developer():
                import plottool as pt  # NOQA
                IPYTHON_COMMANDS = """
                >>> %pylab qt4
                >>> from ibeis.viz.interact import interact_matches  # NOQA
                >>> #qres_vsmany = ut.search_stack_for_localvar('qres_vsmany')
                >>> ibs        = ut.search_stack_for_localvar('ibs')
                >>> daids      = ut.search_stack_for_localvar('daids')
                >>> qnid_t     = ut.search_stack_for_localvar('qnid_t')
                >>> qres_vsone = ut.search_stack_for_localvar('qres_vsone')
                >>> all_nids_t = ut.search_stack_for_localvar('all_nids_t')
                >>> # Find index in daids of correct matches
                >>> cm = qres_vsone
                >>> correct_indices = np.where(np.array(all_nids_t) == qnid_t)[0]
                >>> correct_aids2 = ut.take(daids, correct_indices)
                >>> qaid = cm.qaid
                >>> aid = correct_aids2[0]
                >>> # Report visual uuid for inclusion or exclusion in script
                >>> print(ibs.get_annot_visual_uuids([qaid, aid]))

                >>> # Feature match things
                >>> print('cm.filtkey_list = %r' % (cm.filtkey_list,))
                >>> fm  = cm.aid2_fm[aid]
                >>> fs  = cm.aid2_fs[aid]
                >>> fsv = cm.aid2_fsv[aid]
                >>> mx = 2
                >>> qfx, dfx = fm[mx]
                >>> fsv_single = fsv[mx]
                >>> fs_single = fs[mx]
                >>> # check featweights
                >>> data_featweights = ibs.get_annot_fgweights([aid])[0]
                >>> data_featweights[dfx]
                >>> fnum = pt.next_fnum()
                >>> bad_aid = cm.get_top_aids()[0]
                >>> #match_interaction_good = interact_matches.MatchInteraction(ibs, cm, aid, annot_mode=1)
                >>> #match_interaction_bad = interact_matches.MatchInteraction(ibs, cm, bad_aid)
                >>> match_interaction_good = cm.ishow_matches(ibs, aid, annot_mode=1, fnum=1)
                >>> match_interaction_bad = cm.ishow_matches(ibs, bad_aid, annot_mode=1, fnum=2)
                >>> match_interaction = match_interaction_good
                >>> self = match_interaction
                >>> self.select_ith_match(mx)
                >>> #impossible_to_match = len(correct_indices) > 0
                """
                y = """
                >>> from os.path import exists
                >>> import vtool as vt
                >>> import vtool.patch as vtpatch
                >>> import vtool.image as vtimage  # NOQA
                >>> chip_list = ibs.get_annot_chips([aid])
                >>> kpts_list = ibs.get_annot_kpts([aid])
                >>> probchip_fpath_list = ibs.get_probchip_fpath(aid)
                >>> probchip_list = [vt.imread(fpath, grayscale=True) if exists(fpath) else None for fpath in probchip_fpath_list]
                >>> kpts  = kpts_list[0]
                >>> probchip = probchip_list[0]
                >>> kp = kpts[dfx]
                >>> patch  = vt.get_warped_patch(probchip, kp)[0].astype(np.float32) / 255.0
                >>> fnum2 = pt.next_fnum()
                >>> pt.figure(fnum2, pnum=(1, 2, 1), doclf=True, docla=True)
                >>> pt.imshow(probchip)
                >>> pt.draw_kpts2([kp])
                >>> pt.figure(fnum2, pnum=(1, 2, 2))
                >>> pt.imshow(patch * 255)
                >>> pt.update()
                >>> vt.gaussian_average_patch(patch)
                >>> cm.ishow_top(ibs, annot_mode=1)
                """
                y
                ut.set_clipboard(IPYTHON_COMMANDS)
                #ut.spawn_delayed_ipython_paste()
                ut.embed(remove_pyqt_hook=False)
                IPYTHON_COMMANDS

        testcases[case].append(testtup)

    for qaid in six.iterkeys(qaid2_qres_vsmany):
        qres_vsmany = qaid2_qres_vsmany[qaid]
        qres_vsone  = qaid2_qres_vsone[qaid]
        nscoretup_vsone  = qres_vsone.get_nscoretup()
        nscoretup_vsmany = qres_vsmany.get_nscoretup()
        metatup = incinfo['metatup']
        ibs_gt, aid1_to_aid2 = metatup
        aid2_to_aid1 = ut.invert_dict(aid1_to_aid2)

        top_aids_vsone  = ut.get_list_column(nscoretup_vsone.sorted_aids, 0)
        top_aids_vsmany = ut.get_list_column(nscoretup_vsmany.sorted_aids, 0)
        # tranform to groundtruth database coordinates
        all_daids_t = ut.dict_take_list(aid2_to_aid1, daids)
        top_aids_vsone_t  = ut.dict_take_list(aid2_to_aid1, top_aids_vsone)
        top_aids_vsmany_t = ut.dict_take_list(aid2_to_aid1, top_aids_vsmany)
        qaid_t = aid2_to_aid1[qaid]

        aids_tup = (all_daids_t, top_aids_vsone_t, top_aids_vsmany_t, (qaid_t,),)
        nids_tup = ibs_gt.unflat_map(ibs_gt.get_annot_nids, aids_tup)
        (all_nids_t, top_nids_vsone_t, top_nids_vsmany_t, (qnid_t,),) = nids_tup

        vsmany_rank  = ut.listfind(top_nids_vsmany_t, qnid_t)
        vsone_rank   = ut.listfind(top_nids_vsone_t, qnid_t)
        impossible_to_match = ut.listfind(all_nids_t, qnid_t) is None

        # Sort the test case into a category
        testtup = TestTup(qaid_t, qaid, vsmany_rank, vsone_rank)
        if vsmany_rank is None and vsone_rank is None and impossible_to_match:
            append_case(SINGLETON, testtup)
        elif vsmany_rank is not None and vsone_rank is None:
            if vsmany_rank < 5:
                append_case(VSMANY_DOMINATES, testtup)
            else:
                append_case(VSMANY_OUTPERFORMED, testtup)
        elif vsmany_rank is None:
            append_case(BOTH_FAIL, testtup)
        elif vsone_rank > vsmany_rank:
            append_case(VSMANY_WINS, testtup)
        elif vsone_rank < vsmany_rank:
            append_case(VSONE_WINS, testtup)
        elif vsone_rank == vsmany_rank:
            append_case(WASH, testtup)
        else:
            raise AssertionError('unenumerated case')
        count_dict = ut.count_dict_vals(testcases)
        print('+--')
        #print(ut.dict_str(testcases))
        print('---')
        print(ut.dict_str(count_dict))
        print('L__')
        #ut.embed()


@profile
def query_vsmany_initial(ibs, qaids, daids, use_cache=False, qreq_vsmany_=None,
                         save_qcache=False):
    r"""

    Args:
        ibs (IBEISController):  ibeis controller object
        qaids (list):  query annotation ids
        daids (list):  database annotation ids
        use_cache (bool):  turns on disk based caching
        qreq_vsmany_ (QueryRequest):  persistant vsmany query request

    Returns:
        tuple: (newfsv_list, newscore_aids)

    CommandLine:
        python -m ibeis.algo.hots.special_query --test-query_vsmany_initial

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.hots.special_query import *  # NOQA
        >>> ibs, valid_aids = testdata_special_query()
        >>> qaids = valid_aids[0:1]
        >>> daids = valid_aids[1:]
        >>> use_cache = False
        >>> # execute function
        >>> qaid2_qres_vsmany, qreq_vsmany_ = query_vsmany_initial(ibs, qaids, daids, use_cache)
        >>> qres_vsmany = qaid2_qres_vsmany[qaids[0]]
        >>> # verify results
        >>> result = qres_vsmany.get_top_aids().tolist()
        >>> print(result)
        [2, 6, 4]
    """
    num_names = len(set(ibs.get_annot_nids(daids)))
    vsmany_cfgdict = dict(
        K=automated_params.choose_vsmany_K(num_names, qaids, daids),
        Knorm=3,
        index_method='multi',
        pipeline_root='vsmany',
        return_expanded_nns=True
    )
    cm_list, qreq_vsmany_ = ibs.query_chips(
        qaids, daids, cfgdict=vsmany_cfgdict, return_request=True,
        use_cache=use_cache, qreq_=qreq_vsmany_, save_qcache=save_qcache)
    qaid2_qres_vsmany = {cm.qaid: cm for cm in cm_list}
    isnsum = qreq_vsmany_.qparams.score_method == 'nsum'
    assert isnsum, 'not nsum'
    assert qreq_vsmany_.qparams.pipeline_root != 'vsone'
    return qaid2_qres_vsmany, qreq_vsmany_


@profile
def build_vsone_shortlist(ibs, qaid2_qres_vsmany):
    """
    looks that the top N names in a vsmany query to apply vsone reranking

    Args:
        ibs (IBEISController):  ibeis controller object
        qaid2_qres_vsmany (dict):  dict of query result objects

    Returns:
        list: vsone_query_pairs

    CommandLine:
        python -m ibeis.algo.hots.special_query --test-build_vsone_shortlist

    Example:
        >>> # SLOW_DOCTEST
        >>> from ibeis.algo.hots.special_query import *  # NOQA
        >>> ibs, valid_aids = testdata_special_query()
        >>> qaids = valid_aids[0:1]
        >>> daids = valid_aids[1:]
        >>> qaid2_qres_vsmany, qreq_vsmany_ = query_vsmany_initial(ibs, qaids, daids)
        >>> # execute function
        >>> vsone_query_pairs = build_vsone_shortlist(ibs, qaid2_qres_vsmany)
        >>> qaid, top_aid_list = vsone_query_pairs[0]
        >>> top_nid_list = ibs.get_annot_name_rowids(top_aid_list)
        >>> assert top_nid_list.index(1) == 0, 'name 1 should be rank 1'
        >>> assert len(top_nid_list) == 5, 'should have 3 names and up to 2 image per name'

    [(1, [3, 2, 6, 5, 4])]
    [(1, [2, 3, 6, 5, 4])]

    """
    vsone_query_pairs = []
    nNameShortlist = 3
    nAnnotPerName = 2
    for qaid, qres_vsmany in six.iteritems(qaid2_qres_vsmany):
        nscoretup = qres_vsmany.get_nscoretup()
        (sorted_nids, sorted_nscores, sorted_aids, sorted_scores) = nscoretup
        #top_nid_list = ut.listclip(sorted_nids, nNameShortlist)
        top_aids_list = ut.listclip(sorted_aids, nNameShortlist)
        top_aids_list_ = [ut.listclip(aids, nAnnotPerName) for aids in top_aids_list]
        top_aid_list = ut.flatten(top_aids_list_)
        # get top annotations beloning to the database query
        # TODO: allow annots not in daids to be included
        #top_unflataids = ibs.get_name_aids(top_nid_list, enable_unknown_fix=True)
        #flat_top_aids = ut.flatten(top_unflataids)
        #top_aid_list = ut.intersect_ordered(flat_top_aids, qres_vsmany.daids)
        vsone_query_pairs.append((qaid, top_aid_list))
    print('built %d pairs' % (len(vsone_query_pairs),))
    return vsone_query_pairs


@profile
def query_vsone_pairs(ibs, vsone_query_pairs, use_cache=False, save_qcache=False):
    """
    does vsone queries to rerank the top few vsmany querys

    Returns:
        tuple: qaid2_qres_vsone, qreq_vsone_

    CommandLine:
        python -m ibeis.algo.hots.special_query --test-query_vsone_pairs

    Example:
        >>> # SLOW_DOCTEST
        >>> from ibeis.algo.hots.special_query import *  # NOQA
        >>> ibs, valid_aids = testdata_special_query()
        >>> qaids = valid_aids[0:1]
        >>> daids = valid_aids[1:]
        >>> qaid = qaids[0]
        >>> filtkey = hstypes.FiltKeys.DISTINCTIVENESS
        >>> use_cache = False
        >>> save_qcache = False
        >>> # execute function
        >>> qaid2_qres_vsmany, qreq_vsmany_ = query_vsmany_initial(ibs, qaids, daids)
        >>> vsone_query_pairs = build_vsone_shortlist(ibs, qaid2_qres_vsmany)
        >>> qaid2_qres_vsone, qreq_vsone_ = query_vsone_pairs(ibs, vsone_query_pairs)
        >>> qres_vsone = qaid2_qres_vsone[qaid]
        >>> top_namescore_aids = qres_vsone.get_top_aids().tolist()
        >>> result = str(top_namescore_aids)
        >>> top_namescore_names = ibs.get_annot_names(top_namescore_aids)
        >>> assert top_namescore_names[0] == 'easy', 'top_namescore_names[0]=%r' % (top_namescore_names[0],)
    """
    #vsone_cfgdict = dict(codename='vsone_unnorm')
    #codename = 'vsone_unnorm_dist_ratio_extern_distinctiveness',
    codename = 'vsone_unnorm_dist_ratio'
    vsone_cfgdict = dict(
        index_method='single',
        codename=codename,
    )
    #------------------------
    qaid2_qres_vsone = {}
    for qaid, top_aids in vsone_query_pairs:
        # Perform a query request for each
        cm_list_vsone_, __qreq_vsone_ = ibs.query_chips(
            [qaid], top_aids, cfgdict=vsone_cfgdict, return_request=True,
            use_cache=use_cache, save_qcache=save_qcache)
        qaid2_qres_vsone_ = {cm.qaid: cm for cm in cm_list_vsone_}
        qaid2_qres_vsone.update(qaid2_qres_vsone_)
    #------------------------
    # Create pseudo query request because there is no good way to
    # represent the vsone reranking as a single query request and
    # we need one for the score normalizer
    #pseudo_codename_ = codename.replace('unnorm', 'norm') + '_extern_distinctiveness'
    pseudo_codename_ = codename.replace('unnorm', 'norm')  # + '_extern_distinctiveness'
    pseudo_vsone_cfgdict = dict(codename=pseudo_codename_)
    pseudo_qaids = ut.get_list_column(vsone_query_pairs, 0)
    pseudo_daids = ut.unique_ordered(ut.flatten(ut.get_list_column(vsone_query_pairs, 1)))
    # FIXME: making the pseudo qreq_ takes a nontrivial amount of time for what
    # should be a trivial task.
    pseudo_qreq_vsone_ = ibs.new_query_request(pseudo_qaids, pseudo_daids,
                                               cfgdict=pseudo_vsone_cfgdict,
                                               verbose=ut.VERBOSE)
    #pseudo_qreq_vsone_.load_distinctiveness_normalizer()
    qreq_vsone_ = pseudo_qreq_vsone_
    # Hack in a special config name
    qreq_vsone_.qparams.query_cfgstr = '_special' + qreq_vsone_.qparams.query_cfgstr
    return qaid2_qres_vsone, qreq_vsone_


@profile
def augment_vsone_with_vsmany(vsone_query_pairs, qaid2_qres_vsone, qaid2_qres_vsmany, qreq_vsone_):
    """
    AUGMENT VSONE QUERIES (BIG HACKS AFTER THIS POINT)
    Apply vsmany distinctiveness scores to vsone

    Args:
        vsone_query_pairs (?):
        qaid2_qres_vsone (dict):  dict of query result objects
        qaid2_qres_vsmany (dict):  dict of query result objects
        qreq_vsone_ (?):

    CommandLine:
        python -m ibeis.algo.hots.special_query --test-augment_vsone_with_vsmany

    Example:
        >>> # SLOW_DOCTEST
        >>> from ibeis.algo.hots.special_query import *  # NOQA
        >>> # build test data
        >>> ibs, valid_aids = testdata_special_query()
        >>> qaids = valid_aids[0:1]
        >>> daids = valid_aids[1:]
        >>> qaid = qaids[0]
        >>> qaid2_qres_vsmany, qreq_vsmany_ = query_vsmany_initial(
        ...    ibs, qaids, daids, use_cache=False, save_qcache=False,
        ...    qreq_vsmany_=None)
        >>> vsone_query_pairs = build_vsone_shortlist(ibs, qaid2_qres_vsmany)
        >>> qaid2_qres_vsone, qreq_vsone_ = query_vsone_pairs(ibs, vsone_query_pairs, False)
        >>> if qreq_vsone_.qparams.score_normalization:
        >>>    qreq_vsone_.load_score_normalizer()
        >>> # execute function
        >>> result = augment_vsone_with_vsmany(vsone_query_pairs, qaid2_qres_vsone, qaid2_qres_vsmany, qreq_vsone_)
        >>> # verify results
        >>> cm = qaid2_qres_vsone[qaid]
        >>> assert np.all(ut.inbounds(cm.aid2_fsv[daids[0]], 0.0, 1.0, eq=True))
        >>> assert np.all(ut.inbounds(cm.aid2_score[daids[0]], 0.0, 1.0, eq=True))
        >>> print(result)
    """
    for qaid, top_aids in vsone_query_pairs:
        qres_vsone = qaid2_qres_vsone[qaid]
        qres_vsmany = qaid2_qres_vsmany[qaid]
        #with ut.EmbedOnException():
        if len(top_aids) == 0:
            print('Warning: top_aids is len 0')
            qaid = qres_vsmany.qaid
            continue
        qres_vsone.assert_self()
        qres_vsmany.assert_self()
        filtkey = hstypes.FiltKeys.DISTINCTIVENESS
        VSMANY_DISTINCTIVENESS = qreq_vsone_.qparams.use_external_distinctiveness
        # VSMANY DISTINCTIVENESS
        if True or VSMANY_DISTINCTIVENESS:
            newfsv_list, newscore_aids = get_new_qres_distinctiveness(qres_vsone, qres_vsmany, top_aids, filtkey)
        else:
            # VSONE DISTINCTIVENESS
            newfsv_list, newscore_aids = get_extern_distinctiveness(qreq_vsone_, qres_vsone)
        #with ut.EmbedOnException():
        apply_new_qres_filter_scores(
            qreq_vsone_, qres_vsone, newfsv_list, newscore_aids, filtkey)


def new_feature_score_dimension(cm, daid):
    """ returns new fsv vectors but does not apply them """
    shape = (cm.aid2_fsv[daid].shape[0], 1)
    new_scores_vsone = np.full(shape, np.nan)
    new_fsv = np.hstack((cm.aid2_fsv[daid], new_scores_vsone))
    #new_scores = new_fsv.T[-1].T
    return new_fsv


@profile
def get_new_qres_distinctiveness(qres_vsone, qres_vsmany, top_aids, filtkey):
    """
    gets the distinctiveness score from vsmany and applies it to vsone

    CommandLine:
        python -m ibeis.algo.hots.special_query --exec-get_new_qres_distinctiveness

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.hots.special_query import *  # NOQA
        >>> ibs, valid_aids = testdata_special_query()
        >>> qaids = valid_aids[0:1]
        >>> daids = valid_aids[1:]
        >>> qaid = qaids[0]
        >>> filtkey = hstypes.FiltKeys.DISTINCTIVENESS
        >>> use_cache = False
        >>> # execute function
        >>> qaid2_qres_vsmany, qreq_vsmany_ = query_vsmany_initial(ibs, qaids, daids, use_cache)
        >>> vsone_query_pairs = build_vsone_shortlist(ibs, qaid2_qres_vsmany)
        >>> qaid2_qres_vsone, qreq_vsone_ = query_vsone_pairs(ibs, vsone_query_pairs, use_cache)
        >>> qreq_vsone_.load_score_normalizer()
        >>> qres_vsone = qaid2_qres_vsone[qaid]
        >>> qres_vsmany = qaid2_qres_vsmany[qaid]
        >>> top_aids = vsone_query_pairs[0][1]
        >>> # verify results
        >>> newfsv_list, newscore_aids = get_new_qres_distinctiveness(qres_vsone, qres_vsmany, top_aids, filtkey)
    """
    newfsv_list = []
    newscore_aids = []

    # make sure filter does not already exist
    scorex_vsone  = ut.listfind(qres_vsone.filtkey_list, filtkey)
    # Make new filtkey_list
    new_filtkey_list = qres_vsone.filtkey_list[:]
    new_filtkey_list.append(filtkey)
    newscore_aids = top_aids[:]
    for daid in top_aids:
        # Distinctiveness is mostly independent of the vsmany database results
        if daid not in qres_vsone.aid2_fm:  # or daid not in qres_vsmany.aid2_fm):
            # no matches to work with
            continue
        if scorex_vsone is None:
            new_fsv_vsone = new_feature_score_dimension(qres_vsone, daid)
            assert len(new_filtkey_list) == len(new_fsv_vsone.T), 'filter length is not consistent'
        fm_vsone  = qres_vsone.aid2_fm[daid]
        qfx_vsone = fm_vsone.T[0]
        # Use vsmany as the distinctivness
        # Get the distinctiveness score from the neighborhood
        # around each query point in the vsmany query result
        norm_sqared_dist = qres_vsmany.qfx2_dist.T[-1].take(qfx_vsone)
        norm_dist = np.sqrt(norm_sqared_dist)
        # FIXME: params not used
        # but this is probably depricated anyway
        dcvs_power, dcvs_max_clip, dcvs_min_clip = 1.0, 1.0, 0.0
        dstncvs = distinctiveness_normalizer.compute_distinctiveness_from_dist(norm_dist, dcvs_power, dcvs_max_clip, dcvs_min_clip)
        # Copy new scores to the new fsv vector
        new_fsv_vsone.T[-1].T[:] = dstncvs  #
        newfsv_list.append(new_fsv_vsone)
    return newfsv_list, newscore_aids


@profile
def get_extern_distinctiveness(qreq_, cm, **kwargs):
    r"""
    Uses distinctivness normalizer class (which uses predownloaded models)
    to normalize the distinctivness of a keypoint for query points.


    IDEA:
        because we have database points as well we can use the distance between
        normalizer of the query point and the normalizer of the database point.
        They should have a similar normalizer if they are a correct match AND
        nondistinctive.

    Args:
        qreq_ (QueryRequest):  query request object with hyper-parameters
        cm (QueryResult):  object of feature correspondences and scores

    Returns:
        tuple: (new_fsv_list, daid_list)

    CommandLine:
        python -m ibeis.algo.hots.special_query --test-get_extern_distinctiveness

    Example:
        >>> # SLOW_DOCTEST
        >>> from ibeis.algo.hots.special_query import *  # NOQA
        >>> import ibeis
        >>> # build test data
        >>> ibs = ibeis.opendb('testdb1')
        >>> daids = ibs.get_valid_aids(species=ibeis.const.TEST_SPECIES.ZEB_PLAIN)
        >>> qaids = daids[0:1]
        >>> cfgdict = dict(codename='vsone_unnorm_dist_ratio_extern_distinctiveness')
        >>> qreq_ = ibs.new_query_request(qaids, daids, cfgdict=cfgdict)
        >>> #qreq_.lazy_load()
        >>> cm = ibs.query_chips(qreq_=qreq_, use_cache=False, save_qcache=False)[0]
        >>> # execute function
        >>> (new_fsv_list, daid_list) = get_extern_distinctiveness(qreq_, cm)
        >>> # verify results
        >>> assert all([fsv.shape[1] == 1 + len(cm.filtkey_list) for fsv in new_fsv_list])
        >>> assert all([np.all(fsv.T[-1] >= 0) for fsv in new_fsv_list])
        >>> assert all([np.all(fsv.T[-1] <= 1) for fsv in new_fsv_list])
    """
    dstcnvs_normer = qreq_.dstcnvs_normer
    assert dstcnvs_normer is not None, 'must have loaded normalizer'
    filtkey = hstypes.FiltKeys.DISTINCTIVENESS
    # make sure filter does not already exist
    scorex_vsone  = ut.listfind(cm.filtkey_list, filtkey)
    assert scorex_vsone is None, 'already applied distinctivness'
    daid_list = list(six.iterkeys(cm.aid2_fsv))
    # Find subset of features to get distinctivness of
    qfxs_list = [cm.aid2_fm[daid].T[0] for daid in daid_list]
    query_vecs = qreq_.ibs.get_annot_vecs(cm.qaid, config2_=qreq_.qparams)
    # there might be duplicate feature indexes in the list of feature index
    # lists. We can use to perform neighbor lookup more efficiently by only
    # performing a single query per feature index. Utool does the mapping for us
    def rowid_distinctivness(unique_flat_qfx_list, dstcnvs_normer=None, query_vecs=None, **kwargs):
        # Take only the unique vectors
        unique_flat_subvecs = query_vecs.take(unique_flat_qfx_list, axis=0)
        unique_flat_dstcvns = dstcnvs_normer.get_distinctiveness(unique_flat_subvecs, **kwargs)
        return unique_flat_dstcvns[:, None]

    aug_fsv_list = ut.unflat_unique_rowid_map(
        rowid_distinctivness, qfxs_list,
        dstcnvs_normer=dstcnvs_normer, query_vecs=query_vecs, **kwargs)

    if False:
        with ut.Timer('time1'):
            aug_fsv_list = ut.unflat_unique_rowid_map(
                rowid_distinctivness, qfxs_list, dstcnvs_normer=dstcnvs_normer,
                query_vecs=query_vecs)
        with ut.Timer('time2'):
            # Less efficient way to do this
            _vecs_list = [query_vecs.take(qfxs, axis=0) for qfxs in qfxs_list]
            _aug_fsv_list = [dstcnvs_normer.get_distinctiveness(_vecs)[:, None] for _vecs in _vecs_list]
        isequal_list = [np.all(np.equal(*tup)) for tup in zip(aug_fsv_list, _aug_fsv_list)]
        assert all(isequal_list), 'utool is broken'

    # Compute the distinctiveness as the augmenting score
    # ensure the shape is (X, 1)
    # Stack the new and augmenting scores
    old_fsv_list = [cm.aid2_fsv[daid] for daid  in daid_list]
    new_fsv_list = list(map(np.hstack, zip(old_fsv_list, aug_fsv_list)))

    # FURTHER HACKS TO SCORING
    #if 'fg_power' in kwargs:
    for filtkey in hstypes.WEIGHT_FILTERS:
        key = filtkey  + '_power'
        if key in kwargs:
            _power = kwargs[key]
            _index = ut.listfind(cm.filtkey_list, filtkey)
            for fsv in new_fsv_list:
                fsv.T[_index] **= _power
    #new_aid2_fsv = dict(zip(daid_list, new_fsv_list))
    return new_fsv_list, daid_list


def product_scoring(new_fsv_vsone):
    """ product of all weights """
    new_fs_vsone = new_fsv_vsone.prod(axis=1)
    return new_fs_vsone


@profile
def apply_new_qres_filter_scores(qreq_vsone_, qres_vsone, newfsv_list, newscore_aids, filtkey):
    r"""
    applies the new filter scores vectors to a query result and updates other
    scores

    Args:
        qres_vsone (QueryResult):  object of feature correspondences and scores
        newfsv_list (list):
        newscore_aids (?):
        filtkey (?):

    CommandLine:
        python -m ibeis.algo.hots.special_query --test-apply_new_qres_filter_scores

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.hots.special_query import *  # NOQA
        >>> ibs, valid_aids = testdata_special_query()
        >>> qaids = valid_aids[0:1]
        >>> daids = valid_aids[1:]
        >>> qaid = qaids[0]
        >>> filtkey = hstypes.FiltKeys.DISTINCTIVENESS
        >>> use_cache = False
        >>> qaid2_qres_vsmany, qreq_vsmany_ = query_vsmany_initial(ibs, qaids, daids, use_cache)
        >>> vsone_query_pairs = build_vsone_shortlist(ibs, qaid2_qres_vsmany)
        >>> qaid2_qres_vsone, qreq_vsone_ = query_vsone_pairs(ibs, vsone_query_pairs, use_cache)
        >>> qreq_vsone_.load_score_normalizer()
        >>> qres_vsone = qaid2_qres_vsone[qaid]
        >>> qres_vsmany = qaid2_qres_vsmany[qaid]
        >>> top_aids = vsone_query_pairs[0][1]
        >>> newfsv_list, newscore_aids = get_new_qres_distinctiveness(qres_vsone, qres_vsmany, top_aids, filtkey)
        >>> apply_new_qres_filter_scores(qreq_vsone_, qres_vsone, newfsv_list, newscore_aids, filtkey)

    Ignore:
        qres_vsone.show_top(ibs, name_scoring=True)
        print(qres_vsone.get_inspect_str(ibs=ibs, name_scoring=True))

        print(qres_vsmany.get_inspect_str(ibs=ibs, name_scoring=True))

    """
    assert ut.listfind(qres_vsone.filtkey_list, filtkey) is None
    # HACK to update result cfgstr
    qres_vsone.filtkey_list.append(filtkey)
    qres_vsone.cfgstr = qreq_vsone_.get_cfgstr()
    # Find positions of weight filters and score filters
    # so we can apply a weighted average
    #numer_filters  = [hstypes.FiltKeys.LNBNN, hstypes.FiltKeys.RATIO]

    weight_filters = hstypes.WEIGHT_FILTERS
    weight_filtxs, nonweight_filtxs = vt.index_partition(qres_vsone.filtkey_list, weight_filters)

    for new_fsv_vsone, daid in zip(newfsv_list, newscore_aids):
        #scorex_vsone  = ut.listfind(qres_vsone.filtkey_list, filtkey)
        #if scorex_vsone is None:
        # TODO: add spatial verification as a filter score
        # augment the vsone scores
        # TODO: paramaterize
        weighted_ave_score = True
        if weighted_ave_score:
            # weighted average scoring
            new_fs_vsone = vt.weighted_average_scoring(new_fsv_vsone, weight_filtxs, nonweight_filtxs)
        else:
            # product scoring
            new_fs_vsone = product_scoring(new_fsv_vsone)
        new_score_vsone = new_fs_vsone.sum()
        qres_vsone.aid2_fsv[daid]   = new_fsv_vsone
        qres_vsone.aid2_fs[daid]    = new_fs_vsone
        qres_vsone.aid2_score[daid] = new_score_vsone
        # FIXME: this is not how to compute new probability
        #if qres_vsone.aid2_prob is not None:
        #    qres_vsone.aid2_prob[daid] = qres_vsone.aid2_score[daid]

    # This is how to compute new probability
    if qreq_vsone_.qparams.score_normalization:
        # FIXME: TODO: Have unsupported scores be represented as Nones
        # while score normalizer is still being trained.
        normalizer = qreq_vsone_.normalizer
        daid2_score = qres_vsone.aid2_score
        score_list = list(six.itervalues(daid2_score))
        daid_list  = list(six.iterkeys(daid2_score))
        prob_list = normalizer.normalize_score_list(score_list)
        daid2_prob = dict(zip(daid_list, prob_list))
        qres_vsone.aid2_prob = daid2_prob


def verbose_report_results(ibs, qaids, qaid2_qres_vsone, qaid2_qres_vsmany):
    for qaid in qaids:
        qres_vsone = qaid2_qres_vsone[qaid]
        qres_vsmany = qaid2_qres_vsmany[qaid]
        if qres_vsmany is not None:
            vsmanyinspectstr = qres_vsmany.get_inspect_str(ibs=ibs, name_scoring=True)
            print(ut.msgblock('VSMANY-INITIAL-RESULT qaid=%r' % (qaid,), vsmanyinspectstr))
        if qres_vsone is not None:
            vsoneinspectstr = qres_vsone.get_inspect_str(ibs=ibs, name_scoring=True)
            print(ut.msgblock('VSONE-VERIFIED-RESULT qaid=%r' % (qaid,), vsoneinspectstr))


def test_vsone_verified(ibs):
    """
    hack in vsone-reranking

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.all_imports import *  # NOQA
        >>> #reload_all()
        >>> from ibeis.algo.hots.automated_matcher import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('PZ_MTEST')
        >>> test_vsone_verified(ibs)
    """
    import plottool as pt
    #qaids = ibs.get_easy_annot_rowids()
    nids = ibs.get_valid_nids(filter_empty=True)
    grouped_aids_ = ibs.get_name_aids(nids)
    grouped_aids = list(filter(lambda x: len(x) > 1, grouped_aids_))
    items_list = grouped_aids

    sample_aids = ut.flatten(ut.sample_lists(items_list, num=2, seed=0))
    qaid2_qres, qreq_ = query_vsone_verified(ibs, sample_aids, sample_aids)
    for cm in ut.InteractiveIter(list(six.itervalues(qaid2_qres))):
        pt.close_all_figures()
        fig = cm.ishow_top(ibs)
        fig.show()
    #return qaid2_qres


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.algo.hots.special_query
        python -m ibeis.algo.hots.special_query --allexamples
        python -m ibeis.algo.hots.special_query --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
