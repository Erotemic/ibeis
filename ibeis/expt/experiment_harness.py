# -*- coding: utf-8 -*-
"""
Runs many queries and keeps track of some results
"""
from __future__ import absolute_import, division, print_function
import sys
import textwrap
import numpy as np
#import six
import utool as ut
from functools import partial
from ibeis.expt import experiment_helpers
#from ibeis.expt import experiment_configs
#from ibeis.expt import experiment_printres
#from ibeis.expt import experiment_drawing
from ibeis.expt import test_result
#from ibeis.expt import annotation_configs
#from ibeis.expt import cfghelpers
print, print_, printDBG, rrr, profile = ut.inject(
    __name__, '[expt_harn]')

NOMEMORY = ut.get_argflag('--nomemory')
TESTRES_VERBOSITY = 2 - (2 * ut.QUIET)
NOCACHE_TESTRES =  ut.get_argflag(('--nocache-testres', '--nocache-big'), False)
USE_BIG_TEST_CACHE = (not ut.get_argflag(('--no-use-testcache',
                                          '--nocache-test')) and ut.USE_CACHE and
                      not NOCACHE_TESTRES)
TEST_INFO = True

DRY_RUN =  ut.get_argflag(('--dryrun', '--dry'))  # dont actually query. Just print labels and stuff


def run_test_configurations2(ibs, acfg_name_list, test_cfg_name_list,
                             use_cache=None, qaid_override=None,
                             daid_override=None, initial_aids=None):
    """
    Loops over annot configs.

    Try and use this function as a starting point to clean up this module.
    The code is getting too untenable.

    CommandLine:
        python -m ibeis.expt.experiment_harness --exec-run_test_configurations2

    Example:
        >>> # SLOW_DOCTEST
        >>> from ibeis.expt.experiment_harness import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb(defaultdb='PZ_MTEST')
        >>> default_acfgstrs = ['controlled:qsize=20,dpername=1,dsize=10', 'controlled:qsize=20,dpername=10,dsize=100']
        >>> acfg_name_list = ut.get_argval(('--aidcfg', '--acfg', '-a'), type_=list, default=default_acfgstrs)
        >>> test_cfg_name_list = ut.get_argval('-t', type_=list, default=['custom', 'custom:fg_on=False'])
        >>> use_cache = False
        >>> testres_list = run_test_configurations2(ibs, acfg_name_list, test_cfg_name_list, use_cache)
    """
    testnameid = ibs.get_dbname() + ' ' + str(test_cfg_name_list) + str(acfg_name_list)
    lbl = '[harn] TEST_CFG ' + str(test_cfg_name_list) + str(acfg_name_list)

    # Generate list of database annotation configurations
    if len(acfg_name_list) == 0:
        raise ValueError('must give acfg name list')

    acfg_list, expanded_aids_list = experiment_helpers.get_annotcfg_list(
        ibs, acfg_name_list, qaid_override=qaid_override,
        daid_override=daid_override, initial_aids=initial_aids)
    # Generate list of query pipeline param configs
    cfgdict_list, pipecfg_list = experiment_helpers.get_pipecfg_list(
        test_cfg_name_list, ibs=ibs)

    cfgx2_lbl = experiment_helpers.get_varied_pipecfg_lbls(cfgdict_list)

    if ut.NOT_QUIET:
        ut.colorprint(textwrap.dedent("""

        [harn]================
        [harn] experiment_harness.test_configurations2()""").strip(), 'white')
        msg = '[harn] Running %s using %s and %s' % (
            ut.quantity_str('test', len(acfg_list) * len(pipecfg_list)),
            ut.quantity_str('pipeline config', len(pipecfg_list)),
            ut.quantity_str('annot config', len(acfg_list)),
        )
        ut.colorprint(msg, 'white')

    testres_list = []

    nAcfg = len(acfg_list)

    expanded_aids_iter = ut.ProgressIter(expanded_aids_list,
                                         lbl='annot config',
                                         freq=1, autoadjust=False,
                                         enabled=ut.NOT_QUIET)

    #if ut.get_argflag(('--pcfginfo', '--pipecfginfo')):
    #    ut.colorprint('Requested PcfgInfo for tests... ', 'red')
    #    for pcfgx, pipecfg in enumerate(pipecfg_list):
    #        print('+--- %d / %d ===' % (pcfgx, (len(pipecfg_list))))
    #        print(pipecfg.get_cfgstr())
    #        print('L___')
    #    ut.colorprint('Finished Reporting PcfgInfo. Exiting', 'red')
    #    sys.exit(1)

    #if ut.get_argflag(('--acfginfo', '--aidcfginfo')):
    #    # Print info about annots for the test
    #    ut.colorprint('Requested AcfgInfo for tests... ', 'red')
    #    annotation_configs.print_acfg_list(acfg_list, expanded_aids_list, ibs)
    #    ut.colorprint('Finished Reporting AcfgInfo. Exiting', 'red')
    #    sys.exit(1)

    for acfgx, (qaids, daids) in enumerate(expanded_aids_iter):
        assert len(qaids) != 0, (
            '[harness] No query annotations specified')
        assert len(daids) != 0, (
            '[harness] No database annotations specified')
        acfg = acfg_list[acfgx]
        if ut.NOT_QUIET:
            ut.colorprint('\n---Annot config testnameid=%r' % (
                testnameid,), 'turquoise')
        subindexer_partial = partial(ut.ProgressIter, parent_index=acfgx,
                                     parent_nTotal=nAcfg, enabled=ut.NOT_QUIET)
        testres = run_test_configurations(
            ibs, qaids, daids, pipecfg_list,
            cfgx2_lbl, cfgdict_list, lbl,
            testnameid, use_cache=use_cache,
            subindexer_partial=subindexer_partial)
        if DRY_RUN:
            continue
        testres.acfg = acfg
        testres.test_cfg_name_list = test_cfg_name_list
        testres_list.append(testres)
    if DRY_RUN:
        print('DRYRUN: Cannot continue past run_test_configurations2')
        sys.exit(0)

    return testres_list


