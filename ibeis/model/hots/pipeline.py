"""
Hotspotter pipeline module

TODO:
    We need to remove dictionaries from the pipeline
    We can easily use parallel lists

Module Concepts::

    PREFIXES:
    qaid2_XXX - prefix mapping query chip index to
    qfx2_XXX  - prefix mapping query chip feature index to

     * nns    - a (qfx2_idx, qfx2_dist) tuple
     * nnfilts - a (qfx2_score_list, qfx2_valid_list) tuple

     * idx    - the index into the nnindexers descriptors
     * qfx    - query feature index wrt the query chip
     * dfx    - query feature index wrt the database chip
     * dist   - the distance to a corresponding feature
     * fm     - a list of featur match pairs (qfx, dfx)
     * fsv    - a score vector of a corresponding feature
     * valid  - a valid bit for a corresponding feature

    PIPELINE_VARS::
    qaid2_nns - maping from query chip index to nns
    {
     * qfx2_idx   - ranked list of query feature indexes to database feature indexes
     * qfx2_dist - ranked list of query feature indexes to database feature indexes
    }

    * qaid2_norm_weight - mapping from qaid to (qfx2_normweight, qfx2_selnorm)
             = qaid2_nnfiltagg[qaid]

CommandLine:
    To see the ouput of a complete pipeline run use

    # Set to whichever database you like
    python main.py --db PZ_MTEST --setdb
    python main.py --db NAUT_test --setdb
    python main.py --db testdb1 --setdb

    # Then run whichever configuration you like
    python main.py --verbose --noqcache --cfg codename:vsone  --query 1
    python main.py --verbose --noqcache --cfg codename:vsone_norm  --query 1
    python main.py --verbose --noqcache --cfg codename:vsmany --query 1
    python main.py --verbose --noqcache --cfg codename:vsmany_nsum  --query 1
"""

from __future__ import absolute_import, division, print_function
from six.moves import zip, range
import six
import numpy as np
import vtool as vt
from vtool import keypoint as ktool
from vtool import spatial_verification as sver
from ibeis.model.hots import name_scoring
from ibeis.model.hots import hots_query_result
from ibeis.model.hots import hstypes
#from ibeis.model.hots import coverage_kpts
from ibeis.model.hots import nn_weights
from ibeis.model.hots import voting_rules2 as vr2
from ibeis.model.hots import exceptions as hsexcept
from ibeis.model.hots import _pipeline_helpers as plh
import utool as ut
#profile = ut.profile
print, print_,  printDBG, rrr, profile = ut.inject(__name__, '[pipeline]', DEBUG=False)


# TODO: chimatch should really be an object that moves through the pipeline
ChipMatch = hstypes.ChipMatch


#=================
# Globals
#=================

TAU = 2 * np.pi  # References: tauday.com
NOT_QUIET = ut.NOT_QUIET and not ut.get_argflag('--quiet-query')
DEBUG_PIPELINE = ut.get_argflag(('--debug-pipeline', '--debug-pipe'))
VERB_PIPELINE =  NOT_QUIET and (ut.VERBOSE or ut.get_argflag(('--verbose-pipeline', '--verb-pipe')))
VERYVERBOSE_PIPELINE = ut.get_argflag(('--very-verbose-pipeline', '--very-verb-pipe'))


NN_LBL      = 'Assign NN:       '
FILT_LBL    = 'Filter NN:       '
BUILDCM_LBL = 'Build Chipmatch: '
SVER_LVL    = 'SVER:            '


# TODO: make these purely belong to helpers
testrun_pipeline_upto = plh.testrun_pipeline_upto
get_pipeline_testdata = plh.get_pipeline_testdata


# Query Level 0
#@ut.indent_func('[Q0]')
@profile
def request_ibeis_query_L0(ibs, qreq_, verbose=VERB_PIPELINE):
    r"""
    Driver logic of query pipeline

    Note:
        Make sure _pipeline_helpres.testrun_pipeline_upto reflects what happens
        in this function

    Args:
        ibs   (IBEISController): IBEIS database object to be queried.
            technically this object already lives inside of qreq_.
        qreq_ (QueryRequest): hyper-parameters. use ``ibs.new_query_request`` to create one

    Returns:
        (dict[int, QueryResult]): qaid2_qres maps query annotid to QueryResult

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-request_ibeis_query_L0

    Example1:
        >>> # one-vs-many:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> import ibeis
        >>> cfgdict = dict(codename='vsmany')
        >>> ibs, qreq_ = get_pipeline_testdata(cfgdict=cfgdict)
        >>> print(qreq_.qparams.query_cfgstr)
        >>> verbose = True
        >>> qaid2_qres = request_ibeis_query_L0(ibs, qreq_, verbose=verbose)
        >>> qres = qaid2_qres[list(qaid2_qres.keys())[0]]
        >>> if ut.get_argflag('--show') or ut.inIPython():
        ...     qres.show_analysis(ibs, fnum=0, make_figtitle=True)
        >>> print(qres.get_inspect_str())

    Example2:
        >>> # one-vs-one:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> import ibeis  # NOQA
        >>> cfgdict1 = dict(codename='vsone', sv_on=False)
        >>> ibs1, qreq_1 = get_pipeline_testdata(cfgdict=cfgdict1)
        >>> print(qreq_1.qparams.query_cfgstr)
        >>> qaid2_qres1 = request_ibeis_query_L0(ibs1, qreq_1)
        >>> qres1 = qaid2_qres1[list(qaid2_qres1.keys())[0]]
        >>> if ut.get_argflag('--show') or ut.inIPython():
        ...     qres1.show_analysis(ibs1, fnum=1, make_figtitle=True)
        >>> print(qres1.get_inspect_str())

    """
    # Load data for nearest neighbors
    if verbose:
        assert ibs is qreq_.ibs
        print('\n\n[hs] +--- STARTING HOTSPOTTER PIPELINE ---')
        print(qreq_.get_infostr())

    assert len(qreq_.qparams.active_filter_list) > 0, 'no scoring filter selected'

    qreq_.lazy_load(verbose=verbose)

    if qreq_.qparams.pipeline_root == 'smk':
        from ibeis.model.hots.smk import smk_match
        # Alternative to naive bayes matching:
        # Selective match kernel
        qaid2_scores, qaid2_chipmatch_FILT_ = smk_match.execute_smk_L5(qreq_)
    elif qreq_.qparams.pipeline_root in ['vsone', 'vsmany']:

        # TODO: We should bring the vsone breakup down to this level,
        # then we should remerge the results after the build chipmatch.
        # then we should rectify the position in fk so the dupvote filter
        # can be run and name scoring will be meaningful.

        # Nearest neighbors (qaid2_nns)
        # a nns object is a tuple(ndarray, ndarray) - (qfx2_dx, qfx2_dist)
        # * query descriptors assigned to database descriptors
        # * FLANN used here
        qaid2_nns_ = nearest_neighbors(qreq_, verbose=verbose)

        # Remove Impossible Votes
        # a nnfilt object is an ndarray qfx2_valid
        # * marks matches to the same image as invalid
        qaid2_nnvalid0_ = baseline_neighbor_filter(qreq_, qaid2_nns_,
                                                   verbose=verbose)

        # Nearest neighbors weighting / scoring (qaid2_filtweights)
        # qaid2_filtweights maps qaid to filtweights which is a dict
        # that maps a filter name to that query's weights for that filter
        qaid2_filtweights_ = weight_neighbors(qreq_, qaid2_nns_, qaid2_nnvalid0_,
                                              verbose=verbose)

        # Thresholding and combine weights into a score
        # * scores for feature matches are tested for valididty
        # * scores for feature matches are aggregated
        # * nnfilt = (qfx2_valid, qfx2_score)
        # qfx2_score is an aggregate of all the weights
        qaid2_nnfilts_, qaid2_nnfiltagg_ = filter_neighbors(qreq_, qaid2_nns_,
                                                            qaid2_nnvalid0_,
                                                            qaid2_filtweights_,
                                                            verbose=verbose)

        # Nearest neighbors to chip matches (qaid2_chipmatch)
        # * Inverted index used to create aid2_fmfsvfk (TODO: aid2_fmfv)
        # * Initial scoring occurs
        # * vsone un-swapping occurs here
        qaid2_chipmatch_FILT_ = build_chipmatches(qreq_, qaid2_nns_,
                                                  qaid2_nnvalid0_,
                                                  qaid2_nnfilts_,
                                                  qaid2_nnfiltagg_,
                                                  verbose=verbose)
    else:
        print('invalid pipeline root %r' % (qreq_.qparams.pipeline_root))

    # Spatial verification (qaid2_chipmatch) (TODO: cython)
    # * prunes chip results and feature matches
    # TODO: allow for reweighting of feature matches to happen.
    qaid2_chipmatch_SVER_ = spatial_verification(qreq_, qaid2_chipmatch_FILT_,
                                                 verbose=verbose)

    # We might just put this check inside the function like it is for SVER.
    # or just not do that and use some good pipeline framework
    if qreq_.qparams.rrvsone_on:
        # VSONE RERANKING
        qaid2_chipmatch_ = vsone_reranking(qreq_, qaid2_chipmatch_SVER_, verbose=verbose)
    else:
        qaid2_chipmatch_ = qaid2_chipmatch_SVER_

    # Query results format (qaid2_qres)
    # * Final Scoring. Prunes chip results.
    # * packs into a wrapped query result object
    qaid2_qres_ = chipmatch_to_resdict(qreq_, qaid2_chipmatch_,
                                       verbose=verbose)

    # <HACK>
    # FOR VSMANY DISTINCTIVENSS
    if qreq_.qparams.return_expanded_nns:
        assert qreq_.qparams.vsmany, ' must be in a special vsmany mode'
        # MAJOR HACK TO RETURN ALL QUERY NEAREST NEIGHBORS
        # BREAKS PIPELINE CACHING ASSUMPTIONS
        # SHOULD ONLY BE CALLED BY SPECIAL_QUERY
        # CAUSES TOO MUCH DATA TO BE SAVED
        for qaid in qreq_.get_external_qaids():
            # TODO: hook up external neighbor mechanism?
            # No, not here, further down.
            (qfx2_idx, qfx2_dist) = qaid2_nns_[qaid]
            qres = qaid2_qres_[qaid]
            qres.qfx2_dist = qfx2_dist
            msg_list = [
                #'qres.qfx2_daid = ' + ut.get_object_size_str(qres.qfx2_daid),
                #'qres.qfx2_dfx = ' + ut.get_object_size_str(qres.qfx2_dfx),
                'qres.qfx2_dist = ' + ut.get_object_size_str(qres.qfx2_dist),
            ]
            print('\n'.join(msg_list))
    # </HACK>

    if VERB_PIPELINE:
        print('[hs] L___ FINISHED HOTSPOTTER PIPELINE ___')

    return qaid2_qres_

