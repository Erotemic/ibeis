# -*- coding: utf-8 -*-
"""
TODO: make qparams and qreq_ serializeable

TODO:
    Rename to IdentifyRequest
"""
from __future__ import absolute_import, division, print_function
from ibeis.model.hots import neighbor_index
from ibeis.model.hots import multi_index
from ibeis.model.hots import score_normalization
from ibeis.model.hots import distinctiveness_normalizer
from ibeis.model.hots import query_params
from ibeis.model.hots import _pipeline_helpers as plh  # NOQA
import vtool as vt
#import copy
import six
import utool as ut
import numpy as np
import warnings
from ibeis.model.hots import hots_query_result
(print, print_, printDBG, rrr, profile) = ut.inject(__name__, '[qreq]')

VERBOSE = ut.VERBOSE or ut.get_argflag(('--verbose-qreq', '--verbqreq'))


def testdata_newqreq(defaultdb):
    import ibeis
    ibs = ibeis.opendb(defaultdb=defaultdb)
    qaid_list = [1]
    daid_list = [1, 2, 3, 4, 5]
    return ibs, qaid_list, daid_list


def testdata_qreq():
    import ibeis
    qaid_list = [1, 2]
    daid_list = [1, 2, 3, 4, 5]
    ibs = ibeis.opendb(db='testdb1')
    qreq_ = new_ibeis_query_request(ibs, qaid_list, daid_list)
    return qreq_, ibs


@profile
def new_ibeis_query_request(ibs, qaid_list, daid_list, cfgdict=None,
                            verbose=ut.NOT_QUIET, unique_species=None,
                            use_memcache=True, query_cfg=None):
    """
    ibeis entry point to create a new query request object

    CommandLine:
        python -m ibeis.model.hots.query_request --test-new_ibeis_query_request
        python -m ibeis.model.hots.query_request --test-new_ibeis_query_request:2

    Example0:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.query_request import *  # NOQA
        >>> ibs, qaid_list, daid_list = testdata_newqreq('PZ_MTEST')
        >>> unique_species = None
        >>> verbose = ut.NOT_QUIET
        >>> cfgdict = {'sv_on': False, 'fg_on': True}
        >>> # Execute test
        >>> qreq_ = new_ibeis_query_request(ibs, qaid_list, daid_list, cfgdict=cfgdict)
        >>> # Check Results
        >>> print(qreq_.qparams.query_cfgstr)
        >>> assert qreq_.qparams.sv_on is False, (
        ...     'qreq_.qparams.sv_on = %r ' % qreq_.qparams.sv_on)
        >>> result = ibs.get_dbname() + qreq_.get_data_hashid()
        >>> print(result)
        PZ_MTEST_DSUUIDS((5)@n7v0df!&j5o8pni)

        PZ_MTEST_DSUUIDS((5)q87ho9a0@9s02imh)

    Example1:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.query_request import *  # NOQA
        >>> ibs, qaid_list, daid_list = testdata_newqreq('NAUT_test')
        >>> unique_species = None
        >>> verbose = ut.NOT_QUIET
        >>> cfgdict = {'sv_on': True, 'fg_on': True}
        >>> # Execute test
        >>> qreq_ = new_ibeis_query_request(ibs, qaid_list, daid_list, cfgdict=cfgdict)
        >>> # Check Results.
        >>> # Featweight should be off because there is no Naut detector
        >>> print(qreq_.qparams.query_cfgstr)
        >>> assert qreq_.qparams.sv_on is True, (
        ...     'qreq_.qparams.sv_on = %r ' % qreq_.qparams.sv_on)
        >>> result = ibs.get_dbname() + qreq_.get_data_hashid()
        >>> print(result)
        NAUT_test_DSUUIDS((5)&flvjboruwyi08%t)

    NAUT_test_DSUUIDS((5)4e972cjxcj30a8u1)
    NAUT_test_DSUUIDS((5)8l4exo@+@b+kh9!!)

    Example2:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.query_request import *  # NOQA
        >>> ibs, qaid_list, daid_list = testdata_newqreq('PZ_MTEST')
        >>> unique_species = None
        >>> verbose = ut.NOT_QUIET
        >>> cfgdict = {'sv_on': False, 'augment_queryside_hack': True}
        >>> # Execute test
        >>> qreq_ = new_ibeis_query_request(ibs, qaid_list, daid_list, cfgdict=cfgdict)
        >>> # Check Results.
        >>> # Featweight should be off because there is no Naut detector
        >>> print(qreq_.qparams.query_cfgstr)
        >>> assert qreq_.qparams.sv_on is False, (
        ...     'qreq_.qparams.sv_on = %r ' % qreq_.qparams.sv_on)
        >>> result = ibs.get_dbname() + qreq_.get_data_hashid()
        >>> print(result)
        PZ_MTEST_DSUUIDS((5)@n7v0df!&j5o8pni)


    Ignore:
        # This is supposed to be the begginings of the code to transition the
        # pipeline configuration into the new minimal dict based structure that
        # supports different configs for query and database annotations.
        dcfg = qreq_.get_external_data_config2()
        qcfg = qreq_.get_external_query_config2()
        ut.dict_intersection(qcfg.__dict__, dcfg.__dict__)

        from ibeis.experiments import cfghelpers
        cfg_list = [qcfg.__dict__, dcfg.__dict__]
        nonvaried_cfg, varied_cfg_list = cfghelpers.partition_varied_cfg_list(
            cfg_list, recursive=True)
        qvaried, dvaried = varied_cfg_list
    """
    if verbose:
        print('[qreq] +--- New IBEIS QRequest --- ')
    cfg     = ibs.cfg.query_cfg if query_cfg is None else query_cfg
    qresdir = ibs.get_qres_cachedir()
    cfgdict = {} if cfgdict is None else cfgdict.copy()

    DYNAMIC_K = False
    if DYNAMIC_K and 'K' not in cfgdict:
        model_params = [0.2,  0.5]
        from ibeis.other.optimize_k import compute_K
        nDaids = len(daid_list)
        cfgdict['K'] = compute_K(nDaids, model_params)

    # <HACK>
    if unique_species is None:
        unique_species_ = apply_species_with_detector_hack(
            ibs, cfgdict, qaid_list, daid_list)
    else:
        unique_species_ = unique_species
    # </HACK>
    qparams = query_params.QueryParams(cfg, cfgdict)
    data_config2_ = qparams
    #
    # <HACK>
    # MAKE A SECOND CONFIG FOR QUERIES AND DATABASE VECTORS ONLY
    # allow query and database annotations to have different feature configs
    if qparams.augment_queryside_hack:
        query_cfgdict = cfgdict.copy()
        query_cfgdict['augment_orientation'] = True
        query_config2_ = query_params.QueryParams(cfg, query_cfgdict)
    else:
        query_config2_ = qparams
    # </HACK>
    _indexer_request_params = dict(use_memcache=use_memcache)
    qreq_ = QueryRequest.new_query_request(
        qaid_list, daid_list, qparams, qresdir, ibs, _indexer_request_params)
    qreq_.query_config2_ = query_config2_
    qreq_.data_config2_ = data_config2_
    qreq_.unique_species = unique_species_  # HACK
    if verbose:
        print('[qreq] * query_cfgstr = %s' % (qreq_.qparams.query_cfgstr,))
        print('[qreq] * unique_species = %s' % (qreq_.unique_species,))
        print('[qreq] * len(qaid_list) = %s' % (len(qaid_list),))
        print('[qreq] * len(daid_list) = %s' % (len(daid_list),))
        print('[qreq] * data_hashid   = %s' % (qreq_.get_data_hashid(),))
        print('[qreq] * query_hashid  = %s' % (qreq_.get_query_hashid(),))
        print('[qreq] L___ New IBEIS QRequest ___ ')
    return qreq_


