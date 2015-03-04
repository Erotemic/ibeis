from __future__ import absolute_import, division, print_function
#import six
#import numpy as np
#from ibeis.model.hots import hstypes
import utool as ut
#profile = ut.profile
print, print_,  printDBG, rrr, profile = ut.inject(__name__, '[_plh]', DEBUG=False)


VERB_PIPELINE = ut.get_argflag(('--verb-pipeline', '--verb-pipe')) or ut.VERYVERBOSE
VERB_TESTDATA = ut.get_argflag('--verb-testdata') or ut.VERYVERBOSE


def testrun_pipeline_upto(qreq_, stop_node=None, verbose=True):
    r"""
    convinience: runs pipeline for tests
    this should mirror request_ibeis_query_L0

    Ignore:
        >>> import utool as ut
        >>> source = ut.get_func_sourcecode(request_ibeis_query_L0)
        >>> stripsource = source[:]
        >>> stripsource = ut.strip_line_comments(stripsource)
        >>> triplequote1 = ut.TRIPLE_DOUBLE_QUOTE
        >>> triplequote2 = ut.TRIPLE_SINGLE_QUOTE
        >>> docstr_regex1 = 'r?' + triplequote1 + '.* + ' + triplequote1 + '\n    '
        >>> docstr_regex2 = 'r?' + triplequote2 + '.* + ' + triplequote2 + '\n    '
        >>> stripsource = ut.regex_replace(docstr_regex1, '', stripsource)
        >>> stripsource = ut.regex_replace(docstr_regex2, '', stripsource)
        >>> stripsource = ut.strip_line_comments(stripsource)
        >>> print(stripsource)
    """
    from ibeis.model.hots.pipeline import (
        nearest_neighbors, baseline_neighbor_filter, weight_neighbors,
        build_chipmatches, spatial_verification,
        chipmatch_to_resdict, vsone_reranking)

    qreq_.lazy_load(verbose=verbose)
    #---
    if stop_node == 'nearest_neighbors':
        return locals()
    nns_list = nearest_neighbors(qreq_, verbose=verbose)
    #---
    if stop_node == 'baseline_neighbor_filter':
        return locals()
    nnvalid0_list = baseline_neighbor_filter(qreq_, nns_list, verbose=verbose)
    #---
    if stop_node == 'weight_neighbors':
        return locals()
    filtkey_list, filtweights_list, filtvalids_list = weight_neighbors(qreq_, nns_list, nnvalid0_list, verbose=verbose)
    #---
    if stop_node == 'filter_neighbors':
        raise AssertionError('no longer exists')
    #---
    if stop_node == 'build_chipmatches':
        return locals()
    cm_list_FILT = build_chipmatches(qreq_, nns_list, nnvalid0_list, filtkey_list, filtweights_list, filtvalids_list, verbose=verbose)
    #---
    if stop_node == 'spatial_verification':
        return locals()
    cm_list_SVER = spatial_verification(qreq_, cm_list_FILT, verbose=verbose)
    #---
    if stop_node == 'vsone_reranking':
        return locals()
    if qreq_.qparams.rrvsone_on:
        # VSONE RERANKING
        cm_list_VSONERR = vsone_reranking(qreq_, cm_list_SVER, verbose=verbose)
        cm_list = cm_list_VSONERR
    else:
        cm_list = cm_list_SVER
    #---
    if stop_node == 'chipmatch_to_resdict':
        return locals()
    qaid2_qres = chipmatch_to_resdict(qreq_, cm_list, verbose=verbose)

    assert False, 'unknown stop_node=%r' % (stop_node,)

    #qaid2_svtups = qreq_.metadata['qaid2_svtups']
    return locals()


