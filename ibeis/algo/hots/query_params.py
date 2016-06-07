# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals
import collections
import utool as ut
from ibeis.algo.hots import hstypes
from ibeis.algo import Config
(print, rrr, profile) = ut.inject2(__name__, '[qreq]')


def testdata_queryparams():
    cfgdict = {'pipeline_root': 'asmk', 'sv_on': False, 'fg_on': True}
    qparams = QueryParams(cfgdict=cfgdict)
    return qparams


# This object will behave like a dictionary with ** capability
class QueryParams(collections.Mapping):
    def __init__(qparams, query_cfg=None, cfgdict=None):
        """
        Rename to pipeline params

        Structure to store static query pipeline parameters
        parses nested config structure into this flat one

        Args:
            query_cfg (QueryConfig): query_config
            cfgdict (dict or None): dictionary to update query_cfg with

        CommandLine:
            python -m ibeis.algo.hots.query_params --test-__init__

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.query_params import *  # NOQA
            >>> import ibeis
            >>> ibs = ibeis.opendb('testdb1')
            >>> query_cfg = ibs.cfg.query_cfg
            >>> #query_cfg.pipeline_root = 'asmk'
            >>> cfgdict = {'pipeline_root': 'asmk', 'sv_on': False, 'fg_on': True}
            >>> qparams = QueryParams(query_cfg, cfgdict)
            >>> assert qparams.pipeline_root == 'smk'
            >>> assert qparams.fg_on is True
            >>> result = qparams.query_cfgstr
            >>> print(')_\n'.join(result.split(')_')))

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.query_params import *  # NOQA
            >>> import ibeis
            >>> ibs = ibeis.opendb('testdb1')
            >>> query_cfg = ibs.cfg.query_cfg
            >>> #query_cfg.pipeline_root = 'asmk'
            >>> cfgdict = dict(rotation_invariance=True)
            >>> qparams = QueryParams(query_cfg, cfgdict)
            >>> ut.assert_eq(qparams.hesaff_params['rotation_invariance'], True)

            _smk_SMK(agg=True,t=0.0,a=3.0,idf)_
            VocabAssign(nAssign=10,a=1.2,s=None,eqw=T)_
            VocabTrain(nWords=8000,init=akmeans++,nIters=128,taids=all)_
            SV(OFF)_
            FEATWEIGHT(ON,uselabel,rf)_
            FEAT(hesaff+sift_)_
            CHIP(sz450)
        """
        # if given custom settings update the config and ensure feasibilty
        if query_cfg is None:
            query_cfg = Config.QueryConfig()
        if cfgdict is not None:
            query_cfg = query_cfg.deepcopy()
            query_cfg.update_query_cfg(**cfgdict)
        # Get flat item list
        param_list = Config.parse_config_items(query_cfg)
        # Assert that there are no config conflicts
        duplicate_keys = ut.find_duplicate_items(ut.get_list_column(param_list, 0))
        assert len(duplicate_keys) == 0, 'Configs have duplicate names: %r' % duplicate_keys
        # Set nexted config attributes as flat qparam properties
        for key, val in param_list:
            setattr(qparams, key, val)
        # Add params not implicitly represented in Config object
        pipeline_root              = query_cfg.pipeline_root
        qparams.chip_cfg_dict      = query_cfg._featweight_cfg._feat_cfg._chip_cfg.to_dict()
        qparams.flann_params       = query_cfg.flann_cfg.get_flann_params()
        qparams.hesaff_params      = query_cfg._featweight_cfg._feat_cfg.get_hesaff_params()
        qparams.pipeline_root      = pipeline_root
        qparams.vsmany             = pipeline_root == 'vsmany'
        qparams.vsone              = pipeline_root == 'vsone'
        # Add custom strings to the mix as well
        # TODO; Find better way to specify config strings
        # FIXME: probchip is not in here
        qparams.probchip_cfgstr   = query_cfg._featweight_cfg.get_cfgstr(
            use_feat=False, use_chip=False)
        qparams.featweight_cfgstr = query_cfg._featweight_cfg.get_cfgstr()
        qparams.chip_cfgstr       = query_cfg._featweight_cfg._feat_cfg._chip_cfg.get_cfgstr()
        qparams.feat_cfgstr       = query_cfg._featweight_cfg._feat_cfg.get_cfgstr()
        qparams.nn_cfgstr         = query_cfg.nn_cfg.get_cfgstr()
        qparams.nnweight_cfgstr   = query_cfg.nnweight_cfg.get_cfgstr()
        qparams.sv_cfgstr         = query_cfg.sv_cfg.get_cfgstr()
        qparams.flann_cfgstr      = query_cfg.flann_cfg.get_cfgstr()
        qparams.query_cfgstr      = query_cfg.get_cfgstr()
        qparams.vocabtrain_cfgstr = query_cfg.smk_cfg.vocabtrain_cfg.get_cfgstr()
        qparams.rrvsone_cfgstr    = query_cfg.rrvsone_cfg.get_cfgstr()

    def get_postsver_filtkey_list(qparams):
        """ HACK: gets columns of fsv post spatial verification.  This will
        eventually be incorporated into cmtup_old instead and will not be
        dependant on specifically where you are in the pipeline
        """
        filtkey_list = qparams.active_filter_list
        if qparams.sver_output_weighting:
            filtkey_list = filtkey_list[:] + [hstypes.FiltKeys.HOMOGERR]
        return filtkey_list

    # Dictionary like interface

    def get(qparams, key, *d):
        """ get a paramater value by string """
        ERROR_ON_DEFAULT = True
        if ERROR_ON_DEFAULT:
            return getattr(qparams, key)
        else:
            return getattr(qparams, key, *d)

    def __getitem__(qparams, key):
        return qparams.__dict__[key]

    def __iter__(qparams):
        return iter(qparams.__dict__)

    def __len__(qparams):
        return len(qparams.__dict__)

    def __getstate__(qparams):
        """
        Make QueryRequest pickleable

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.query_params import *  # NOQA
            >>> from six.moves import cPickle as pickle
            >>> qparams = testdata_queryparams()
            >>> qparams_dump = pickle.dumps(qparams)
            >>> qparams2 = pickle.loads(qparams_dump)
        """
        state_dict = qparams.__dict__.copy()
        return state_dict

    def copy(qparams):
        return qparams.__dict__.copy()

    def __setstate__(qparams, state_dict):
        qparams.__dict__.update(state_dict)


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.algo.hots.query_params
        python -m ibeis.algo.hots.query_params --allexamples
        python -m ibeis.algo.hots.query_params --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