#============================
# 1) Nearest Neighbors
#============================


#@ut.indent_func('[nn]')
@profile
def nearest_neighbors(qreq_, verbose=VERB_PIPELINE):
    """
    Plain Nearest Neighbors

    Args:
        qreq_ (QueryRequest):  query request object with hyper-parameters
        verbose (bool):

    Returns:
        dict: qaid2_nns - a dict mapping query annnotation-ids to a nearest
            neighbor tuple (qfx2_idx, qfx2_dist). indexes and dist have the
            shape (nDesc x K) where nDesc is the number of descriptors in the
            annotation, and K is the number of approximate nearest neighbors.

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-nearest_neighbors

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> verbose = True
        >>> cfgdict = dict(codename='nsum')
        >>> ibs, qreq_ = get_pipeline_testdata(dbname='testdb1',
        ...                                             cfgdict=cfgdict)
        >>> # execute function
        >>> qaid2_nns = nearest_neighbors(qreq_, verbose)
        >>> qaids = qreq_.get_internal_qaids()
        >>> nns = qaid2_nns[qaids[0]]
        >>> (qfx2_idx, qfx2_dist) = nns
        >>> # Assert dictionary corresponds to internal qaids
        >>> ut.assert_eq(list(qaid2_nns.keys()), qaids.tolist())
        >>> # Assert nns tuple is valid
        >>> ut.assert_eq(qfx2_idx.shape, qfx2_dist.shape)
        >>> ut.assert_eq(qfx2_idx.shape[1], 5)
        >>> ut.assert_inbounds(qfx2_idx.shape[0], 1000, 2000)
    """
    # Neareset neighbor configuration
    K      = qreq_.qparams.K
    Knorm  = qreq_.qparams.Knorm
    #checks = qreq_.qparams.checks
    # Get both match neighbors and normalizing neighbors
    num_neighbors  = K + Knorm
    if verbose:
        print('[hs] Step 1) Assign nearest neighbors: %s' %
              (qreq_.qparams.nn_cfgstr,))
    # For each internal query annotation
    internal_qaids = qreq_.get_internal_qaids()
    # Find the nearest neighbors of each descriptor vector
    qvecs_list = qreq_.ibs.get_annot_vecs(internal_qaids, qreq_=qreq_)
    # Mark progress ane execute nearest indexer nearest neighbor code
    progkw = dict(freq=20, time_thresh=2.0)
    qvec_iter = ut.ProgressIter(qvecs_list, lbl=NN_LBL, **progkw)
    nns_list = [qreq_.indexer.knn(qfx2_vec, num_neighbors)
                 for qfx2_vec in qvec_iter]
    # Verbose statistics reporting
    if verbose:
        plh.print_nearest_neighbor_assignments(qvecs_list, nns_list)
    # Return old style dicts for now
    qaid2_nns = dict(zip(internal_qaids, nns_list))
    if qreq_.qparams.with_metadata:
        qreq_.metadata['nns'] = qaid2_nns
    return qaid2_nns


#============================
# 1.5) Remove Impossible Weights
#============================


@profile
def baseline_neighbor_filter(qreq_, qaid2_nns, verbose=VERB_PIPELINE):
    """

    Args:
        qreq_ (QueryRequest):  query request object with hyper-parameters
        qaid2_nns (dict):  maps query annotid to (qfx2_idx, qfx2_dist)
        verbose (bool):

    Returns:
        qaid2_nnvalid0 : mapping from qaid to qfx2_valid0

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-baseline_neighbor_filter

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *   # NOQA
        >>> import ibeis
        >>> cfgdict = dict(codename='nsum')
        >>> dbname = 'testdb1'
        >>> ibs, qreq_ = get_pipeline_testdata(dbname=dbname, cfgdict=cfgdict)
        >>> ibs = ibeis.opendb('testdb1')
        >>> aid_list = ibs.get_valid_aids()
        >>> locals_ = testrun_pipeline_upto(qreq_, 'baseline_neighbor_filter')
        >>> args = [locals_[key] for key in ['qaid2_nns']]
        >>> qaid2_nns, = args
        >>> # execute function
        >>> qaid2_nnvalid0 = baseline_neighbor_filter(qreq_, qaid2_nns)
        >>> nnvalid0 = qaid2_nnvalid0[1]
        >>> assert not np.any(nnvalid0[:, 0]), (
        ...    'first col should be all invalid because of self match')
        >>> assert not np.all(nnvalid0[:, 1]), (
        ...    'second col should have some good matches')
        >>> ut.assert_inbounds(nnvalid0.sum(), 1900, 2000)

    Removes matches to self, the same image, or the same name.
    """
    if verbose:
        print('[hs] Step 1.5) Baseline neighbor filter')
    cant_match_sameimg  = not qreq_.qparams.can_match_sameimg
    cant_match_samename = not qreq_.qparams.can_match_samename
    cant_match_self     = not cant_match_sameimg
    K = qreq_.qparams.K
    aid_nnidx_iter = (
        # Look at impossibility of the first K nearest neighbors
        (aid, qfx2_idx.T[0:K].T)
        for (aid, (qfx2_idx, _)) in six.iteritems(qaid2_nns)
    )
    nnvalid0_list = [
        flag_impossible_votes(qreq_, qaid, qfx2_nnidx, cant_match_self,
                              cant_match_sameimg, cant_match_samename,
                              verbose=verbose)
        for qaid, qfx2_nnidx in aid_nnidx_iter
    ]
    internal_qaids_iter = six.iterkeys(qaid2_nns)
    qaid2_nnvalid0 = dict(zip(internal_qaids_iter, nnvalid0_list))
    return qaid2_nnvalid0


@profile
def flag_impossible_votes(qreq_, qaid, qfx2_nnidx, cant_match_self,
                            cant_match_sameimg, cant_match_samename,
                            verbose=VERB_PIPELINE):
    """
    Flags matches to self or same image
    """
    # Baseline is all matches have score 1 and all matches are valid
    qfx2_valid0 = np.ones(qfx2_nnidx.shape, dtype=np.bool)

    # Get neighbor annotation information
    qfx2_aid = qreq_.indexer.get_nn_aids(qfx2_nnidx)
    # dont vote for yourself or another chip in the same image
    if cant_match_self:
        qfx2_notsamechip = qfx2_aid != qaid
        if DEBUG_PIPELINE:
            plh._self_verbose_check(qfx2_notsamechip, qfx2_valid0)
        qfx2_valid0 = np.logical_and(qfx2_valid0, qfx2_notsamechip)
    if cant_match_sameimg:
        qfx2_gid = qreq_.ibs.get_annot_gids(qfx2_aid)
        qgid     = qreq_.ibs.get_annot_gids(qaid)
        qfx2_notsameimg = qfx2_gid != qgid
        if DEBUG_PIPELINE:
            plh._sameimg_verbose_check(qfx2_notsameimg, qfx2_valid0)
        qfx2_valid0 = np.logical_and(qfx2_valid0, qfx2_notsameimg)
    if cant_match_samename:
        # This should probably be off
        qfx2_nid = qreq_.ibs.get_annot_name_rowids(qfx2_aid)
        qnid = qreq_.ibs.get_annot_name_rowids(qaid)
        qfx2_notsamename = qfx2_nid != qnid
        if DEBUG_PIPELINE:
            plh._samename_verbose_check(qfx2_notsamename, qfx2_valid0)
        qfx2_valid0 = np.logical_and(qfx2_valid0, qfx2_notsamename)
    return qfx2_valid0


#============================
# 2) Nearest Neighbor weights
#============================