def get_pipeline_testdata(dbname=None, cfgdict=None, qaid_list=None,
                          daid_list=None, defaultdb='testdb1', cmdline_ok=True,
                          preload=True):
    """
    Gets testdata for pipeline defined by tests / and or command line

    Args:
        cmdline_ok : if false does not check command line

    CommandLine:
        python -m ibeis.model.hots._pipeline_helpers --test-get_pipeline_testdata

    Example:
        >>> # ENABLE_DOCTEST
        >>> import ibeis  # NOQA
        >>> from ibeis.model.hots import _pipeline_helpers as plh
        >>> cfgdict = dict(pipeline_root='vsone', codename='vsone')
        >>> ibs, qreq_ = plh.get_pipeline_testdata(cfgdict=cfgdict)
        >>> print(qreq_.get_external_daids())
        >>> print(qreq_.get_external_qaids())
        >>> print(qreq_.qparams.query_cfgstr)
    """
    import ibeis
    from ibeis.model.hots import query_request
    # Allow commandline specification if paramaters are not specified in tests
    if cfgdict is None:
        cfgdict = {}

    if cmdline_ok:
        from ibeis.model import Config
        # Allow specification of db and qaids/daids
        if dbname is not None:
            defaultdb = dbname
        dbname = ut.get_argval('--db', str, defaultdb)
        qaid_list = ut.get_argval(('--qaid_list', '--qaid'), list, qaid_list)
        daid_list = ut.get_argval('--daid_list', list, daid_list)
        #if 'codename' not in cfgdict:
        # Allow commond line specification of all query params
        default_cfgdict = dict(Config.parse_config_items(Config.QueryConfig()))
        default_cfgdict.update(cfgdict)
        _orig_cfgdict = cfgdict
        force_keys = set(list(_orig_cfgdict.keys()))
        cfgdict = ut.util_arg.argparse_dict(default_cfgdict, verbose=not
                                            ut.QUIET, only_specified=True,
                                            force_keys=force_keys)
        if VERB_PIPELINE or VERB_TESTDATA:
            print('[plh] cfgdict = ' + ut.dict_str(cfgdict))
    ibs = ibeis.opendb(dbname)
    if qaid_list is None:
        if dbname == 'testdb1':
            qaid_list = [1]
        if dbname == 'GZ_ALL':
            qaid_list = [1032]
        if dbname == 'PZ_ALL':
            qaid_list = [1, 3, 5, 9]
        else:
            qaid_list = [1]
    if daid_list is None:
        daid_list = ibs.get_valid_aids()
        if dbname == 'testdb1':
            daid_list = daid_list[0:min(5, len(daid_list))]
    elif daid_list == 'all':
        daid_list = ibs.get_valid_aids()
    ibs = ibeis.test_main(db=dbname)

    if 'with_metadata' not in cfgdict:
        cfgdict['with_metadata'] = True
    qreq_ = query_request.new_ibeis_query_request(ibs, qaid_list, daid_list, cfgdict=cfgdict)
    if preload:
        qreq_.lazy_load()
    return ibs, qreq_


#+--- OTHER TESTDATA FUNCS ---


def testdata_pre_weight_neighbors(defaultdb='testdb1', qaid_list=[1, 2], daid_list=None, codename='vsmany', cfgdict=None):
    if cfgdict is None:
        cfgdict = dict(codename=codename)
    ibs, qreq_ = get_pipeline_testdata(
        qaid_list=qaid_list, daid_list=daid_list, defaultdb=defaultdb, cfgdict=cfgdict)
    locals_ = testrun_pipeline_upto(qreq_, 'weight_neighbors')
    nns_list, nnvalid0_list = ut.dict_take(locals_, ['nns_list', 'nnvalid0_list'])
    return ibs, qreq_, nns_list, nnvalid0_list


def testdata_sparse_matchinfo_nonagg(defaultdb='testdb1', codename='vsmany'):
    ibs, qreq_, args = testdata_pre_build_chipmatch(defaultdb=defaultdb, codename=codename)
    nns_list, nnvalid0_list, filtkey_list, filtweights_list, filtvalids_list = args
    if qreq_.qparams.vsone:
        interal_index = 1
    else:
        interal_index = 0
    qaid = qreq_.get_external_qaids()[0]
    daid = qreq_.get_external_daids()[1]
    qfx2_idx, _     = nns_list[interal_index]
    qfx2_valid0     = nnvalid0_list[interal_index]
    qfx2_score_list = filtweights_list[interal_index]
    qfx2_valid_list = filtvalids_list[interal_index]
    args = qfx2_idx, qfx2_valid0, qfx2_score_list, qfx2_valid_list
    return qreq_, qaid, daid, args


def testdata_pre_build_chipmatch(defaultdb='testdb1', codename='vsmany'):
    cfgdict = dict(codename=codename)
    ibs, qreq_ = get_pipeline_testdata(defaultdb=defaultdb, cfgdict=cfgdict)
    locals_ = testrun_pipeline_upto(qreq_, 'build_chipmatches')
    args = ut.dict_take(locals_, ['nns_list', 'nnvalid0_list', 'filtkey_list', 'filtweights_list', 'filtvalids_list'])
    return ibs, qreq_, args


def testdata_pre_baselinefilter(defaultdb='testdb1', qaid_list=None, daid_list=None, codename='vsmany'):
    cfgdict = dict(codename=codename)
    ibs, qreq_ = get_pipeline_testdata(
        qaid_list=qaid_list, daid_list=daid_list, defaultdb=defaultdb, cfgdict=cfgdict)
    locals_ = testrun_pipeline_upto(qreq_, 'baseline_neighbor_filter')
    nns_list, = ut.dict_take(locals_, ['nns_list'])
    return qreq_, nns_list


def testdata_pre_sver(defaultdb='PZ_MTEST', qaid_list=None, daid_list=None):
    """
        >>> from ibeis.model.hots._pipeline_helpers import *  # NOQA
    """
    #from ibeis.model import Config
    cfgdict = dict()
    ibs, qreq_ = get_pipeline_testdata(
        qaid_list=qaid_list, daid_list=daid_list, defaultdb=defaultdb, cfgdict=cfgdict)
    locals_ = testrun_pipeline_upto(qreq_, 'spatial_verification')
    cm_list = locals_['cm_list_FILT']
    #nnfilts_list   = locals_['nnfilts_list']
    return ibs, qreq_, cm_list