@profile
def apply_species_with_detector_hack(ibs, cfgdict, qaids, daids,
                                     verbose=VERBOSE):
    """
    HACK turns of featweights if they cannot be applied
    """
    # Only apply the hack with repsect to the queried annotations
    aid_list = np.hstack((qaids, daids)).tolist()
    unique_species = ibs.get_database_species(aid_list)
    # turn off featureweights when not absolutely sure they are ok to us,)
    candetect = (len(unique_species) == 1 and
                 ibs.has_species_detector(unique_species[0]))
    if not candetect:
        if ut.NOT_QUIET:
            print('[qreq] HACKING FG_WEIGHT OFF (db species is not supported)')
            if len(unique_species) != 1:
                print('[qreq]  * len(unique_species) = %r' % len(unique_species))
            else:
                print('[qreq]  * unique_species = %r' % (unique_species,))
        #print('[qreq]  * valid species = %r' % (
        #    ibs.get_species_with_detectors(),))
        #cfg._featweight_cfg.featweight_enabled = 'ERR'
        cfgdict['featweight_enabled'] = 'ERR'
        cfgdict['fg_on'] = False
    else:
        #print(ibs.get_annot_species_texts(aid_list))
        if verbose:
            print('[qreq] Using fgweights of unique_species=%r' % (
                unique_species,))
        pass
        #, aid_list=%r' % (unique_species, aid_list))
    return unique_species