#@ut.indent_func('[wn]')
@profile
def weight_neighbors(qreq_, qaid2_nns, qaid2_nnvalid0, verbose=VERB_PIPELINE):
    """
    PIPELINE NODE 3 - assigns weights to feature matches based on the active
    filter list.

    Args:
        qreq_ (QueryRequest):  query request object with hyper-parameters
        qaid2_nns (dict):  maps query annotid to (qfx2_idx, qfx2_dist)
        qaid2_nnvalid0 (dict):  maps query annotid to qfx2_valid0
        verbose (bool):

    Returns:
        dict : qaid2_filtweights

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-weight_neighbors

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> #cfgdict = dict(codename='vsone')
        >>> cfgdict = dict(codename='nsum')
        >>> # dbname = 'GZ_ALL'  # 'testdb1'
        >>> dbname = 'testdb1'
        >>> ibs, qreq_ = get_pipeline_testdata(dbname, cfgdict, qaid_list=[1, 2])
        >>> locals_ = testrun_pipeline_upto(qreq_, 'weight_neighbors')
        >>> args = [locals_[key] for key in ['qaid2_nns', 'qaid2_nnvalid0']]
        >>> qaid2_nns, qaid2_nnvalid0  = args
        >>> # execute function
        >>> qaid2_filtweights = weight_neighbors(qreq_, qaid2_nns, qaid2_nnvalid0)
        >>> filtkey_list = qaid2_filtweights[1].keys()
        >>> filtkey_list == [hstypes.FiltKeys.LNBNN, hstypes.FiltKeys.DUPVOTE]
    """
    if verbose:
        print('[hs] Step 2) Weight neighbors: ' + qreq_.qparams.filt_cfgstr)
    # Gravity weighting does not work well enough yet
    if qreq_.qparams.gravity_weighting:
        #filtkey_list.append('gravity')
        raise NotImplementedError('have not finished gv weighting')

    assert len(qreq_.qparams.active_filter_list) > 0, 'no scoring filter selected'

    if qreq_.qparams.filt_on:
        # Build weights for each active filter
        internal_qaids = list(six.iterkeys(qaid2_nns))
        filtkey_list = qreq_.qparams.active_filter_list
        filtfn_list  = [nn_weights.NN_WEIGHT_FUNC_DICT[filtkey] for filtkey in filtkey_list]
        # compute weighting
        qweights_list = [filtfn(qaid2_nns, qaid2_nnvalid0, qreq_) for filtfn in filtfn_list]
        # Index by qaids first
        filtweights_list = [
            ut.odict(
                zip(
                    filtkey_list,
                    [qaid2_weights[qaid] for qaid2_weights in qweights_list]
                )
            )
            for qaid in internal_qaids
        ]
        # Use dictionary output until ready to move completely to lists
        qaid2_filtweights = ut.odict(zip(internal_qaids, filtweights_list))
    else:
        raise NotImplementedError('need to turn on filters')
        qaid2_filtweights = {}
    return qaid2_filtweights


#==========================
# 3) Neighbor scoring (Voting Profiles)
# aggregates weights, applies thresholds
# TODO: do not aggregate weights. Needs to be
# able to update them in the future
#==========================


#@ut.indent_func('[fn]')
@profile
def filter_neighbors(qreq_, qaid2_nns, qaid2_nnvalid0, qaid2_filtweights, verbose=VERB_PIPELINE):
    """
    converts feature weights to feature scores and validity masks

    Args:
        qreq_ (QueryRequest):  query request object with hyper-parameters
        qaid2_nns (dict):  maps query annotid to (qfx2_idx, qfx2_dist)
        qaid2_nnvalid0 (dict):  maps query annotid to qfx2_valid0
        qaid2_filtweights (dict):  mapping to weights computed by filters like
            lnnbnn and ratio
        verbose (bool):

    Returns:
        tuple: (qaid2_nnfilts, qaid2_nnfiltagg) - mappings from qaid
            nnfilts is a tuple (filtkey_list, qfx2_score_list, qfx2_valid_list)
            nnfiltsagg is a tuple (qfx2_score_agg, qfx2_valid_agg)

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-filter_neighbors

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> verbose = True
        >>> cfgdict = dict(dupvote_weight=1.0)
        >>> ibs, qreq_ = get_pipeline_testdata(cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'filter_neighbors')
        >>> args = [locals_[key] for key in ['qaid2_nns', 'qaid2_nnvalid0', 'qaid2_filtweights']]
        >>> qaid2_nns, qaid2_nnvalid0, qaid2_filtweights = args
        >>> # Make sure internal qaids are behaving well
        >>> ut.assert_lists_eq(list(six.iterkeys(qaid2_nns)), list(six.iterkeys(qaid2_nnvalid0)))
        >>> ut.assert_lists_eq(list(six.iterkeys(qaid2_nns)), qreq_.get_internal_qaids())
        >>> # execute function
        >>> qaid2_nnfilts, qaid2_nnfiltagg = filter_neighbors(
        ...     qreq_, qaid2_nns, qaid2_nnvalid0, qaid2_filtweights)
        >>> # Make sure we are getting expected filter scores back.
        >>> nnfilts = six.next(six.itervalues(qaid2_nnfilts))
        >>> (filtkey_list, qfx2_score_list, qfx2_valid_list) = nnfilts
        >>> expected_filtkeys = [hstypes.FiltKeys.LNBNN,
        ...                      hstypes.FiltKeys.DUPVOTE, hstypes.FiltKeys.FG]
        >>> ut.assert_lists_eq(filtkey_list, expected_filtkeys, 'bad filters')
        >>> assert qfx2_score_list[0].shape == qfx2_score_list[1].shape, 'inconsistent shape'
        >>> ut.assert_inbounds(qfx2_score_list[0].shape[0], 1200, 1300)
        >>> ut.assert_lists_eq(qfx2_valid_list, [None] * len(expected_filtkeys), 'all should be valid')
    """
    if verbose:
        print('[hs] Step 3) Filter neighbors: ')
    nnfiltagg_list = []
    nnfilts_list = []
    internal_qaids = list(six.iterkeys(qaid2_nns))
    #qaid_iter = ut.ProgressIter(internal_qaids, lbl=FILT_LBL, freq=20, time_thresh=2.0)
    qaid_iter = internal_qaids
    # Filter matches based on config and weights
    for qaid in qaid_iter:
        # all the filter weights for this query
        qfx2_valid0 = qaid2_nnvalid0[qaid]
        filt2_weights = qaid2_filtweights[qaid]
        # Get a numeric score score and valid flag for each feature match
        nnfilts, nnfiltagg = threshold_and_scale_weights(qreq_, qaid, qfx2_valid0,
                                                         filt2_weights)
        nnfiltagg_list.append(nnfiltagg)
        nnfilts_list.append(nnfilts)
    # dict output until pipeline moves to lists
    qaid2_nnfilts = dict(zip(internal_qaids, nnfilts_list))
    qaid2_nnfiltagg = dict(zip(internal_qaids, nnfiltagg_list))
    return qaid2_nnfilts, qaid2_nnfiltagg


#@ut.indent_func('[_tsw]')
@profile
def threshold_and_scale_weights(qreq_, qaid, qfx2_valid0, filt2_weights):
    """
    helper function

    converts weights into per keypoint scores for a given filter / weight function
    qfx2_score is an ndarray containing the score of individual feature matches.
    qfx2_valid marks if that score will be thresholded.

    FIXME: currently what should be called scores are called weights and visveras
    maybe raw_weight and weight would be better

    Args:
        qreq_ (QueryRequest):  query request object with hyper-parameters
        qaid (int):  query annotation id
        qfx2_valid0 (ndarray):  maps query feature index to K matches non-impossibility flags
        filt2_weights (dict):  maps filter names to qfx2_weight ndarray

    Return:
        tuple : (nnfilts, nnfiltagg)

    NOTE:
        soon nnfiltagg will not be returned

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-threshold_and_scale_weights:0

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict(dupvote_weight=1.0)
        >>> cfgdict = dict(codename='vsone')
        >>> ibs, qreq_ = get_pipeline_testdata(cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'filter_neighbors')
        >>> args = [locals_[key] for key in ['qaid2_nns', 'qaid2_nnvalid0', 'qaid2_filtweights']]
        >>> qaid2_nns, qaid2_nnvalid0, qaid2_filtweights = args
        >>> # Continue with function logic
        >>> qaid = qreq_.get_internal_qaids()[1]
        >>> filt2_weights = qaid2_filtweights[qaid]
        >>> qfx2_valid0 = qaid2_nnvalid0[qaid]
        >>> # execute function
        >>> nnfilts, nnfiltagg = threshold_and_scale_weights(qreq_, qaid, qfx2_valid0, filt2_weights)
        >>> ut.assert_eq(nnfilts[0], [hstypes.FiltKeys.RATIO, hstypes.FiltKeys.FG])
        >>> ratio_scores = nnfilts[2][0]
        >>> assert np.all(ratio_scores <= 1.0), 'expected ratio scores <= 1.0'
        >>> assert np.all(ratio_scores >= 0.0), 'exepcted ratio scores >= 0.0'

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict(codename='vsmany')
        >>> ibs, qreq_ = get_pipeline_testdata(cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'filter_neighbors')
        >>> args = [locals_[key] for key in ['qaid2_nns', 'qaid2_nnvalid0', 'qaid2_filtweights']]
        >>> qaid2_nns, qaid2_nnvalid0, qaid2_filtweights = args
        >>> # Continue with function logic
        >>> qaid = qreq_.get_internal_qaids()[0]
        >>> filt2_weights = qaid2_filtweights[qaid]
        >>> qfx2_valid0 = qaid2_nnvalid0[qaid]
        >>> # execute function
        >>> nnfilts, nnfiltagg = threshold_and_scale_weights(qreq_, qaid, qfx2_valid0, filt2_weights)
        >>> ut.assert_lists_eq(nnfilts[0], [hstypes.FiltKeys.LNBNN, hstypes.FiltKeys.DUPVOTE, hstypes.FiltKeys.FG])

    """
    # Apply the filter weightings to determine feature validity and scores
    filtkey_list = list(six.iterkeys(filt2_weights))
    raw_weights_list = list(six.itervalues(filt2_weights))
    # stw := sign, thresh, weight
    stw_list = [qreq_.qparams.filt2_stw[filt] for filt in filtkey_list]
    st_list  = [stw[0:2] for stw in stw_list]
    w_list   = [stw[2]   for stw in stw_list]

    #-------
    # proably the second most incomprehensable (aka complex) list
    # comphrehensions I've written. They aren't that bad.
    #-------

    # Mask feature weights that do not pass their threshold specified in FiltCfg
    # This leaves passing features marked as True and failing features as False
    # The sign lets us toggle less than or greater than
    qfx2_valid_list = [
        None if thresh is None else (
            np.less_equal(np.multiply(sign, qfx2_raw_weights), (sign * thresh))
        )
        for qfx2_raw_weights, (sign, thresh) in zip(raw_weights_list, st_list)
    ]

    # Build feature scores as feature weights scaled by values in FiltCfg
    # these should correspond to filtkeys with a sign of +1
    invert_score_filter_set = {hstypes.FiltKeys.RATIO, hstypes.FiltKeys.DIST}
    qfx2_score_list = [
        None if weight == 0 else (
            np.multiply(qfx2_raw_weights, weight)
            # hack to make higher ratio scores better.
            if filt not in invert_score_filter_set else
            np.multiply(np.subtract(1.0, qfx2_raw_weights), weight)
        )
        for qfx2_raw_weights, filt, weight in zip(raw_weights_list, filtkey_list, w_list)
    ]

    # Aggregation: # TODO: this step should happen later
    qfx2_valid_agg = vt.and_lists(qfx2_valid0, *ut.filter_Nones(qfx2_valid_list))
    qfx2_score_agg = vt.mult_lists(*ut.filter_Nones(qfx2_score_list))
    # dont need to check qfx2_valid_agg because of qfx2_valid0
    if len(qfx2_score_agg) == 0:
        qfx2_score_agg = np.ones(qfx2_valid0.shape, dtype=hstypes.FS_DTYPE)

    # outputs
    nnfilts = (filtkey_list, qfx2_score_list, qfx2_valid_list)
    nnfiltagg = (qfx2_score_agg, qfx2_valid_agg)
    return nnfilts, nnfiltagg