def get_big_test_cache_info(ibs, cfgx2_qreq_):
    if ut.is_developer():
        import ibeis
        from os.path import dirname, join
        repodir = dirname(ut.get_module_dir(ibeis))
        bt_cachedir = join(repodir, 'BIG_TEST_CACHE2')
    else:
        bt_cachedir = './localdata/BIG_TEST_CACHE2'
    ut.ensuredir(bt_cachedir)
    bt_cachestr = ut.hashstr_arr27([
        qreq_.get_cfgstr(with_query=True)
        for qreq_ in cfgx2_qreq_],
        ibs.get_dbname() + '_cfgs')
    bt_cachename = 'BIGTESTCACHE2'
    return bt_cachedir, bt_cachename, bt_cachestr


@profile
def run_test_configurations(ibs, qaids, daids, pipecfg_list, cfgx2_lbl,
                            cfgdict_list, lbl, testnameid,
                            use_cache=None,
                            subindexer_partial=ut.ProgressIter):
    """

    CommandLine:
        python -m ibeis.expt.experiment_harness --exec-run_test_configurations2

    """
    cfgslice = None
    if cfgslice is not None:
        pipecfg_list = pipecfg_list[cfgslice]

    dbname = ibs.get_dbname()

    if ut.NOT_QUIET:
        print('Constructing query requests')
    cfgx2_qreq_ = [
        ibs.new_query_request(qaids, daids, verbose=False, query_cfg=pipe_cfg)
        for pipe_cfg in ut.ProgressIter(pipecfg_list, lbl='Building qreq_',
                                        enabled=False)
    ]

    if use_cache is None:
        use_cache = USE_BIG_TEST_CACHE

    if use_cache:
        get_big_test_cache_info(ibs, cfgx2_qreq_)
        try:
            cachetup = get_big_test_cache_info(ibs, cfgx2_qreq_)
            testres = ut.load_cache(*cachetup)
            testres.cfgdict_list = cfgdict_list
            testres.cfgx2_lbl = cfgx2_lbl  # hack override
        except IOError:
            pass
        else:
            if ut.NOT_QUIET:
                ut.colorprint('Experiment Harness Cache Hit... Returning', 'turquoise')
            return testres

    cfgx2_cfgresinfo = []
    #nPipeCfg = len(pipecfg_list)
    cfgiter = subindexer_partial(range(len(cfgx2_qreq_)),
                                 lbl='query config',
                                 freq=1, adjust=False,
                                 separate=True)
    # Run each pipeline configuration
    prev_feat_cfgstr = None
    for cfgx in cfgiter:
        qreq_ = cfgx2_qreq_[cfgx]

        ut.colorprint('testnameid=%r' % (
            testnameid,), 'green')
        ut.colorprint('annot_cfgstr = %s' % (
            qreq_.get_cfgstr(with_query=True, with_pipe=False),), 'yellow')
        ut.colorprint('pipe_cfgstr= %s' % (
            qreq_.get_cfgstr(with_data=False),), 'turquoise')
        ut.colorprint('pipe_hashstr = %s' % (
            qreq_.get_pipe_hashstr(),), 'teal')
        if DRY_RUN:
            continue

        indent_prefix = '[%s cfg %d/%d]' % (
            dbname,
            # cfgiter.count (doesnt work when quiet)
            (cfgiter.parent_index * cfgiter.nTotal) + cfgx ,
            cfgiter.nTotal * cfgiter.parent_nTotal
        )

        with ut.Indenter(indent_prefix):
            # Run the test / read cache
            _need_compute = True
            if use_cache:
                # smaller cache for individual configuration runs
                st_cfgstr = qreq_.get_cfgstr(with_query=True)
                bt_cachedir = cachetup[0]
                st_cachedir = ut.unixjoin(bt_cachedir, 'small_tests')
                st_cachename = 'smalltest'
                ut.ensuredir(st_cachedir)
                try:
                    cfgres_info = ut.load_cache(st_cachedir, st_cachename, st_cfgstr)
                except IOError:
                    _need_compute = True
                else:
                    _need_compute = False
            if _need_compute:
                if prev_feat_cfgstr is not None and prev_feat_cfgstr != qreq_.qparams.feat_cfgstr:
                    # Clear features to preserve memory
                    ibs.clear_table_cache()
                    #qreq_.ibs.print_cachestats_str()
                cfgres_info = get_query_result_info(qreq_)
                # record previous feature configuration
                prev_feat_cfgstr = qreq_.qparams.feat_cfgstr
                if use_cache:
                    ut.save_cache(st_cachedir, st_cachename, st_cfgstr, cfgres_info)
        if not NOMEMORY:
            # Store the results
            cfgx2_cfgresinfo.append(cfgres_info)
        else:
            cfgx2_qreq_[cfgx] = None
    if ut.NOT_QUIET:
        ut.colorprint('[harn] Completed running test configurations', 'white')
    if DRY_RUN:
        print('ran tests dryrun mode.')
        return
    if NOMEMORY:
        print('ran tests in memory savings mode. Cannot Print. exiting')
        return
    # Store all pipeline config results in a test result object
    testres = test_result.TestResult(pipecfg_list, cfgx2_lbl, cfgx2_cfgresinfo, cfgx2_qreq_)
    testres.testnameid = testnameid
    testres.lbl = lbl
    testres.cfgdict_list = cfgdict_list
    testres.aidcfg = None
    if use_cache:
        ut.save_cache(*tuple(list(cachetup) + [testres]))
    return testres