@six.add_metaclass(ut.ReloadingMetaclass)
class QueryRequest(object):
    """
    Request object for pipline paramter run
    """

    @classmethod
    def new_query_request(cls, qaid_list, daid_list, qparams, qresdir, ibs,
                          _indexer_request_params):
        """
        old way of calling new
        """
        qreq_ = cls()
        qreq_.ibs = ibs
        qreq_.qparams = qparams   # Parameters relating to pipeline execution
        qreq_.qresdir = qresdir
        qreq_._indexer_request_params = _indexer_request_params
        qreq_.set_external_daids(daid_list)
        qreq_.set_external_qaids(qaid_list)
        return qreq_

    def __init__(qreq_):
        # Reminder:
        # lists and other objects are functionally equivalent to pointers
        #
        # Conceptually immutable State
        qreq_.unique_species = None  # num categories
        qreq_.internal_qspeciesid_list = None  # category species id label list
        qreq_.internal_qaids = None
        qreq_.internal_daids = None
        # Conceptually mutable state
        qreq_.internal_qaids_mask = None
        qreq_.internal_daids_mask = None
        # Loaded Objects
        qreq_.ibs = None  # Handle to parent IBEIS Controller
        qreq_.indexer = None  # The nearest neighbor mechanism
        qreq_.normalizer = None  # The scoring normalization mechanism
        qreq_.dstcnvs_normer = None
        qreq_.hasloaded = False
        # Pipeline configuration
        qreq_.qparams = None   # Parameters relating to pipeline execution
        qreq_.query_config2_ = None
        qreq_.data_config2_ = None
        qreq_._indexer_request_params = None
        # Set values
        qreq_.unique_species = None  # HACK
        qreq_.qresdir = None
        qreq_.prog_hook = None

    #def write_query_request(qreq_, fpath):
    #    ut.save_cPickle(fpath, qreq_)

    def __getstate__(qreq_):
        """
        Make QueryRequest pickleable

        CommandLine:
            python -m ibeis.dev -t candidacy --db testdb1

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.model.hots.query_request import *  # NOQA
            >>> from six.moves import cPickle as pickle
            >>> qreq_, ibs = testdata_qreq()
            >>> qreq_dump = pickle.dumps(qreq_)
            >>> qreq2_ = pickle.loads(qreq_dump)
        """
        state_dict = qreq_.__dict__.copy()
        state_dict['dbdir'] = qreq_.ibs.get_dbdir()
        state_dict['ibs'] = None
        state_dict['prog_hook'] = None
        state_dict['indexer'] = None
        state_dict['normalizer'] = None
        state_dict['dstcnvs_normer'] = None
        state_dict['hasloaded'] = False
        return state_dict

    def __setstate__(qreq_, state_dict):
        #print('[!!!!!!!!!!!!!!!!!!!!] Calling set state.')
        import ibeis
        dbdir = state_dict['dbdir']
        del state_dict['dbdir']
        state_dict['ibs'] = ibeis.opendb(dbdir=dbdir, web=False)
        qreq_.__dict__.update(state_dict)

    @profile
    def shallowcopy(qreq_, qaids=None, qx=None, dx=None):
        """
        Creates a copy of qreq with the same qparams object and a subset of the
        qx and dx objects.  used to generate chunks of vsone and vsmany queries

        CommandLine:
            python -m ibeis.model.hots.query_request --exec-shallowcopy

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.model.hots.query_request import *  # NOQA
            >>> import ibeis
            >>> qreq_, ibs = testdata_qreq()
            >>> qreq2_ = qreq_.shallowcopy(qx=0)
            >>> assert qreq_.get_external_daids() is qreq2_.get_external_daids()
            >>> assert len(qreq_.get_external_qaids()) != len(qreq2_.get_external_qaids())
            >>> #assert qreq_.metadata is not qreq2_.metadata
        """
        #qreq2_ = copy.copy(qreq_)  # copy calls setstate and getstate
        qreq2_ = QueryRequest()
        qreq2_.__dict__.update(qreq_.__dict__)
        if qx is not None:
            qaid_list  = qreq2_.get_external_qaids()
            qaid_list  = qaid_list[qx:qx + 1]
            qreq2_.set_external_qaids(qaid_list)  # , quuid_list)
        elif qaids is not None:
            assert qx is None, 'cannot specify both qx and qaids'
            _intersect = np.intersect1d(qaids, qreq2_.get_external_qaids())
            assert len(_intersect) == len(qaids), 'not a subset'
            qreq2_.set_external_qaids(qaids)  # , quuid_list)
        if dx is not None:
            daid_list  = qreq2_.get_external_daids()
            daid_list  = daid_list[dx:dx + 1]
            #duuid_list = qreq2_.get_external_duuids()
            #duuid_list = duuid_list[dx:dx + 1]
            qreq2_.set_external_daids(daid_list)
        # The shallow copy does not bring over output / query data
        qreq2_.indexer = None
        #qreq2_.metadata = {}
        qreq2_.hasloaded = False
        return qreq2_

    # --- State Modification ---

    @profile
    def remove_internal_daids(qreq_, remove_daids):
        r"""
        State Modification: remove daids from the query request.  Do not call
        this function often. It invalidates the indexer, which is very slow to
        rebuild.  Should only be done between query pipeline runs.

        CommandLine:
            python -m ibeis.model.hots.query_request --test-remove_internal_daids

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.model.hots.query_request import *  # NOQA
            >>> import ibeis
            >>> # build test data
            >>> ibs = ibeis.opendb('testdb1')
            >>> species = ibeis.const.Species.ZEB_PLAIN
            >>> daids = ibs.get_valid_aids(species=species, is_exemplar=True)
            >>> qaids = ibs.get_valid_aids(species=species, is_exemplar=False)
            >>> qreq_ = ibs.new_query_request(qaids, daids)
            >>> remove_daids = daids[0:1]
            >>> # execute function
            >>> assert len(qreq_.internal_daids) == 4, 'bad setup data'
            >>> qreq_.remove_internal_daids(remove_daids)
            >>> # verify results
            >>> assert len(qreq_.internal_daids) == 3, 'did not remove'
        """
        # Invalidate the current indexer, mask and metadata
        qreq_.indexer = None
        qreq_.internal_daids_mask = None
        #qreq_.metadata = {}
        # Find indices to remove
        delete_flags = vt.get_covered_mask(qreq_.internal_daids, remove_daids)
        delete_indices = np.where(delete_flags)[0]
        assert len(delete_indices) == len(remove_daids), (
            'requested removal of nonexistant daids')
        # Remove indices
        qreq_.internal_daids = np.delete(qreq_.internal_daids, delete_indices)
        # TODO: multi-indexer delete support
        if qreq_.indexer is not None:
            warnings.warn('Implement point removal from trees')
            qreq_.indexer.remove_ibeis_support(qreq_, remove_daids)

    @profile
    def add_internal_daids(qreq_, new_daids):
        """
        State Modification: add new daid to query request. Should only be
        done between query pipeline runs
        """
        if ut.DEBUG2:
            species = qreq_.ibs.get_annot_species(new_daids)
            assert set(qreq_.unique_species) == set(species), (
                'inconsistent species')
        qreq_.internal_daids_mask = None
        #qreq_.metadata = {}
        qreq_.internal_daids = np.append(qreq_.internal_daids, new_daids)
        # TODO: multi-indexer add_support
        if qreq_.indexer is not None:
            #qreq_.load_indexer(verbose=True)
            qreq_.indexer.add_ibeis_support(qreq_, new_daids)

    @profile
    def set_external_daids(qreq_, daid_list):
        if qreq_.qparams.vsmany:
            qreq_.set_internal_daids(daid_list)
        else:
            qreq_.set_internal_qaids(daid_list)

    @profile
    def set_external_qaids(qreq_, qaid_list):
        if qreq_.qparams.vsmany:
            qreq_.set_internal_qaids(qaid_list)
        else:
            qreq_.set_internal_daids(qaid_list)

    @profile
    def set_external_qaid_mask(qreq_, masked_qaid_list):
        r"""
        Args:
            qaid_list (list):

        CommandLine:
            python -m ibeis.model.hots.query_request --test-set_external_qaid_mask

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.model.hots.query_request import *  # NOQA
            >>> import ibeis
            >>> ibs = ibeis.opendb(db='testdb1')
            >>> qaid_list = [1, 2, 3, 4, 5]
            >>> daid_list = [1, 2, 3, 4, 5]
            >>> qreq_ = ibs.new_query_request(qaid_list, daid_list)
            >>> masked_qaid_list = [2, 4, 5]
            >>> qreq_.set_external_qaid_mask(masked_qaid_list)
            >>> result = np.array_str(qreq_.get_external_qaids())
            >>> print(result)
            [1 3]
        """
        if qreq_.qparams.vsmany:
            qreq_.set_internal_masked_qaids(masked_qaid_list)
        else:
            qreq_.set_internal_masked_daids(masked_qaid_list)

    # --- Internal Annotation ID Masks ----

    @profile
    def set_internal_masked_daids(qreq_, masked_daid_list):
        """ used by the pipeline to execute a subset of the query request
        without modifying important state """
        if masked_daid_list is None or len(masked_daid_list) == 0:
            qreq_.internal_daids_mask = None
        else:
            #with ut.EmbedOnException():
            # input denotes invalid elements mark all elements not in that
            # list as True
            flags = vt.get_uncovered_mask(qreq_.internal_daids,
                                          masked_daid_list)
            assert len(flags) == len(qreq_.internal_daids), (
                'unequal len internal daids')
            qreq_.internal_daids_mask = flags

    @profile
    def set_internal_masked_qaids(qreq_, masked_qaid_list):
        """
        used by the pipeline to execute a subset of the query request
        without modifying important state

        Example:
            >>> # ENABLE_DOCTEST
            >>> import utool as ut
            >>> from ibeis.model.hots import pipeline
            >>> cfgdict1 = dict(codename='vsone', sv_on=True)
            >>> qaid_list = [1, 2, 3, 4]
            >>> daid_list = [1, 2, 3, 4]
            >>> ibs, qreq_ = plh.get_pipeline_testdata(cfgdict=cfgdict1,
            ...     qaid_list=qaid_list, daid_list=daid_list)
            >>> qaids = qreq_.get_internal_qaids()
            >>> ut.assert_lists_eq(qaid_list, qaids)
            >>> masked_qaid_list = [1, 2, 3,]
            >>> qreq_.set_internal_masked_qaids(masked_qaid_list)
            >>> new_internal_aids = qreq_.get_internal_qaids()
            >>> ut.assert_lists_eq(new_internal_aids, [4])
        """
        if masked_qaid_list is None or len(masked_qaid_list) == 0:
            qreq_.internal_qaids_mask = None
        else:
            #with ut.EmbedOnException():
            # input denotes invalid elements mark all elements not in that
            # list as True
            flags = vt.get_uncovered_mask(qreq_.internal_qaids,
                                          masked_qaid_list)
            assert len(flags) == len(qreq_.internal_qaids), (
                'unequal len internal qaids')
            qreq_.internal_qaids_mask = flags

    @profile
    def set_internal_unmasked_qaids(qreq_, unmasked_qaid_list):
        """
        used by the pipeline to execute a subset of the query request
        without modifying important state

        Example:
            >>> # ENABLE_DOCTEST
            >>> import utool as ut
            >>> from ibeis.model.hots import pipeline
            >>> cfgdict1 = dict(codename='vsone', sv_on=True)
            >>> qaid_list = [1, 2, 3, 4]
            >>> daid_list = [1, 2, 3, 4]
            >>> ibs, qreq_ = plh.get_pipeline_testdata(cfgdict=cfgdict1,
            ...     qaid_list=qaid_list, daid_list=daid_list)
            >>> qaids = qreq_.get_internal_qaids()
            >>> ut.assert_lists_eq(qaid_list, qaids)
            >>> unmasked_qaid_list = [1, 2, 3,]
            >>> qreq_.set_internal_unmasked_qaids(unmasked_qaid_list)
            >>> new_internal_aids = qreq_.get_internal_qaids()
            >>> ut.assert_lists_eq(new_internal_aids, unmasked_qaid_list)
        """
        if unmasked_qaid_list is None:
            qreq_.internal_qaids_mask = None
        else:
            # input denotes valid elements
            # mark all elements not in that list as False
            flags = vt.get_covered_mask(
                qreq_.internal_qaids, unmasked_qaid_list)
            assert len(flags) == len(qreq_.internal_qaids), (
                'unequal len internal qaids')
            qreq_.internal_qaids_mask = flags

    # --- Internal Annotation IDs ----

    @profile
    def set_internal_daids(qreq_, daid_list):
        qreq_.internal_daids_mask = None  # Invalidate mask
        qreq_.internal_daids = np.array(daid_list)

    @profile
    def set_internal_qaids(qreq_, qaid_list):
        qreq_.internal_qaids_mask = None  # Invalidate mask
        qreq_.internal_qaids = np.array(qaid_list)

    # --- INTERNAL INTERFACE ---
    # For within pipeline use only

    @profile
    def get_internal_daids(qreq_):
        if qreq_.internal_daids_mask is None:
            return qreq_.internal_daids
        else:
            return qreq_.internal_daids[qreq_.internal_daids_mask]

    @profile
    def get_internal_qaids(qreq_):
        if qreq_.internal_qaids_mask is None:
            return qreq_.internal_qaids
        else:
            return qreq_.internal_qaids[qreq_.internal_qaids_mask]

    @profile
    def get_internal_duuids(qreq_):
        return qreq_.ibs.get_annot_semantic_uuids(qreq_.get_internal_daids())

    @profile
    def get_internal_quuids(qreq_):
        return qreq_.ibs.get_annot_semantic_uuids(qreq_.get_internal_qaids())

    def get_internal_data_config2(qreq_):
        return (qreq_.data_config2_ if qreq_.qparams.vsmany else
                qreq_.query_config2_)

    def get_internal_query_config2(qreq_):
        return (qreq_.query_config2_ if qreq_.qparams.vsmany else
                qreq_.data_config2_)

    def get_external_data_config2(qreq_):
        return qreq_.data_config2_

    def get_external_query_config2(qreq_):
        return qreq_.query_config2_

    # --- EXTERNAL INTERFACE ---

    def get_unique_species(qreq_):
        return qreq_.unique_species

    # External id-lists

    @property
    def daids(qreq_):
        return qreq_.get_external_daids()

    @property
    def qaids(qreq_):
        return qreq_.get_external_qaids()

    @profile
    def get_external_daids(qreq_):
        """ These are the users daids in vsone mode """
        if qreq_.qparams.vsmany:
            return qreq_.get_internal_daids()
        else:
            return qreq_.get_internal_qaids()

    @profile
    def get_external_qaids(qreq_):
        """ These are the users qaids in vsone mode """
        if qreq_.qparams.vsmany:
            return qreq_.get_internal_qaids()
        else:
            return qreq_.get_internal_daids()

    @profile
    def get_external_quuids(qreq_):
        """ These are the users qauuids in vsone mode """
        if qreq_.qparams.vsmany:
            return qreq_.get_internal_quuids()
        else:
            return qreq_.get_internal_duuids()

    @profile
    def get_external_duuids(qreq_):
        """ These are the users qauuids in vsone mode """
        if qreq_.qparams.vsmany:
            return qreq_.get_internal_duuids()
        else:
            return qreq_.get_internal_quuids()

    @profile
    def get_external_query_groundtruth(qreq_, qaids):
        """ gets groundtruth that are accessible via this query """
        external_daids = qreq_.get_external_daids()
        gt_aids = qreq_.ibs.get_annot_groundtruth(
            qaids, daid_list=external_daids)
        return gt_aids

    # External id-hashes

    def get_data_hashid(qreq_):
        daids = qreq_.get_external_daids()
        try:
            assert len(daids) > 0, 'QRequest not populated. len(daids)=0'
        except AssertionError as ex:
            ut.printex(ex, iswarning=True)
        # TODO: SYSTEM : semantic should only be used if name scoring is on
        data_hashid = qreq_.ibs.get_annot_hashid_semantic_uuid(
            daids, prefix='D')
        return data_hashid

    def get_query_hashid(qreq_):
        qaids = qreq_.get_external_qaids()
        assert len(qaids) > 0, 'QRequest not populated. len(qaids)=0'
        # TODO: SYSTEM : semantic should only be used if name scoring is on
        query_hashid = qreq_.ibs.get_annot_hashid_semantic_uuid(
            qaids, prefix='Q')
        return query_hashid

    def get_internal_query_hashid(qreq_):
        if qreq_.qparams.vsmany:
            return qreq_.get_query_hashid()
        else:
            return qreq_.get_data_hashid()

    def get_internal_data_hashid(qreq_):
        if qreq_.qparams.vsmany:
            return qreq_.get_data_hashid()
        else:
            return qreq_.get_query_hashid()

    def get_pipe_cfgstr(qreq_):
        """
        FIXME: name
        params only """
        #query_cfgstr = qreq_.qparams.query_cfgstr
        pipe_cfgstr = qreq_.qparams.query_cfgstr
        return pipe_cfgstr

    def get_pipe_hashstr(qreq_):
        # this changes invalidates match_chip4 bibcaches generated before
        # august 24 2015
        #pipe_hashstr = ut.hashstr(qreq_.get_pipe_cfgstr())
        pipe_hashstr = ut.hashstr27(qreq_.get_pipe_cfgstr())
        return pipe_hashstr

    @profile
    def get_cfgstr(qreq_, with_query=False, with_data=True, with_pipe=True):
        r"""
        main cfgstring used to identify the 'querytype'
        FIXME: name params + data

        TODO:
            rename query_cfgstr to pipe_cfgstr or pipeline_cfgstr EVERYWHERE

        Args:
            with_query (bool): (default = False)

        Returns:
            str: cfgstr

        CommandLine:
            python -m ibeis.model.hots.query_request --exec-get_cfgstr

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.model.hots.query_request import *  # NOQA
            >>> import ibeis
            >>> ibs = ibeis.opendb(defaultdb='testdb1')
            >>> species = ibeis.const.Species.ZEB_PLAIN
            >>> daids = ibs.get_valid_aids(species=species)
            >>> qaids = ibs.get_valid_aids(species=species)
            >>> qreq_ = ibs.new_query_request(qaids, daids)
            >>> with_query = True
            >>> cfgstr = qreq_.get_cfgstr(with_query)
            >>> result = ('cfgstr = %s' % (str(cfgstr),))
            >>> print(result)
        """
        cfgstr_list = []
        if with_query:
            cfgstr_list.append(qreq_.get_query_hashid())
        if with_data:
            cfgstr_list.append(qreq_.get_data_hashid())
        if with_pipe:
            cfgstr_list.append(qreq_.get_pipe_cfgstr())
        cfgstr = ''.join(cfgstr_list)
        return cfgstr

    def get_full_cfgstr(qreq_):
        """ main cfgstring used to identify the 'querytype'
        FIXME: name
        params + data + query
        """
        full_cfgstr = qreq_.get_cfgstr(with_query=True)
        return full_cfgstr

    def get_qresdir(qreq_):
        return qreq_.qresdir

    # --- Lazy Loading ---

    @profile
    def lazy_preload(qreq_, verbose=True):
        """
        feature weights and normalizers should be loaded before vsone queries
        are issued. They do not depened only on qparams

        Load non-query specific normalizers / weights
        """
        if verbose:
            print('[qreq] lazy preloading')
        qreq_.ensure_features(verbose=verbose)
        if qreq_.qparams.fg_on is True:
            qreq_.ensure_featweights(verbose=verbose)
        if qreq_.qparams.score_normalization is True:
            qreq_.load_score_normalizer(verbose=verbose)
        if qreq_.qparams.use_external_distinctiveness:
            qreq_.load_distinctiveness_normalizer(verbose=verbose)

    @profile
    def lazy_load(qreq_, verbose=True):
        """
        Performs preloading of all data needed for a batch of queries
        """
        print('[qreq] lazy loading')
        #with ut.Indenter('[qreq.lazy_load]'):
        qreq_.hasloaded = True
        #qreq_.ibs = ibs  # HACK
        qreq_.lazy_preload(verbose=verbose)
        if qreq_.qparams.pipeline_root in ['vsone', 'vsmany']:
            qreq_.load_indexer(verbose=verbose)
        #if qreq_.qparams.pipeline_root in ['smk']:
        #    # TODO load vocabulary indexer

    # load query data structures
    @profile
    def ensure_chips(qreq_, verbose=True, extra_tries=1):
        r""" ensure chips are computed (used in expt, not used in pipeline)

        Args:
            verbose (bool):  verbosity flag(default = True)
            extra_tries (int): (default = 0)

        CommandLine:
            python -m ibeis.model.hots.query_request --test-ensure_chips

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.model.hots.query_request import *  # NOQA
            >>> import ibeis
            >>> ibs = ibeis.opendb(defaultdb='testdb1')
            >>> daids = ibs.get_valid_aids()[0:3]
            >>> qaids = ibs.get_valid_aids()[0:6]
            >>> qreq_ = ibs.new_query_request(qaids, daids)
            >>> verbose = True
            >>> extra_tries = 1
            >>> ut.remove_file_list(ibs.get_annot_chip_fpath(qaids, config2_=qreq_.get_external_query_config2()))
            >>> ut.remove_file_list(ibs.get_annot_chip_fpath(daids, config2_=qreq_.get_external_data_config2()))
            >>> result = qreq_.ensure_chips(verbose, extra_tries)
            >>> print(result)
        """
        if verbose:
            print('[qreq] ensure_chips')
        external_qaids = qreq_.get_external_qaids()
        external_daids = qreq_.get_external_daids()
        #np.union1d(external_qaids, external_daids)
        # TODO check if configs are the same
        externgetkw = dict(
            ensure=True,
            check_external_storage=True,
            extra_tries=extra_tries
        )
        q_chip_fpath = qreq_.ibs.get_annot_chip_fpath(  # NOQA
            external_qaids,
            config2_=qreq_.get_external_query_config2(), **externgetkw)
        d_chip_fpath = qreq_.ibs.get_annot_chip_fpath(  # NOQA
            external_daids,
            config2_=qreq_.get_external_data_config2(), **externgetkw)

    @profile
    def ensure_features(qreq_, verbose=True):
        r""" ensure features are computed
        Args:
            verbose (bool):  verbosity flag(default = True)

        CommandLine:
            python -m ibeis.model.hots.query_request --test-ensure_features

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.model.hots.query_request import *  # NOQA
            >>> import ibeis
            >>> ibs = ibeis.opendb(defaultdb='testdb1')
            >>> daids = ibs.get_valid_aids()[0:3]
            >>> qaids = ibs.get_valid_aids()[0:6]
            >>> qreq_ = ibs.new_query_request(qaids, daids)
            >>> ibs.delete_annot_feats(qaids,  config2_=qreq_.get_external_query_config2())  # Remove the chips
            >>> ut.remove_file_list(ibs.get_annot_chip_fpath(qaids, config2_=qreq_.get_external_query_config2()))
            >>> verbose = True
            >>> result = qreq_.ensure_features(verbose)
            >>> print(result)
        """
        #with ut.EmbedOnException():
        if verbose:
            print('[qreq] ensure_features')
        external_qaids = qreq_.get_external_qaids()
        external_daids = qreq_.get_external_daids()
        qfids = qreq_.ibs.get_annot_feat_rowids(  # NOQA
            external_qaids, ensure=True,
            config2_=qreq_.get_external_query_config2())
        dfids = qreq_.ibs.get_annot_feat_rowids(  # NOQA
            external_daids, ensure=True,
            config2_=qreq_.get_external_data_config2())
        if ut.DEBUG2:
            qkpts = qreq_.ibs.get_annot_kpts(
                external_qaids, ensure=False,
                config2_=qreq_.get_external_query_config2())
            dkpts = qreq_.ibs.get_annot_kpts(  # NOQA
                external_daids, ensure=False,
                config2_=qreq_.get_external_data_config2())
            #if verbose:
            try:
                assert len(qkpts) > 0, 'no query keypoint'
                assert qkpts[0].size > 0, (
                    'Query keypoints are corrupted! qkpts=%r' % (qkpts,))
            except Exception:
                print('qkpts = %r' % (qkpts,))
                raise

    @profile
    def ensure_featweights(qreq_, verbose=True):
        """ ensure feature weights are computed """
        #with ut.EmbedOnException():
        if verbose:
            print('[qreq] ensure_featweights')
        #internal_qaids = qreq_.get_internal_qaids()
        #internal_daids = qreq_.get_internal_daids()
        #qreq_.ibs.get_annot_fgweights(internal_qaids, ensure=True, config2_=qreq_.qparams)
        #qreq_.ibs.get_annot_fgweights(internal_daids, ensure=True, config2_=qreq_.qparams)
        external_qaids = qreq_.get_external_qaids()
        external_daids = qreq_.get_external_daids()
        qfw_rowids = qreq_.ibs.get_annot_featweight_rowids(  # NOQA
            external_qaids, ensure=True,
            config2_=qreq_.get_external_query_config2())
        dfw_rowids = qreq_.ibs.get_annot_featweight_rowids(  # NOQA
            external_daids, ensure=True,
            config2_=qreq_.get_external_data_config2())
        if ut.DEBUG2:
            qfeatweights = qreq_.ibs.get_annot_fgweights(
                external_qaids, ensure=True,
                config2_=qreq_.get_external_query_config2())
            dfeatweights = qreq_.ibs.get_annot_fgweights(  # NOQA
                external_daids, ensure=True,
                config2_=qreq_.get_external_data_config2())
            #if verbose:
            try:
                assert len(qfeatweights) > 0, 'no query featweights'
                assert qfeatweights[0].size > 0, (
                    'Query featweights are corrupted! qfeatweights=%r' %
                    (qfeatweights,))
            except Exception:
                print('qfeatweights = %r' % (qfeatweights,))
                raise
            #print('Featweight hash')
            #print(qkpts)
            #print(dkpts)
            #print(ut.hashstr27(str(qfeatweights)))
            #print(ut.hashstr27(str(dfeatweights)))

    @profile
    def load_indexer(qreq_, verbose=True, force=False):
        if not force and qreq_.indexer is not None:
            return False
        else:
            index_method = qreq_.qparams.index_method
            if index_method == 'single':
                # TODO: SYSTEM updatable indexer
                if ut.VERYVERBOSE or verbose:
                    print('[qreq] loading single indexer normalizer')
                indexer = neighbor_index.request_ibeis_nnindexer(
                    qreq_, verbose=verbose, **qreq_._indexer_request_params)
            elif index_method == 'multi':
                if ut.VERYVERBOSE or verbose:
                    print('[qreq] loading multi indexer normalizer')
                indexer = multi_index.request_ibeis_mindexer(
                    qreq_, verbose=verbose)
            else:
                raise AssertionError('uknown index_method=%r' % (index_method,))
            qreq_.indexer = indexer
            return True

    @profile
    def load_score_normalizer(qreq_, verbose=True):
        if qreq_.normalizer is not None:
            return False
        if verbose:
            print('[qreq] loading score normalizer')
        # TODO: SYSTEM updatable normalizer
        normalizer = score_normalization.request_ibeis_normalizer(
            qreq_, verbose=verbose)
        qreq_.normalizer = normalizer

    @profile
    def load_distinctiveness_normalizer(qreq_, verbose=True):
        """
        Example:
            >>> from ibeis.model.hots import distinctiveness_normalizer
            >>> verbose = True
        """
        if qreq_.dstcnvs_normer is not None:
            return False
        if verbose:
            print('[qreq] loading external distinctiveness normalizer')
        # TODO: SYSTEM updatable dstcnvs_normer
        _ = distinctiveness_normalizer
        request_dcvs_normer = _.request_ibeis_distinctiveness_normalizer
        dstcnvs_normer = request_dcvs_normer(qreq_, verbose=verbose)
        qreq_.dstcnvs_normer = dstcnvs_normer
        if verbose:
            print('qreq_.dstcnvs_normer = %r' % (qreq_.dstcnvs_normer,))

    def get_infostr(qreq_):
        infostr_list = []
        app = infostr_list.append
        qaid_internal = qreq_.get_internal_qaids()
        daid_internal = qreq_.get_internal_daids()
        qd_intersection = ut.intersect_ordered(daid_internal, qaid_internal)
        app(' * len(internal_daids) = %r' % len(daid_internal))
        app(' * len(internal_qaids) = %r' % len(qaid_internal))
        app(' * len(qd_intersection) = %r' % len(qd_intersection))
        infostr = '\n'.join(infostr_list)
        return infostr

    def assert_self(qreq_, ibs):
        print('[qreq] ASSERT SELF')
        qaids    = qreq_.get_external_qaids()
        qauuids  = qreq_.get_external_quuids()
        daids    = qreq_.get_external_daids()
        dauuids  = qreq_.get_external_duuids()
        _qaids   = qreq_.get_internal_qaids()
        _qauuids = qreq_.get_internal_quuids()
        _daids   = qreq_.get_internal_daids()
        _dauuids = qreq_.get_internal_duuids()
        def assert_uuids(aids, uuids):
            if ut.NOT_QUIET:
                print('[qreq_] asserting %s aids' % len(aids))
            assert len(aids) == len(uuids)
            assert all([u1 == u2 for u1, u2 in
                        zip(ibs.get_annot_semantic_uuids(aids), uuids)])
        assert_uuids(qaids, qauuids)
        assert_uuids(daids, dauuids)
        assert_uuids(_qaids, _qauuids)
        assert_uuids(_daids, _dauuids)

    def make_empty_query_results(qreq_):
        """ returns empty query results for each external qaid """
        external_qaids   = qreq_.get_external_qaids()
        external_qauuids = qreq_.get_external_quuids()
        daids  = qreq_.get_external_daids()
        cfgstr = qreq_.get_cfgstr()
        qres_list = [hots_query_result.QueryResult(qaid, qauuid, cfgstr, daids)
                     for qaid, qauuid in zip(external_qaids, external_qauuids)]
        for qres in qres_list:
            qres.aid2_score = {}
        return qres_list

    def make_empty_query_result(qreq_, qaid):
        """ makes an empty result for some query aid.  Hack used in case qres
        returned is None to get a single qres """
        qauuid = qreq_.ibs.get_annot_semantic_uuids(qaid)
        daids  = qreq_.get_external_daids()
        cfgstr = qreq_.get_cfgstr()
        qres = hots_query_result.QueryResult(qaid, qauuid, cfgstr, daids)
        qres.aid2_score = {}
        return qres

    def load_cached_qres(qreq_, qaid):
        """ convinience function for loading a query that has already been
        cached """
        shallow_qreq_ = qreq_.shallowcopy()
        shallow_qreq_.set_external_qaids([qaid])
        qres = shallow_qreq_.ibs._query_chips4(
            [qaid], qreq_.get_external_daids(), use_cache=True,
            use_bigcache=False, qreq_=shallow_qreq_)[qaid]
        return qres


def test_cfg_deepcopy():
    """
    TESTING FUNCTION

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.hots.query_request import *  # NOQA
        >>> result = test_cfg_deepcopy()
        >>> print(result)
    """
    import ibeis
    ibs = ibeis.opendb('testdb1')
    cfg1 = ibs.cfg.query_cfg
    cfg2 = cfg1.deepcopy()
    cfg3 = cfg2
    assert cfg1.get_cfgstr() == cfg2.get_cfgstr()
    assert cfg2.sv_cfg is not cfg1.sv_cfg
    assert cfg3.sv_cfg is cfg2.sv_cfg
    cfg2.update_query_cfg(sv_on=False)
    assert cfg1.get_cfgstr() != cfg2.get_cfgstr()
    assert cfg2.get_cfgstr() == cfg3.get_cfgstr()


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.model.hots.query_request --test-QueryParams
        utprof.sh -m ibeis.model.hots.query_request --test-QueryParams

        python -m ibeis.model.hots.query_request
        python -m ibeis.model.hots.query_request --allexamples
        python -m ibeis.model.hots.query_request --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    ut.doctest_funcs()