#============================
# 4) Conversion from featurematches to chipmatches qfx2 -> aid2
#============================


def testdata_build_chipmatch(dbname, cfgdict):
    ibs, qreq_ = get_pipeline_testdata('testdb1', cfgdict=cfgdict)
    locals_ = testrun_pipeline_upto(qreq_, 'build_chipmatches')
    args = [locals_[key] for key in [
        'qaid2_nns', 'qaid2_nnvalid0', 'qaid2_nnfilts', 'qaid2_nnfiltagg']]
    return ibs, qreq_, args


#@ut.indent_func('[bc]')
#@profile
def build_chipmatches(qreq_, qaid2_nns, qaid2_nnvalid0, qaid2_nnfilts, qaid2_nnfiltagg, verbose=VERB_PIPELINE):
    """
    pipeline step 4 - builds sparse chipmatches

    Takes the dense feature matches from query feature to (what could be any)
    database features and builds sparse matching pairs for each annotation to
    annotation match.

    Args:
        qreq_ (QueryRequest) : hyper-parameters

        qaid2_nns (dict): dict of assigned nearest features (only indexes are
            used here)

        qaid2_nnfilts (dict): nonaggregate feature scores and validities for
            each feature NEW

        qaid2_nnfiltagg (dict): dict of (qfx2_score, qfx2_valid) where the
            scores and matches correspond to the assigned nearest features
            CURRENTLY UNUSED

    Returns:
         dict : qaid2_chipmatch - mapping from qaid to chipmatch
             a chipmatch is a tuple (fm, fsv, fk)
                 fm := list of feature matchs
                 fsv := list of feature scores vectors
                 fk := list of feature ranks
                 H := homog or None

    Notes:
        The prefix ``qaid2_`` denotes a mapping where keys are query-annotation-id

        vsmany/vsone counts here. also this is where the filter
        weights and thershold are applied to the matches. Essientally
        nearest neighbors are converted into weighted assignments

    Ignore:
        python -c "import utool; print(utool.auto_docstr('ibeis.model.hots.pipeline', 'build_chipmatches'))"

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-build_chipmatches
        python -m ibeis.model.hots.pipeline --test-build_chipmatches:0
        python -m ibeis.model.hots.pipeline --test-build_chipmatches:1

    Example1:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> verbose = True
        >>> cfgdict = dict(codename='vsone')
        >>> # get testdata
        >>> ibs, qreq_, args = testdata_build_chipmatch('testdb1', cfgdict)
        >>> (qaid2_nns, qaid2_nnvalid0, qaid2_nnfilts, qaid2_nnfiltagg) = args
        >>> # execute function
        >>> qaid2_chipmatch = build_chipmatches(qreq_, *args, verbose=verbose)
        >>> # verify results
        >>> qaid = qreq_.get_external_qaids()[0]
        >>> daid = qreq_.get_external_daids()[1]
        >>> print('daid=%r' % (daid,))
        >>> print('qaid=%r' % (qaid,))
        >>> fm = qaid2_chipmatch[qaid][0][daid]
        >>> fsv = qaid2_chipmatch[qaid][1][daid]
        >>> num_matches = len(fm)
        >>> print('vsone num_matches = %r' % num_matches)
        >>> filtkey_list = qaid2_nnfilts[qaid][0]
        >>> print('filtkey_list = %r' % (filtkey_list,))
        >>> ut.assert_eq(fm.shape[1], 2, 'feat matches have 2 cols (qfx, dfx)')
        >>> ut.assert_eq(fsv.shape[1], len(filtkey_list), 'feat score vectors have 1 col per filt')
        >>> ut.assert_inbounds(num_matches, 33, 42, 'vsone nmatches out of bounds')
        >>> plh.assert_qaid2_chipmatch(qreq_, qaid2_chipmatch)

    Example2:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> verbose = True
        >>> cfgdict = dict(codename='vsmany')
        >>> #cfgdict = dict(codename='vsmany_csum', dupvote_weight='0.0')
        >>> # get testdata
        >>> ibs, qreq_ = get_pipeline_testdata('testdb1', cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'build_chipmatches')
        >>> args = ut.dict_take(locals_,
        ...    ['qaid2_nns', 'qaid2_nnvalid0', 'qaid2_nnfilts', 'qaid2_nnfiltagg'])
        >>> (qaid2_nns, qaid2_nnvalid0, qaid2_nnfilts, qaid2_nnfiltagg) = args
        >>> # execute function
        >>> qaid2_chipmatch = build_chipmatches(qreq_, *args, verbose=verbose)
        >>> # verify results
        >>> qaid = qreq_.get_internal_qaids()[0]
        >>> daid = qreq_.get_internal_daids()[1]
        >>> chipmatch = qaid2_chipmatch[qaid]
        >>> daid2_fm, daid2_fsv, daid_fk, aid2_score, daid2_H = chipmatch
        >>> fm = daid2_fm[daid]
        >>> fsv = daid2_fsv[daid]
        >>> num_matches = len(fm)
        >>> print('vsmany num_matches = %r' % num_matches)
        >>> ut.assert_eq(fm.shape[1], 2, 'fm needs 2 columns')
        >>> ut.assert_inbounds(num_matches, 550, 600, 'vsmany nmatches out of bounds')
        >>> plh.assert_qaid2_chipmatch(qreq_, qaid2_chipmatch)
    """
    is_vsone =  qreq_.qparams.vsone
    if verbose:
        pipeline_root = qreq_.qparams.pipeline_root
        print('[hs] Step 4) Building chipmatches %s' % (pipeline_root,))
    # Iterate over INTERNAL query annotation ids
    internal_qaids = list(six.iterkeys(qaid2_nns))
    #progkw = dict(freq=20, time_thresh=2.0)
    #intern_qaid_iter = ut.ProgressIter(internal_qaids, lbl=BUILDCM_LBL, **progkw)
    intern_qaid_iter = internal_qaids
    def _get_sparse_matchinfo(intern_qaid):
        # common code between vsone and vsmany
        (qfx2_idx, _) = qaid2_nns[intern_qaid]
        #nnfiltagg   = qaid2_nnfiltagg[intern_qaid]  # NOTE: filtagg will be removed soon
        nnfilts     = qaid2_nnfilts[intern_qaid]
        qfx2_valid0 = qaid2_nnvalid0[intern_qaid]
        valid_match_tup = get_sparse_matchinfo_nonagg(qreq_, qfx2_idx, qfx2_valid0, nnfilts)
        return valid_match_tup

    if is_vsone:
        # VSONE build chipmatch
        external_qaids = qreq_.get_external_qaids()
        assert len(external_qaids) == 1, 'vsone can only accept one external qaid'
        extern_qaid = external_qaids[0]
        # these dict keys are external daids
        chipmatch_ = hstypes.new_chipmatch(with_homog=False)
        (daid2_fm, daid2_fsv, daid2_fk, aid2_score, daid2_H) = chipmatch_
        # External daids are internal qaids in vsone
        for extern_daid in intern_qaid_iter:
            #print(extern_daid)
            #if extern_daid == 2:
            valid_match_tup = _get_sparse_matchinfo(extern_daid)
            if True:
                # debug
                valid_daid = valid_match_tup[0]
                assert np.all(valid_daid == extern_qaid)
            #(valid_daid, valid_qfx, valid_dfx, valid_scorevec, valid_rank,) = valid_match_tup
            # Vsone - append to chipmatches
            (fm, fsv, fk, _, _) = append_chipmatch_vsone_nonagg(valid_match_tup)
            daid2_fm[extern_daid] = fm
            daid2_fsv[extern_daid] = fsv
            daid2_fk[extern_daid] = fk
        # Vsone finalization
        chipmatch = hstypes.fix_chipmatch(chipmatch_)
        # build vsone dict output
        qaid2_chipmatch = {extern_qaid: chipmatch}
    else:
        # VSMANY build chipmatch
        chipmatch_list = []
        for qaid in intern_qaid_iter:
            valid_match_tup = _get_sparse_matchinfo(qaid)
            # Vsmany - create new chipmatch
            chipmatch = append_chipmatch_vsmany_nonagg(valid_match_tup)
            chipmatch_list.append(chipmatch)
        # build vsmany dict output
        qaid2_chipmatch = dict(zip(internal_qaids, chipmatch_list))
    return qaid2_chipmatch