def testdata_post_sver(defaultdb='PZ_MTEST', qaid_list=None, daid_list=None, codename='vsmany', cfgdict=None):
    """
        >>> from ibeis.model.hots._pipeline_helpers import *  # NOQA
    """
    #from ibeis.model import Config
    if cfgdict is None:
        cfgdict = dict(codename=codename)
    ibs, qreq_ = get_pipeline_testdata(
        qaid_list=qaid_list, daid_list=daid_list, defaultdb=defaultdb, cfgdict=cfgdict)
    locals_ = testrun_pipeline_upto(qreq_, 'vsone_reranking')
    cm_list = locals_['cm_list_SVER']
    #nnfilts_list   = locals_['nnfilts_list']
    return ibs, qreq_, cm_list


def testdata_pre_vsonerr(defaultdb='PZ_MTEST', qaid_list=[1], daid_list='all'):
    """
        >>> from ibeis.model.hots._pipeline_helpers import *  # NOQA
    """
    cfgdict = dict(sver_weighting=True, codename='vsmany', rrvsone_on=True)
    # Get pipeline testdata for this configuration
    ibs, qreq_ = get_pipeline_testdata(
        cfgdict=cfgdict, qaid_list=qaid_list, daid_list=daid_list, defaultdb=defaultdb, cmdline_ok=True)
    qaid_list = qreq_.get_external_qaids().tolist()
    qaid = qaid_list[0]
    #daid_list = qreq_.get_external_daids().tolist()
    if len(ibs.get_annot_groundtruth(qaid)) == 0:
        print('WARNING: qaid=%r has no groundtruth' % (qaid,))
    locals_ = testrun_pipeline_upto(qreq_, 'vsone_reranking')
    cm_list = locals_['cm_list_SVER']
    return ibs, qreq_, cm_list, qaid_list


def testdata_scoring(defaultdb='PZ_MTEST', qaid_list=[1], daid_list='all'):
    from ibeis.model.hots import vsone_pipeline
    ibs, qreq_, prior_cm = testdata_matching(defaultdb=defaultdb, qaid_list=qaid_list, daid_list=daid_list)
    config = qreq_.qparams
    cm = vsone_pipeline.refine_matches(qreq_, prior_cm, config)
    cm.evaluate_dnids(qreq_.ibs)
    return qreq_, cm


def testdata_matching(*args, **kwargs):
    """
        >>> from ibeis.model.hots._pipeline_helpers import *  # NOQA
    """
    from ibeis.model.hots import vsone_pipeline
    from ibeis.model.hots import scoring
    ibs, qreq_, cm_list, qaid_list  = testdata_pre_vsonerr(*args, **kwargs)
    vsone_pipeline.prepare_vsmany_chipmatch(qreq_, cm_list)
    nNameShortlist = qreq_.qparams.nNameShortlistVsone
    nAnnotPerName  = qreq_.qparams.nAnnotPerNameVsOne
    scoring.score_chipmatch_list(qreq_, cm_list, 'nsum')
    vsone_pipeline.prepare_vsmany_chipmatch(qreq_, cm_list)
    cm_shortlist = scoring.make_chipmatch_shortlists(qreq_, cm_list, nNameShortlist, nAnnotPerName)
    prior_cm      = cm_shortlist[0]
    return ibs, qreq_, prior_cm


#L_______


def print_nearest_neighbor_assignments(qvecs_list, nns_list):
    nQAnnots = len(qvecs_list)
    nTotalDesc = sum(map(len, qvecs_list))
    nTotalNN = sum([qfx2_idx.size for (qfx2_idx, qfx2_dist) in nns_list])
    print('[hs] * assigned %d desc (from %d annots) to %r nearest neighbors'
          % (nTotalDesc, nQAnnots, nTotalNN))


def _self_verbose_check(qfx2_notsamechip, qfx2_valid0):
    nInvalidChips = ((True - qfx2_notsamechip)).sum()
    nNewInvalidChips = (qfx2_valid0 * (True - qfx2_notsamechip)).sum()
    total = qfx2_valid0.size
    print('[hs] * self invalidates %d/%d assignments' % (nInvalidChips, total))
    print('[hs] * %d are newly invalided by self' % (nNewInvalidChips))


def _samename_verbose_check(qfx2_notsamename, qfx2_valid0):
    nInvalidNames = ((True - qfx2_notsamename)).sum()
    nNewInvalidNames = (qfx2_valid0 * (True - qfx2_notsamename)).sum()
    total = qfx2_valid0.size
    print('[hs] * nid invalidates %d/%d assignments' % (nInvalidNames, total))
    print('[hs] * %d are newly invalided by nid' % nNewInvalidNames)


def _sameimg_verbose_check(qfx2_notsameimg, qfx2_valid0):
    nInvalidImgs = ((True - qfx2_notsameimg)).sum()
    nNewInvalidImgs = (qfx2_valid0 * (True - qfx2_notsameimg)).sum()
    total = qfx2_valid0.size
    print('[hs] * gid invalidates %d/%d assignments' % (nInvalidImgs, total))
    print('[hs] * %d are newly invalided by gid' % nNewInvalidImgs)


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.model.hots._pipline_helpers
        python -m ibeis.model.hots._pipline_helpers --allexamples
        python -m ibeis.model.hots._pipline_helpers --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