@profile
def get_qres_name_result_info(ibs, qres, qreq_):
    """
    these are results per query we care about
     * gt (best correct match) and gf (best incorrect match) rank, their score
       and the difference

    """
    from ibeis.algo.hots import chip_match
    if isinstance(qres, chip_match.ChipMatch2):
        cm = qres
        qaid = cm.qaid
        qnid = cm.qnid
        nscoretup = cm.get_ranked_nids_and_aids()
        sorted_nids, sorted_nscores, sorted_aids, sorted_scores = nscoretup
    else:
        qaid = qres.get_qaid()
        qnid = ibs.get_annot_name_rowids(qaid)
        nscoretup = qres.get_nscoretup(ibs)
        (sorted_nids, sorted_nscores, sorted_aids, sorted_scores)  = nscoretup
        sorted_nids = np.array(sorted_nids)
        #sorted_score_diff = -np.diff(sorted_nscores.tolist())

    is_positive = sorted_nids == qnid
    is_negative = np.logical_and(~is_positive, sorted_nids > 0)
    gt_rank = None if not np.any(is_positive) else np.where(is_positive)[0][0]
    gf_rank = None if not np.any(is_negative) else np.nonzero(is_negative)[0][0]

    if gt_rank is None or gf_rank is None:
        if isinstance(qres, chip_match.ChipMatch2):
            gt_aids = ibs.get_annot_groundtruth(cm.qaid, daid_list=qreq_.get_external_daids())
            #gf_aids = ibs.get_annot_groundfalse(cm.qaid, daid_list=qreq_.get_external_daids())
        else:
            gt_aids = cm.get_groundtruth_daids()
            #gf_aids = ibs.get_annot_groundfalse(qres.get_qaid(), daid_list=qres.get_daids())
        #gt_aids = qres.get_groundtruth_aids(ibs)
        cm.get_groundtruth_daids()
        gt_aid = gt_aids[0] if len(gt_aids) > 0 else None
        gf_aid = None
        gt_raw_score = None
        gf_raw_score = None
        scorediff = scorefactor = None
        #scorelogfactor = scoreexpdiff = None
    else:

        gt_aid = sorted_aids[gt_rank][0]
        gf_aid = sorted_aids[gf_rank][0]
        gt_raw_score = sorted_nscores[gt_rank]
        gf_raw_score = sorted_nscores[gf_rank]
        # different comparison methods
        scorediff      = gt_raw_score - gf_raw_score
        scorefactor    = gt_raw_score / gf_raw_score
        #scorelogfactor = np.log(gt_raw_score) / np.log(gf_raw_score)
        #scoreexpdiff   = np.exp(gt_raw_score) - np.log(gf_raw_score)

        # TEST SCORE COMPARISON METHODS
        #truescore  = np.random.rand(4)
        #falsescore = np.random.rand(4)
        #score_diff      = truescore - falsescore
        #scorefactor    = truescore / falsescore
        #scorelogfactor = np.log(truescore) / np.log(falsescore)
        #scoreexpdiff   = np.exp(truescore) - np.exp(falsescore)
        #for x in [score_diff, scorefactor, scorelogfactor, scoreexpdiff]:
        #    print(x.argsort())

    qresinfo_dict = dict(
        bestranks=gt_rank,
        next_bestranks=gf_rank,
        # TODO remove prev dup entries
        gt_rank=gt_rank,
        gf_rank=gf_rank,
        gt_aid=gt_aid,
        gf_aid=gf_aid,
        gt_raw_score=gt_raw_score,
        gf_raw_score=gf_raw_score,
        scorediff=scorediff,
        scorefactor=scorefactor,
        #scorelogfactor=scorelogfactor,
        #scoreexpdiff=scoreexpdiff
    )
    return qresinfo_dict