def append_chipmatch_vsone_nonagg(valid_match_tup):
    # NEW WAY OF DOING THINGS
    (valid_daid, valid_qfx, valid_dfx, valid_scorevec, valid_rank) = valid_match_tup
    assert ut.list_allsame(valid_daid), 'internal daids should not have different daids for vsone'
    # Note the difference in construction of fm
    fm = np.vstack((valid_dfx, valid_qfx)).T
    fm.shape = (fm.size / 2, 2)
    fsv = valid_scorevec
    fk = valid_rank.tolist()
    return (fm, fsv, fk, None, None)


def append_chipmatch_vsmany_nonagg(valid_match_tup):
    # NEW WAY OF DOING THINGS
    chipmatch = hstypes.new_chipmatch(with_homog=False)
    aid2_fm, aid2_fsv, aid2_fk, aid2_score, aid2_H = chipmatch
    # TODO: Sorting the valid lists by aid might help the speed of this
    # code. Also, consolidating fm, fsv, and fk into one vector will reduce
    # the amount of appends.
    (valid_daid, valid_qfx, valid_dfx, valid_scorevec, valid_rank) = valid_match_tup
    valid_fm = np.vstack((valid_qfx, valid_dfx)).T
    for daid, fm, fsv, fk in zip(valid_daid, valid_fm, valid_scorevec, valid_rank):
        # Note the difference in construction of fm
        aid2_fm[daid].append(fm)
        aid2_fsv[daid].append(fsv)
        aid2_fk[daid].append(fk)
    chipmatch = hstypes.fix_chipmatch(chipmatch)
    return chipmatch


def get_sparse_matchinfo_nonagg(qreq_, qfx2_idx, qfx2_valid0, nnfilts):
    """
    builds sparse iterator that generates feature match pairs, scores, and ranks

    Args:
        qfx2_idx (ndarray[int32_t, ndims=2]): mapping from query feature index
            to db neighbor index
        nnfilts (tuple): (filtkey_list, qfx2_score_list, qfx2_valid_list)
        qreq_ (QueryRequest): query request object with hyper-parameters

    Returns:
        tuple: valid_match_tup

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-get_sparse_matchinfo_nonagg

    Example0:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> verbose = True
        >>> cfgdict = dict(codename='vsmany')
        >>> # get testdata
        >>> ibs, qreq_, args = testdata_build_chipmatch('testdb1', cfgdict)
        >>> (qaid2_nns, qaid2_nnvalid0, qaid2_nnfilts, qaid2_nnfiltagg) = args
        >>> qaid = qreq_.get_internal_qaids()[0]
        >>> daid = qreq_.get_internal_daids()[1]
        >>> qfx2_idx = qaid2_nns[qaid][0]
        >>> qfx2_valid0 = qaid2_nnvalid0[qaid]
        >>> nnfilts = qaid2_nnfilts[qaid]
        >>> nnfiltagg = qaid2_nnfiltagg[qaid]
        >>> (filtkey_list, qfx2_score_list, qfx2_valid_list) = nnfilts
        >>> (qfx2_score_agg, qfx2_valid_agg) = nnfiltagg
        >>> # execute function
        >>> valid_match_tup = get_sparse_matchinfo_nonagg(qreq_, qfx2_idx, qfx2_valid0, nnfilts)
        >>> chipmatch = append_chipmatch_vsmany_nonagg(valid_match_tup)
        >>> (daid2_fm, daid2_fsv, daid2_fk, aid2_score, aid2_H) = chipmatch
        >>> fm = daid2_fm[daid]
        >>> fsv = daid2_fsv[daid]
        >>> fk = daid2_fk[daid]
        >>> ut.assert_eq(aid2_H, None, 'no H yet')
        >>> ut.assert_eq(fm.shape[1], 2, 'column for (qfx, dfx)')
        >>> ut.assert_eq(fm.shape[0], fk.shape[0], 'one rank for every match')
        >>> ut.assert_eq(len(fk.shape), 1, 'fk (feature rank) is 1D')
        >>> ut.assert_eq(fsv.shape[0], fm.shape[0], 'need same num rows')
        >>> ut.assert_eq(fsv.shape[1], len(qreq_.qparams.active_filter_list), 'should have col for every filter')

    Example1:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> verbose = True
        >>> cfgdict = dict(codename='vsone')
        >>> # get testdata
        >>> ibs, qreq_, args = testdata_build_chipmatch('testdb1', cfgdict)
        >>> (qaid2_nns, qaid2_nnvalid0, qaid2_nnfilts, qaid2_nnfiltagg) = args
        >>> qaid = qreq_.get_internal_qaids()[1]
        >>> daid = qreq_.get_internal_daids()[0]
        >>> qfx2_idx = qaid2_nns[qaid][0]
        >>> qfx2_valid0 = qaid2_nnvalid0[qaid]
        >>> nnfilts = qaid2_nnfilts[qaid]
        >>> nnfiltagg = qaid2_nnfiltagg[qaid]
        >>> (filtkey_list, qfx2_score_list, qfx2_valid_list) = nnfilts
        >>> (qfx2_score_agg, qfx2_valid_agg) = nnfiltagg
        >>> # execute function
        >>> valid_match_tup = get_sparse_matchinfo_nonagg(qreq_, qfx2_idx, qfx2_valid0, nnfilts)
        >>> (fm, fsv, fk, _, H) = append_chipmatch_vsone_nonagg(valid_match_tup)
        >>> ut.assert_eq(H, None, 'no H yet')
        >>> ut.assert_eq(fm.shape[1], 2, 'column for (qfx, dfx)')
        >>> #ut.assert_eq(fm.shape[0], fk.shape[0], 'one rank for every match')
        >>> #ut.assert_eq(len(fk.shape), 1, 'fk (feature rank) is 1D')
        >>> ut.assert_eq(fsv.shape[0], fm.shape[0], 'need same num rows')
        >>> ut.assert_eq(fsv.shape[1], len(qreq_.qparams.active_filter_list), 'should have col for every filter')
        >>> assert np.all(fm.T[0] < ibs.get_annot_num_feats(daid, qreq_=qreq_))
        >>> assert np.all(fm.T[1] < ibs.get_annot_num_feats(qaid, qreq_=qreq_))
    """
    K = qreq_.qparams.K
    # Unpack neighbor ids, indicies, filter scores, and flags
    qfx2_nnidx = qfx2_idx.T[0:K].T
    qfx2_daid = qreq_.indexer.get_nn_aids(qfx2_nnidx)
    qfx2_dfx = qreq_.indexer.get_nn_featxs(qfx2_nnidx)
    (filtkey_list, qfx2_score_list, qfx2_valid_list) = nnfilts
    # Get an aggregate validity. This is ok because filters like dupvote dont
    # actually invalidate features it just heavilly downweights them
    qfx2_valid_agg = vt.and_lists(qfx2_valid0, *ut.filter_Nones(qfx2_valid_list))
    # We fill filter each relavant matrix by aggregate validity
    flat_validx = np.flatnonzero(qfx2_valid_agg)
    # Infer the valid internal query feature indexes and ranks
    valid_qfx   = np.floor_divide(flat_validx, K)
    valid_rank  = np.mod(flat_validx, K)
    # Then take the valid indices from internal database
    # annot_rowids, feature indexes, and all scores
    valid_daid  = qfx2_daid.take(flat_validx)
    valid_dfx   = qfx2_dfx.take(flat_validx)
    valid_scorevec = np.vstack([qfx2_score.take(flat_validx)
                                for qfx2_score in qfx2_score_list]).T
    # The q/d's are all internal here, thus in vsone they swap
    valid_match_tup = (valid_daid, valid_qfx, valid_dfx, valid_scorevec, valid_rank)
    return valid_match_tup


#============================
# 5) Spatial Verification
#============================


#@ut.indent_func('[sv]')
def spatial_verification(qreq_, qaid2_chipmatch, verbose=VERB_PIPELINE):
    """
    Args:
        qreq_ (QueryRequest): hyper-parameters
        qaid2_chipmatch (dict):
        dbginfo (bool):

    Returns:
        dict or tuple(dict, dict)

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-spatial_verification

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict(dupvote_weight=1.0, prescore_method='nsum', score_method='nsum')
        >>> ibs, qreq_ = get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'spatial_verification')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch_FILT']
        >>> qaid2_nnfilts = locals_['qaid2_nnfilts']
        >>> qaid2_chipmatchSV = spatial_verification(qreq_, qaid2_chipmatch)
        >>> qaid = qreq_.get_external_qaids()[0]
        >>> gt_daids = qreq_.get_external_query_groundtruth(qaid)
        >>> daid = gt_daids[0]
        >>> fm = qaid2_chipmatch[qaid][0][daid]
        >>> fmSV = qaid2_chipmatchSV[qaid][0][daid]
        >>> fsv = qaid2_chipmatch[qaid][1][daid]
        >>> fsvSV = qaid2_chipmatchSV[qaid][1][daid]
        >>> assert len(fmSV) < len(fm), 'feature matches were not filtered'
        """
    if not qreq_.qparams.sv_on or qreq_.qparams.xy_thresh is None:
        if verbose:
            print('[hs] Step 5) Spatial verification: off')
        return qaid2_chipmatch
    else:
        qaid2_chipmatchSV = _spatial_verification(qreq_, qaid2_chipmatch, verbose=verbose)
        if qreq_.qparams.dupvote_weight > 0:
            hack_fix_dupvote_weights(qreq_, qaid2_chipmatchSV)
        return qaid2_chipmatchSV


#@ut.indent_func('[_sv]')
@profile
def _spatial_verification(qreq_, qaid2_chipmatch, verbose=VERB_PIPELINE):
    """
    make only spatially valid features survive
    """
    if verbose:
        print('[hs] Step 5) Spatial verification: ' + qreq_.qparams.sv_cfgstr)
    use_chip_extent = qreq_.qparams.use_chip_extent
    with_metadata = qreq_.qparams.with_metadata
    qaid2_chipmatchSV = {}
    # dbg info (can remove if there is a speed issue)
    qaid2_svtups = {} if with_metadata else None
    qaid_progiter = ut.ProgressIter(six.iterkeys(qaid2_chipmatch),
                                    nTotal=len(qaid2_chipmatch), lbl=SVER_LVL,
                                    freq=20, time_thresh=2.0)
    for qaid in qaid_progiter:
        # Find a transform from chip2 to chip1 (the old way was 1 to 2)
        chipmatch = qaid2_chipmatch[qaid]
        topx2_aid, nRerank = get_prescore_shortlist(qreq_, qaid, chipmatch)
        daid2_fm = chipmatch[0]
        # Get information for sver, query keypoints, diaglen
        kpts1 = qreq_.ibs.get_annot_kpts(qaid, qreq_=qreq_)
        topx2_kpts = qreq_.ibs.get_annot_kpts(topx2_aid, qreq_=qreq_)
        topx2_dlen_sqrd = precompute_topx2_dlen_sqrd(
            qreq_, daid2_fm, topx2_aid, topx2_kpts, nRerank, use_chip_extent)
        chipmatchSV, daid2_svtup = _internal_sver(qreq_, kpts1, topx2_aid,
                                                  topx2_kpts, topx2_dlen_sqrd,
                                                  nRerank, chipmatch)
        if with_metadata:
            qaid2_svtups[qaid] = daid2_svtup
        # Rebuild the feature match / score arrays to be consistent
        qaid2_chipmatchSV[qaid] = chipmatchSV
    if with_metadata:
        qreq_.metadata['qaid2_svtups'] = qaid2_svtups
    return qaid2_chipmatchSV


def _internal_sver(qreq_, kpts1, topx2_aid, topx2_kpts, topx2_dlen_sqrd,
                   nRerank, chipmatch):
    """
    loops over a shortlist of results for a specific query annotation

    python -m ibeis.model.hots.pipeline --test-chipmatch_to_resdict:1

    """
    xy_thresh       = qreq_.qparams.xy_thresh
    scale_thresh    = qreq_.qparams.scale_thresh
    ori_thresh      = qreq_.qparams.ori_thresh
    min_nInliers    = qreq_.qparams.min_nInliers
    sver_weighting  = qreq_.qparams.sver_weighting
    # unpack chipmatch
    (daid2_fm, daid2_fsv, daid2_fk, daid2_score, daid2_H) = chipmatch
    # Precompute sver chipmatch
    chipmatchSV_ = hstypes.new_chipmatch(with_homog=True)
    (daid2_fm_V, daid2_fsv_V, daid2_fk_V, daid2_score_V, daid2_H_V) = chipmatchSV_
    # dbg info (can remove if there is a speed issue)
    daid2_svtup = {} if qreq_.qparams.with_metadata else None
    for topx in range(nRerank):
        daid = topx2_aid[topx]
        fm = daid2_fm[daid]
        if len(fm) == 0:
            # skip results without any matches
            continue
        dlen_sqrd2 = topx2_dlen_sqrd[topx]
        kpts2 = topx2_kpts[topx]
        fsv    = daid2_fsv[daid]
        fk    = daid2_fk[daid]
        try:
            # Compute homography from chip2 to chip1
            # returned homography maps image1 space into image2 space
            # image1 is a query chip and image2 is a database chip
            sv_tup = sver.spatially_verify_kpts(
                kpts1, kpts2, fm, xy_thresh, scale_thresh, ori_thresh,
                dlen_sqrd2, min_nInliers,
                returnAff=qreq_.qparams.with_metadata)
        except Exception as ex:
            ut.printex(ex, 'Unknown error in spatial verification.',
                          keys=['kpts1', 'kpts2',  'fm', 'xy_thresh',
                                'scale_thresh', 'dlen_sqrd2', 'min_nInliers'])
            sv_tup = None
        if sv_tup is not None:
            # Return the inliers to the homography from chip2 to chip1
            (homog_inliers, homog_errors, H, aff_inliers, aff_errors, Aff) = sv_tup
            if qreq_.qparams.with_metadata:
                daid2_svtup[daid] = sv_tup
            fm_SV = fm[homog_inliers]
            fsv_SV = fsv[homog_inliers]
            fk_SV = fk[homog_inliers]
            if sver_weighting:
                # Rescore based on homography errors
                #xy_thresh_sqrd = dlen_sqrd2 * xy_thresh
                xy_thresh_sqrd = dlen_sqrd2 * xy_thresh
                homog_xy_errors = homog_errors[0][homog_inliers]
                homog_err_weight = (1.0 - np.sqrt(homog_xy_errors / xy_thresh_sqrd))
                #with ut.EmbedOnException():
                homog_err_weight.shape = (homog_err_weight.size, 1)
                fsv_SV = np.concatenate((fsv_SV, homog_err_weight), axis=1)
                #fsv_SV = np.hstack((fsv_SV, homog_err_weight))
            daid2_fm_V[daid]  = fm_SV
            daid2_fsv_V[daid] = fsv_SV
            daid2_fk_V[daid]  = fk_SV
            daid2_H_V[daid]   = H
            #nFeatMatchSVAff += len(aff_inliers)
    chipmatchSV = hstypes.fix_chipmatch(chipmatchSV_)
    return chipmatchSV, daid2_svtup


def get_prescore_shortlist(qreq_, qaid, chipmatch):
    """
    computes which of the annotations should continue in the next pipeline step
    based on the current score.


    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict()
        >>> ibs, qreq_ = get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'spatial_verification')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch_FILT']
        >>> qaid = qreq_.get_external_qaids()[0]
        >>> chipmatch = qaid2_chipmatch[qaid]
        >>> (topx2_aid, nRerank) = get_prescore_shortlist(qreq_, qaid, chipmatch)

    """
    prescore_method = qreq_.qparams.prescore_method
    nShortlist      = qreq_.qparams.nShortlist
    daid2_prescore = score_chipmatch(qreq_, qaid, chipmatch, prescore_method)
    #print('Prescore: %r' % (daid2_prescore,))
    # HACK FOR NAME PRESCORING
    if prescore_method == 'nsum':
        topx2_aid = prescore_nsum(qreq_, daid2_prescore, nShortlist)
        nRerank = len(topx2_aid)
    else:
        topx2_aid = ut.util_dict.keys_sorted_by_value(daid2_prescore)[::-1]
        nRerank = min(len(topx2_aid), nShortlist)
    return topx2_aid, nRerank


def prescore_nsum(qreq_, daid2_prescore, nShortlist):
    """
    CommandLine:
        python -m ibeis.model.hots.pipeline --test-prescore_nsum

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict(codename='nsum_unnorm', index_method='single')
        >>> ibs, qreq_ = get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'spatial_verification', verbose=True)
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch_FILT']
        >>> qaid = qreq_.get_external_qaids()[0]
        >>> chipmatch = qaid2_chipmatch[qaid]
        >>> nShortlist = qreq_.qparams.nShortlist
        >>> prescore_method = qreq_.qparams.prescore_method
        >>> ut.assert_eq(prescore_method, 'nsum', 'pipeline supposed to be nsum')
        >>> daid2_prescore = score_chipmatch(qreq_, qaid, chipmatch, prescore_method)
    """
    daid_list = np.array(daid2_prescore.keys())
    prescore_arr = np.array(daid2_prescore.values())
    nscore_tup = name_scoring.group_scores_by_name(qreq_.ibs, daid_list, prescore_arr)
    (sorted_nids, sorted_nscore, sorted_aids, sorted_scores) = nscore_tup
    topx2_aid = ut.flatten(sorted_aids)
    return topx2_aid


def precompute_topx2_dlen_sqrd(qreq_, aid2_fm, topx2_aid, topx2_kpts,
                                nRerank, use_chip_extent):
    """
    helper for spatial verification, computes the squared diagonal length of
    matching chips

    Args:
        qreq_ (QueryRequest): hyper-parameters
        aid2_fm (dict):
        topx2_aid (dict):
        topx2_kpts (dict):
        nRerank (int):
        use_chip_extent (bool):

    Returns:
        topx2_dlen_sqrd

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-precompute_topx2_dlen_sqrd

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict()
        >>> ibs, qreq_ = get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'spatial_verification')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch_FILT']
        >>> qaid = qreq_.get_external_qaids()[0]
        >>> chipmatch = qaid2_chipmatch[qaid]
        >>> topx2_aid, nRerank = get_prescore_shortlist(qreq_, qaid, chipmatch)
        >>> (aid2_fm, aid2_fsv, aid2_fk, aid2_score, aid2_H) = chipmatch
        >>> kpts1 = qreq_.ibs.get_annot_kpts(qaid, qreq_=qreq_)
        >>> topx2_kpts = qreq_.ibs.get_annot_kpts(topx2_aid, qreq_=qreq_)
        >>> use_chip_extent = False
        >>> topx2_dlen_sqrd = precompute_topx2_dlen_sqrd(qreq_, aid2_fm, topx2_aid, topx2_kpts, nRerank, use_chip_extent)

    """
    if use_chip_extent:
        #topx2_dlen_sqrd = [
        #    ((w ** 2) + (h ** 2))
        #    for (w, h) in qreq_.ibs.get_annot_chip_sizes(topx2_aid[:nRerank], qreq_=qreq_)
        #]
        topx2_dlen_sqrd = qreq_.ibs.get_annot_chip_dlensqrd(topx2_aid[:nRerank], qreq_=qreq_)
        return topx2_dlen_sqrd
    else:
        # Use extent of matching keypoints
        # first get matching keypoints
        top_kpts_list = ut.list_take(topx2_kpts, range(nRerank))
        top_aid_list  = ut.list_take(topx2_aid, range(nRerank))
        top_fm_list   = ut.dict_take(aid2_fm, top_aid_list)
        top_kpts2_m_list = [kpts.take(fm.T[1], axis=0)
                            for (kpts, fm) in zip(top_kpts_list, top_fm_list)]
        topx2_dlen_sqrd = [ktool.get_kpts_dlen_sqrd(kpts2_m)
                           for kpts2_m in top_kpts2_m_list]
    return topx2_dlen_sqrd