@profile
def get_query_result_info(qreq_):
    """
    Helper function.

    Runs queries of a specific configuration returns the best rank of each query

    Args:
        qaids (list) : query annotation ids
        daids (list) : database annotation ids

    Returns:
        qx2_bestranks

    CommandLine:
        python -m ibeis.expt.experiment_harness --test-get_query_result_info
        python -m ibeis.expt.experiment_harness --test-get_query_result_info:0
        python -m ibeis.expt.experiment_harness --test-get_query_result_info:1
        python -m ibeis.expt.experiment_harness --test-get_query_result_info:0 --db lynx -a default:qsame_encounter=True,been_adjusted=True,excluderef=True -t default:K=1
        python -m ibeis.expt.experiment_harness --test-get_query_result_info:0 --db lynx -a default:qsame_encounter=True,been_adjusted=True,excluderef=True -t default:K=1 --cmd

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.expt.experiment_harness import *  # NOQA
        >>> import ibeis
        >>> qreq_ = ibeis.main_helpers.testdata_qreq_(a=['default:qindex=0:3,dindex=0:5'])
        >>> #ibs = ibeis.opendb('PZ_MTEST')
        >>> #qaids = ibs.get_valid_aids()[0:3]
        >>> #daids = ibs.get_valid_aids()[0:5]
        >>> #qreq_ = ibs.new_query_request(qaids, daids, verbose=True, cfgdict={})
        >>> cfgres_info = get_query_result_info(qreq_)
        >>> print(ut.dict_str(cfgres_info))

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.expt.experiment_harness import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('PZ_MTEST')
        >>> #cfgdict = dict(codename='vsone')
        >>> # ibs.cfg.query_cfg.codename = 'vsone'
        >>> qaids = ibs.get_valid_aids()[0:3]
        >>> daids = ibs.get_valid_aids()[0:5]
        >>> qreq_ = ibs.new_query_request(qaids, daids, verbose=True, cfgdict={})
        >>> cfgres_info = get_query_result_info(qreq_)
        >>> print(ut.dict_str(cfgres_info))

    Ignore:

        for qaid, qres in six.iteritems(qaid2_qres):
            break
        for qaid, qres in six.iteritems(qaid2_qres):
            qres.ishow_top(ibs)
    """
    # Execute or load query
    #ibs.get_annot_name_rowids(qaids)
    #ibs.get_annot_name_rowids(daids)

    #qreq_ = ibs.new_query_request(qaids, daids, verbose=True)
    #qx2_qres = ibs.query_chips(qreq_=qreq_)
    #assert [x.qaid for x in qx2_qres] == qaids, 'request missmatch'
    #qx2_qres = ut.dict_take(qaid2_qres, qaids)
    # Get the groundtruth that could have been matched in this experiment

    ibs = qreq_.ibs
    if True:
        # TODO: change qres to chipmatch and make multi-chipmatch
        #ut.embed()
        import vtool as vt
        cm_list = qreq_.ibs.query_chips(qreq_=qreq_, return_cm=True)
        qx2_qres = cm_list
        #cm_list = [qres.as_chipmatch() for qres in qx2_qres]
        qaids = qreq_.get_external_qaids()
        qnids = ibs.get_annot_name_rowids(qaids)

        unique_dnids = np.unique(ibs.get_annot_name_rowids(qreq_.get_external_daids()))

        unique_qnids, groupxs = vt.group_indices(qnids)
        cm_group_list = vt.apply_grouping_(cm_list, groupxs)
        qnid2_aggnamescores = {}

        qnx2_nameres_info = []

        nameres_info_list = []
        for qnid, cm_group in zip(unique_qnids, cm_group_list):
            nid2_name_score_group = [
                dict([(nid, cm.name_score_list[nidx]) for nid, nidx in cm.nid2_nidx.items()])
                for cm in cm_group
            ]
            aligned_name_scores = np.array([
                ut.dict_take(nid2_name_score, unique_dnids.tolist(), -np.inf)
                for nid2_name_score in nid2_name_score_group
            ]).T
            name_score_list = np.nanmax(aligned_name_scores, axis=1)
            qnid2_aggnamescores[qnid] = name_score_list
            # sort
            sortx = name_score_list.argsort()[::-1]
            sorted_namescores = name_score_list[sortx]
            sorted_dnids = unique_dnids[sortx]

            ## infer agg name results
            is_positive = sorted_dnids == qnid
            is_negative = np.logical_and(~is_positive, sorted_dnids > 0)
            gt_name_rank = None if not np.any(is_positive) else np.where(is_positive)[0][0]
            gf_name_rank = None if not np.any(is_negative) else np.nonzero(is_negative)[0][0]
            gt_nid = sorted_dnids[gt_name_rank]
            gf_nid = sorted_dnids[gf_name_rank]
            gt_name_score = sorted_namescores[gt_name_rank]
            gf_name_score = sorted_namescores[gf_name_rank]
            qnx2_nameres_info = {}
            qnx2_nameres_info['qnid'] = qnid
            qnx2_nameres_info['gt_nid'] = gt_nid
            qnx2_nameres_info['gf_nid'] = gf_nid
            qnx2_nameres_info['gt_name_rank'] = gt_name_rank
            qnx2_nameres_info['gf_name_rank'] = gf_name_rank
            qnx2_nameres_info['gt_name_score'] = gt_name_score
            qnx2_nameres_info['gf_name_score'] = gf_name_score

            nameres_info_list.append(qnx2_nameres_info)
            nameres_info = ut.dict_stack(nameres_info_list, 'qnx2_')
    else:
        qx2_qres = qreq_.ibs.query_chips(qreq_=qreq_)

    qaids = qreq_.get_external_qaids()
    daids = qreq_.get_external_daids()
    qx2_gtaids = ibs.get_annot_groundtruth(qaids, daid_list=daids)
    # Get the groundtruth ranks and accuracy measures
    qx2_qresinfo = [get_qres_name_result_info(ibs, qres, qreq_) for qres in qx2_qres]

    cfgres_info = ut.dict_stack(qx2_qresinfo, 'qx2_')
    #for key in qx2_qresinfo[0].keys():
    #    'qx2_' + key
    #    ut.get_list_column(qx2_qresinfo, key)

    if False:
        qx2_avepercision = np.array(
            [qres.get_average_percision(ibs=ibs, gt_aids=gt_aids) for
             (qres, gt_aids) in zip(qx2_qres, qx2_gtaids)])
        cfgres_info['qx2_avepercision'] = qx2_avepercision
    # Compute mAP score  # TODO: use mAP score
    # (Actually map score doesn't make much sense if using name scoring
    #mAP = qx2_avepercision[~np.isnan(qx2_avepercision)].mean()  # NOQA
    cfgres_info['qx2_bestranks'] = ut.replace_nones(cfgres_info['qx2_bestranks'] , -1)
    cfgres_info.update(nameres_info)
    return cfgres_info


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.expt.experiment_harness
        python -m ibeis.expt.experiment_harness --allexamples
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