@profile
def hack_fix_dupvote_weights(qreq_, qaid2_chipmatchSV):
    """
    If the one feature allowed to match to a name was removed by spatial
    verification then that feature never gets to vote.

    Maybe that is a good thing, but maybe we should try and reclaim it.

    CommandLine:
        python main.py --verbose --noqcache --cfg codename:vsmany_nsum  --query 1 --db PZ_MTEST

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-hack_fix_dupvote_weights

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> from ibeis.model.hots.pipeline import _spatial_verification
        >>> cfgdict = dict(dupvote_weight=1.0, prescore_method='nsum', score_method='nsum', K=10)
        >>> ibs, qreq_ = get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'spatial_verification')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch_FILT']
        >>> qaid2_nnfilts = locals_['qaid2_nnfilts']
        >>> dupvotex = ut.listfind(qreq_.qparams.active_filter_list, hstypes.FiltKeys.DUPVOTE)
        >>> assert dupvotex is not None, 'dupvotex=%r' % dupvotex
        >>> qaid2_chipmatchSV = _spatial_verification(qreq_, qaid2_chipmatch)
        >>> before = [[fsv.T[dupvotex].sum()
        ...              for fsv in six.itervalues(chipmatch[1])]
        ...                  for chipmatch in six.itervalues(qaid2_chipmatchSV)]
        >>> before_sum = sum(ut.flatten(before))
        >>> print('before_sum=%r' % (before_sum))
        >>> ut.assert_inbounds(before_sum, 1940, 2200)
        >>> # execute test
        >>> total_reweighted = hack_fix_dupvote_weights(qreq_, qaid2_chipmatchSV)
        >>> print('total_reweighted=%r' % (total_reweighted))
        >>> after = [[fsv.T[dupvotex].sum()
        ...              for fsv in six.itervalues(chipmatch[1])]
        ...                  for chipmatch in six.itervalues(qaid2_chipmatchSV)]
        >>> after_sum = sum(ut.flatten(after))
        >>> print('after_sum=%r' % (after_sum))
        >>> diff = after_sum - before_sum
        >>> assert after_sum >= before_sum, 'sum should increase only'
        >>> ut.assert_inbounds(after_sum, 1950, 2210)
        >>> ut.assert_inbounds(total_reweighted, 5, 25)
        >>> ut.assert_inbounds(diff - total_reweighted, -1E-5, 1E-5)
        >>> total_reweighted2 = hack_fix_dupvote_weights(qreq_, qaid2_chipmatchSV)
        >>> print('total_reweighted2=%r' % (total_reweighted))
        >>> ut.assert_eq(total_reweighted2, 0, 'should be 0 reweighted')
    """
    #filtlist_list = [nnfilts[0] for nnfilts in six.itervalues(qaid2_nnfilts)]
    #assert ut.list_allsame(filtlist_list), 'different queries with differnt filts'
    #filtkey_list = filtlist_list[0]
    dupvotex = ut.listfind(qreq_.qparams.active_filter_list, hstypes.FiltKeys.DUPVOTE)
    if dupvotex is None:
        return
    dupvote_true = qreq_.qparams.filt2_stw[hstypes.FiltKeys.DUPVOTE][2]
    num_reweighted_list = []

    for qaid, chipmatch in six.iteritems(qaid2_chipmatchSV):
        num_reweighted = 0
        daid2_fm, daid2_fsv, daid2_fk, aid2_score, daid2_H = chipmatch
        daid_list = np.array(list(six.iterkeys(daid2_fsv)))
        fm_list = np.array(list(six.itervalues(daid2_fm)))
        fsv_list = np.array(list(six.itervalues(daid2_fsv)))
        # get dup weights in scores
        dw_list = np.array([fsv.T[dupvotex] for fsv in fsv_list])
        fk_list = np.array(list(six.itervalues(daid2_fk)))
        dnid_list = np.array(qreq_.ibs.get_annot_nids(list(daid_list)))
        unique_nids, nid_groupx = vt.group_indicies(dnid_list)
        grouped_fm = vt.apply_grouping(fm_list, nid_groupx)
        grouped_dw = vt.apply_grouping(dw_list, nid_groupx)
        grouped_fk = vt.apply_grouping(fk_list, nid_groupx)
        grouped_daids = vt.apply_grouping(daid_list, nid_groupx)

        for daid_group, fm_group, dw_group, fk_group in zip(grouped_daids, grouped_fm, grouped_dw, grouped_fk):
            # all query features assigned to different annots in this name
            qfx_group = [fm.T[0] for fm in fm_group]
            flat_qfxs = np.hstack(qfx_group)
            #flat_dfws = np.hstack(dw_group)
            duplicate_qfxs = vt.find_duplicate_items(flat_qfxs)
            for qfx in duplicate_qfxs:
                idxs = [np.flatnonzero(qfxs == qfx) for qfxs in qfx_group]
                dupdws = [dws[idx] for idx, dws in zip(idxs, dw_group)]
                flat_dupdws = np.hstack(dupdws)
                # hack to find features where all votes are dupvote downweighted
                if np.all(flat_dupdws < .1):
                    dupdws
                    dupfks = [fks[idx] for idx, fks in zip(idxs, fk_group)]
                    flat_dupdws = np.hstack(dupfks)
                    # This feature needs its dupvote weight back
                    reweight_fk = np.min(flat_dupdws)
                    reweight_groupxs = np.nonzero([reweight_fk in fks for fks in dupfks])[0]
                    assert len(reweight_groupxs) == 1
                    reweight_groupx = reweight_groupxs[0]
                    reweight_daid = daid_group[reweight_groupx]
                    reweight_fsvxs = np.where(vt.and_lists(
                        daid2_fk[reweight_daid] == reweight_fk,
                        daid2_fm[reweight_daid].T[0] == qfx
                    ))[0]
                    assert len(reweight_fsvxs) == 1
                    reweight_fsvx = reweight_fsvxs[0]
                    # inplace modify
                    assert daid2_fsv[reweight_daid].T[dupvotex][reweight_fsvx] < .1, 'this was already reweighted'
                    daid2_fsv[reweight_daid].T[dupvotex][reweight_fsvx] = dupvote_true
                    num_reweighted += 1
                    #raise StopIteration('fds')

                #hasmatches = np.array(list(map(len, dupdws))) > 1
                #print(hasmatches)
                #if np.sum(hasmatches) > 1:
                #    raise StopIteration('fds')
                #    break
                #    pass
                #for idx in zip(fk_group, fsv_group, idxs
                #       pass
            #unique_indicies = vt.group_indicies(flat_qfxs)
            #idx2_groupid = flat_qfxs
            pass
        num_reweighted_list.append(num_reweighted)
    total_reweighted = sum(num_reweighted_list)
    #print('num_reweighted_list = %r' % (num_reweighted_list,))
    #print('total_reweighted = %r' % (total_reweighted,))
    return total_reweighted

#============================
# 5.5ish) Vsone Reranking
#============================


def vsone_reranking(qreq_, qaid2_chipmatch, verbose=VERB_PIPELINE):
    """
    CommandLine:
        python -m ibeis.model.hots.pipeline --test-vsone_reranking
        python -m ibeis.model.hots.pipeline --test-vsone_reranking --show

    Example2:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict(dupvote_weight=1.0, prescore_method='nsum', score_method='nsum', vsone_reranking=True)
        >>> ibs, qreq_ = get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict, qaid_list=[2])
        >>> locals_ = testrun_pipeline_upto(qreq_, 'vsone_reranking')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch_SVER']
        >>> verbose = True
        >>> qaid2_chipmatch_VSONE = vsone_reranking(qreq_, qaid2_chipmatch, verbose=verbose)
        >>> if ut.show_was_requested():
        >>>     from ibeis.model.hots import vsone_pipeline
        >>>     import plottool as pt
        >>>     # NOTE: the aid2_score field must have been hacked
        >>>     vsone_pipeline.show_top_chipmatches(ibs, qaid2_chipmatch, 0,  'prescore')
        >>>     vsone_pipeline.show_top_chipmatches(ibs, qaid2_chipmatch_VSONE,   1, 'vsone-reranked')
        >>>     pt.show_if_requested()
    """
    from ibeis.model.hots import vsone_pipeline
    if verbose:
        print('Step 5.5ish) vsone reranking')
    qaid2_chipmatch_VSONE = vsone_pipeline.vsone_reranking(qreq_, qaid2_chipmatch, verbose)
    return qaid2_chipmatch_VSONE


#============================
# 6) Query Result Format
#============================


@profile
def chipmatch_to_resdict(qreq_, qaid2_chipmatch, verbose=VERB_PIPELINE):
    """
    Converts a dictionary of chipmatch tuples into a dictionary of query results

    Args:
        qaid2_chipmatch (dict):
        metadata (dict):
        qreq_ (QueryRequest): hyper-parameters

    Returns:
        qaid2_qres

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-chipmatch_to_resdict
        python -m ibeis.model.hots.pipeline --test-chipmatch_to_resdict:1

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict(dupvote_weight=1.0, prescore_method='nsum', score_method='nsum')
        >>> ibs, qreq_ = get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'chipmatch_to_resdict')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch']
        >>> qaid2_qres = chipmatch_to_resdict(qreq_, qaid2_chipmatch)
        >>> qres = qaid2_qres[1]

    Example2:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict(dupvote_weight=1.0, prescore_method='nsum', score_method='nsum', sver_weighting=True)
        >>> ibs, qreq_ = get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'chipmatch_to_resdict')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch']
        >>> qaid2_qres = chipmatch_to_resdict(qreq_, qaid2_chipmatch)
        >>> qres = qaid2_qres[1]
        >>> num_filtkeys = len(qres.filtkey_list)
        >>> ut.assert_eq(num_filtkeys, qres.aid2_fsv[2].shape[1])
        >>> ut.assert_eq(num_filtkeys, 4)
        >>> ut.assert_inbounds(qres.aid2_fsv[2].shape[0], 105, 150)
        >>> assert np.all(qres.aid2_fs[2] == qres.aid2_fsv[2].prod(axis=1)), 'math is broken'

    """
    if verbose:
        print('[hs] Step 6) Convert chipmatch -> qres')
    external_qaids   = qreq_.get_external_qaids()
    # Matchable daids
    score_method = qreq_.qparams.score_method
    # Create the result structures for each query.
    filtkey_list = qreq_.qparams.get_postsver_filtkey_list()
    #filtkey_list = qreq_.qparams.active_filter_list
    #if qreq_.qparams.sver_weighting:
    #    filtkey_list = filtkey_list[:] + [hstypes.FiltKeys.HOMOGERR]

    qres_list = qreq_.make_empty_query_results()

    for qaid, qres in zip(external_qaids, qres_list):
        # For each query's chipmatch
        qres.filtkey_list = filtkey_list
        chipmatch = qaid2_chipmatch[qaid]  # FIXME: use a list
        # unpack the chipmatch and populate qres
        #if chipmatch is not None:
        aid2_fm, aid2_fsv, aid2_fk, aid2_score, daid2_H = chipmatch
        qres.aid2_fm = aid2_fm
        # HACK IN SCORE VECTORS
        qres.aid2_fsv = aid2_fsv
        # FIXME: This score is not valid. We have different code
        # that aggregates scores from fsv into fs
        #with ut.EmbedOnException():
        qres.aid2_fs = {daid: fsv.prod(axis=1)
                        for daid, fsv in six.iteritems(aid2_fsv)}
        qres.aid2_fk = aid2_fk
        # TODO:
        # WE SHOULD BE TAKING SCORES FROM THE NEW CHIPMATCH STRUCTURE HERE
        # ------
        # Perform final scoring
        if aid2_score is None or len(aid2_score) == 0:
            # In this case the aid2_score has not been populated by some method
            # like vsone reranking
            daid2_score = score_chipmatch(qreq_, qaid, chipmatch, score_method)
        else:
            daid2_score = aid2_score
        # TODO: Score normalization should happen in its own pipeline node
        # Normalize scores if requested
        if qreq_.qparams.score_normalization:
            normalizer = qreq_.normalizer
            score_list = list(six.itervalues(daid2_score))
            prob_list = normalizer.normalize_score_list(score_list)
            daid2_prob = dict(zip(six.iterkeys(daid2_score), prob_list))
            qres.aid2_prob = daid2_prob
        qres.aid2_H = daid2_H
        # Populate query result fields
        qres.aid2_score = daid2_score
        # Populate query result metadata (things like k+1th neighbor)
        qres.metadata = {}
        for key, qaid2_meta in six.iteritems(qreq_.metadata):
            qres.metadata[key] = qaid2_meta[qaid]
    # Build dictionary structure to maintain functionality
    qaid2_qres = {qaid: qres for qaid, qres in zip(external_qaids, qres_list)}
    return qaid2_qres


#============================
# Scoring Mechanism
#============================

#@ut.indent_func('[scm]')
@profile
def score_chipmatch(qreq_, qaid, chipmatch, score_method):
    """
    Assigns scores to database annotation ids for a particualry query's
    chipmatch

    DOES NOT APPLY SCORE NORMALIZATION

    Args:
        qreq_ (QueryRequest): hyper-parameters
        qaid (int): query annotation id
        chipmatch (tuple):
        score_method (str):
        isprescore (bool): flag

    Returns:
        daid2_score : scores for each database id w.r.t. a single query

    CommandLine:
        python -m ibeis.model.hots.pipeline --test-score_chipmatch

    Example:
        >>> # DISABLE_ENABLE
        >>> # PRESCORE
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict(codename='nsum')
        >>> ibs, qreq_ = get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'spatial_verification')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch_FILT']
        >>> qaid = qreq_.get_external_qaids()[0]
        >>> chipmatch = qaid2_chipmatch[qaid]
        >>> score_method = qreq_.qparams.prescore_method
        >>> daid2_score_pre = score_chipmatch(qreq_, qaid, chipmatch, score_method)

    Example2:
        >>> # POSTSCORE
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> cfgdict = dict(codename='nsum')
        >>> ibs, qreq_ = get_pipeline_testdata('PZ_MTEST', cfgdict=cfgdict)
        >>> locals_ = testrun_pipeline_upto(qreq_, 'chipmatch_to_resdict')
        >>> qaid2_chipmatch = locals_['qaid2_chipmatch']
        >>> qaid = qreq_.get_external_qaids()[0]
        >>> chipmatch = qaid2_chipmatch[qaid]
        >>> score_method = qreq_.qparams.score_method
        >>> daid2_score_post = score_chipmatch(qreq_, qaid, chipmatch, score_method)
    """
    # HACK: Im not even sure if the 'w' suffix is correctly handled anymore
    if score_method.find('w') == len(score_method) - 1:
        score_method = score_method[:-1]
    # Choose the appropriate scoring mechanism
    if score_method == 'csum':
        (aid_list, score_list) = vr2.score_chipmatch_csum(qaid, chipmatch, qreq_)
    elif score_method == 'nsum':
        (aid_list, score_list) = vr2.score_chipmatch_nsum(qaid, chipmatch, qreq_)
    #elif score_method == 'pl':
    #    daid2_score, nid2_score = vr2.score_chipmatch_PL(qaid, chipmatch, qreq_)
    #elif score_method == 'borda':
    #    daid2_score, nid2_score = vr2.score_chipmatch_pos(qaid, chipmatch, qreq_, 'borda')
    #elif score_method == 'topk':
    #    daid2_score, nid2_score = vr2.score_chipmatch_pos(qaid, chipmatch, qreq_, 'topk')
    #elif score_method.startswith('coverage'):
    #    # Method num is at the end of coverage
    #    method = int(score_method.replace('coverage', '0'))
    #    daid2_score = coverage_kpts.score_chipmatch_coverage(qaid, chipmatch, qreq_, method=method)
    else:
        raise Exception('[hs] unknown scoring method:' + score_method)

    # HACK: should not use dicts in pipeline if it can be helped
    daid2_score = dict(zip(aid_list, score_list))
    return daid2_score


#============================
# Result Caching
#============================


#@ut.indent_func('[tlr]')
@profile
def try_load_resdict(qreq_, force_miss=False, verbose=VERB_PIPELINE):
    """
    Try and load the result structures for each query.
    returns a list of failed qaids

    Args:
        qreq_ (QueryRequest): hyper-parameters
        force_miss (bool):

    Returns:
        dict : qaid2_qres_hit

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.model.hots.pipeline import *  # NOQA
        >>> qreq_ = '?'
        >>> force_miss = False
        >>> verbose = False
        >>> qaid2_qres_hit = try_load_resdict(qreq_, force_miss, verbose)
        >>> result = str(qaid2_qres_hit)
        >>> print(result)
    """
    qaids   = qreq_.get_external_qaids()
    qauuids = qreq_.get_external_quuids()
    daids   = qreq_.get_external_daids()

    cfgstr = qreq_.get_cfgstr()
    qresdir = qreq_.get_qresdir()
    qaid2_qres_hit = {}
    #cachemiss_qaids = []
    # TODO: could prefiler paths that don't exist
    for qaid, qauuid in zip(qaids, qauuids):
        qres = hots_query_result.QueryResult(qaid, qauuid, cfgstr, daids)
        try:
            qres.load(qresdir, force_miss=force_miss, verbose=verbose)  # 77.4 % time
        except (hsexcept.HotsCacheMissError, hsexcept.HotsNeedsRecomputeError) as ex:
            if ut.VERYVERBOSE:
                ut.printex(ex, iswarning=True)
            #cachemiss_qaids.append(qaid)  # cache miss
        else:
            qaid2_qres_hit[qaid] = qres  # cache hit
    return qaid2_qres_hit  # , cachemiss_qaids


@profile
def save_resdict(qreq_, qaid2_qres, verbose=VERB_PIPELINE):
    """
    Saves a dictionary of query results to disk

    Args:
        qreq_ (QueryRequest): hyper-parameters
        qaid2_qres (dict):

    Returns:
        None
    """
    qresdir = qreq_.get_qresdir()
    if verbose:
        print('[hs] saving %d query results' % len(qaid2_qres))
    for qres in six.itervalues(qaid2_qres):
        qres.save(qresdir)


#============================
# Testdata
#============================


if __name__ == '__main__':
    """
    python -m ibeis.model.hots.pipeline --verb-test
    python -m ibeis.model.hots.pipeline --test-build_chipmatches
    python -m ibeis.model.hots.pipeline --test-spatial-verification
    python -m ibeis.model.hots.pipeline --test-request_ibeis_query_L0 --show
    python -m ibeis.model.hots.pipeline --test-request_ibeis_query_L0:0 --show
    python -m ibeis.model.hots.pipeline --test-request_ibeis_query_L0:1 --show --db NAUT_test
    python -m ibeis.model.hots.pipeline --test-request_ibeis_query_L0:1 --db NAUT_test --noindent
    python -m ibeis.model.hots.pipeline --allexamples
    """
    import multiprocessing
    multiprocessing.freeze_support()
    ut.doctest_funcs()
    if ut.get_argflag('--show'):
        from plottool import df2
        exec(df2.present())
