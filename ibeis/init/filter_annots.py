# -*- coding: utf-8 -*-
"""
TODO: sort annotations at the end of every step
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import operator
import utool as ut
import numpy as np
import functools
import six
from ibeis.control import controller_inject
(print, print_, printDBG, rrr, profile) = ut.inject(__name__, '[main_helpers]')

VERB_TESTDATA, VERYVERB_TESTDATA = ut.get_verbflag('testdata', 'td')

# TODO: Make these configurable
SEED1 = 0
SEED2 = 42

if ut.is_developer():
    USE_ACFG_CACHE = not ut.get_argflag(('--nocache-annot', '--nocache-aid',
                                         '--nocache')) and ut.USE_CACHE
else:
    USE_ACFG_CACHE = False

_tup = controller_inject.make_ibs_register_decorator(__name__)
CLASS_INJECT_KEY, register_ibs_method = _tup


@register_ibs_method
def filter_annots_general(ibs, aid_list, filter_kw={}, **kwargs):
    r"""
    Args:
        ibs (IBEISController):  ibeis controller object
        aid_list (list):  list of annotation rowids
        filter_kw (?):

    KWargs::
        has_none_annotmatch, any_match_annotmatch, has_all, is_known,
        any_match_annot, logic_annot, none_match_annotmatch,
        max_num_annotmatch, any_startswith_annot, has_any, require_quality,
        species, any_match, view_ext, has_any_annotmatch, view_pername,
        max_num_annot, min_timedelta, any_startswith, max_numfeat,
        any_startswith_annotmatch, been_adjusted, any_endswith_annot,
        require_viewpoint, logic, has_any_annot, min_num_annotmatch, min_num,
        min_num_annot, has_all_annot, has_none, min_pername,
        any_endswith_annotmatch, any_endswith, require_timestamp, none_match,
        contrib_contains, has_all_annotmatch, logic_annotmatch, min_numfeat,
        none_match_annot, view_ext1, view_ext2, max_num, has_none_annot,
        minqual, view

    CommandLine:
        python -m ibeis --tf filter_annots_general
        python -m ibeis --tf filter_annots_general --db PZ_Master1 --has_any=[needswork,correctable,mildviewpoint] --has_none=[viewpoint,photobomb,error:viewpoint,quality] --show

        python -m ibeis --tf filter_annots_general --db=GZ_Master1  \
                --max-numfeat=300 --show --minqual=junk --species=None
        python -m ibeis --tf filter_annots_general --db=lynx \
                --been_adjusted=True

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.init.filter_annots import *  # NOQA
        >>> import ibeis
        >>> filter_kw = ut.argparse_dict(get_default_annot_filter_form(), type_hint=ut.ddict(list, has_any=list, has_none=list, logic=str))
        >>> print('filter_kw = %s' % (ut.dict_str(filter_kw),))
        >>> ibs = ibeis.opendb(defaultdb='testdb1')
        >>> aid_list = ibs.get_valid_aids()
        >>> #filter_kw = dict(is_known=True, min_num=1, has_any='viewpoint')
        >>> #filter_kw = dict(is_known=True, min_num=1, any_match='.*error.*')
        >>> aid_list_ = filter_annots_general(ibs, aid_list, filter_kw)
        >>> print('len(aid_list_) = %r' % (len(aid_list_),))
        >>> all_tags = ut.flatten(ibs.get_annot_all_tags(aid_list_))
        >>> filtered_tag_hist = ut.dict_hist(all_tags)
        >>> ut.print_dict(filtered_tag_hist, key_order_metric='val')
        >>> ut.print_dict(ibs.get_annot_stats_dict(aid_list_), 'annot_stats')
        >>> ut.quit_if_noshow()
        >>> import ibeis.viz.interact
        >>> ibeis.viz.interact.interact_chip.interact_multichips(ibs, aid_list_)
        >>> ut.show_if_requested()
    """
    filter_kw.update(kwargs)
    aid_list_ = aid_list
    #filter_kw = ut.merge_dicts(get_default_annot_filter_form(), filter_kw)
    # TODO MERGE FILTERFLAGS BY TAGS AND FILTERFLAGS INDEPENDANT
    #aid_list_ = ibs.filterannots_by_tags(aid_list_, filter_kw)
    aid_list_ = ibs.filter_annots_independent(aid_list_, filter_kw)
    return aid_list_


def get_default_annot_filter_form():
    """
    CommandLine:
        python -m ibeis --tf get_default_annot_filter_form

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.init.filter_annots import *  # NOQA
        >>> filter_kw = get_default_annot_filter_form()
        >>> print(ut.dict_str(filter_kw, align=True))
        >>> print(', '.join(filter_kw.keys()))
    """
    from ibeis.expt import annotation_configs
    iden_defaults = annotation_configs.INDEPENDENT_DEFAULTS.copy()
    filter_kw = iden_defaults
    #tag_defaults = get_annot_tag_filterflags(
    #    None, None, {}, request_defaultkw=True)
    #filter_kw = ut.dict_union3(iden_defaults, tag_defaults, combine_op=None)
    return filter_kw


@register_ibs_method
@profile
def get_annot_tag_filterflags(ibs, aid_list, filter_kw,
                              request_defaultkw=False):
    """
    Filters annotations by tags including those that is belongs to in a pair
    """
    from ibeis import tag_funcs

    # Build Filters
    filter_keys = ut.get_func_kwargs(tag_funcs.filterflags_general_tags)

    annotmatch_filterkw = {}
    annot_filterkw = {}
    both_filterkw = {}

    kwreg = ut.KWReg(enabled=request_defaultkw)

    for key in filter_keys:
        annotmatch_filterkw[key] = filter_kw.get(*kwreg(key + '_annotmatch', None))
        annot_filterkw[key]      = filter_kw.get(*kwreg(key + '_annot', None))
        both_filterkw[key]       = filter_kw.get(*kwreg(key, None))

    if request_defaultkw:
        return kwreg.defaultkw

    # Grab Data
    need_annot_tags = any([var is not None for var in annot_filterkw.values()])
    need_annotmatch_tags =  any([
        var is not None for var in annotmatch_filterkw.values()])
    need_both_tags =  any([var is not None for var in both_filterkw.values()])

    if need_annot_tags or need_both_tags:
        annot_tags_list = ibs.get_annot_case_tags(aid_list)

    if need_annotmatch_tags or need_both_tags:
        annotmatch_tags_list = ibs.get_annot_annotmatch_tags(aid_list)

    if need_both_tags:
        both_tags_list = list(map(ut.unique_keep_order,
                                  map(ut.flatten, zip(annot_tags_list,
                                                      annotmatch_tags_list))))

    # Filter Data
    flags = np.ones(len(aid_list), dtype=np.bool)
    if need_annot_tags:
        flags_ = tag_funcs.filterflags_general_tags(
            annot_tags_list, **annot_filterkw)
        np.logical_and(flags_, flags, out=flags)

    if need_annotmatch_tags:
        flags_ = tag_funcs.filterflags_general_tags(
            annotmatch_tags_list, **annotmatch_filterkw)
        np.logical_and(flags_, flags, out=flags)

    if need_both_tags:
        flags_ = tag_funcs.filterflags_general_tags(
            both_tags_list, **both_filterkw)
        np.logical_and(flags_, flags, out=flags)
    return flags


@register_ibs_method
def filterannots_by_tags(ibs, aid_list, filter_kw):
    r"""
    Args:
        ibs (IBEISController):  ibeis controller object
        aid_list (list):  list of annotation rowids

    CommandLine:
        python -m ibeis --tf filterannots_by_tags
        utprof.py -m ibeis --tf filterannots_by_tags

    SeeAlso:
        filter_annotmatch_by_tags

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.init.filter_annots import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb(defaultdb='PZ_Master1')
        >>> aid_list = ibs.get_valid_aids()
        >>> has_any = ut.get_argval('--tags', type_=list,
        >>>                         default=['SceneryMatch', 'Photobomb'])
        >>> min_num = ut.get_argval('--min_num', type_=int, default=1)
        >>> filter_kw = dict(has_any=has_any, min_num=1)
        >>> aid_list_ = filterannots_by_tags(ibs, aid_list, filter_kw)
        >>> print('aid_list_ = %r' % (aid_list_,))
        >>> ut.quit_if_noshow()
        >>> pass
        >>> # TODO: show special annot group in GUI
    """
    flags = get_annot_tag_filterflags(ibs, aid_list, filter_kw)
    aid_list_ = ut.list_compress(aid_list, flags)
    return aid_list_


def get_acfg_cacheinfo(ibs, aidcfg):
    from ibeis.expt import cfghelpers
    # Make loading aids a big faster for experiments
    if ut.is_developer():
        import ibeis
        from os.path import dirname, join
        repodir = dirname(ut.get_module_dir(ibeis))
        acfg_cachedir = join(repodir, 'ACFG_CACHE')
    else:
        acfg_cachedir = './localdata/ACFG_CACHE'
        ut.ensuredir(acfg_cachedir)
    acfg_cachename = 'ACFG_CACHE'

    RESPECT_INTERNAL_CFGS = False
    if RESPECT_INTERNAL_CFGS:
        aid_cachestr = ibs.get_dbname() + '_' + ut.hashstr27(ut.to_json(aidcfg))
    else:
        import copy
        relevant_aidcfg = copy.deepcopy(aidcfg)
        ut.delete_dict_keys(relevant_aidcfg['qcfg'],
                            cfghelpers.INTERNAL_CFGKEYS)
        ut.delete_dict_keys(relevant_aidcfg['dcfg'],
                            cfghelpers.INTERNAL_CFGKEYS)
        aid_cachestr = (
            ibs.get_dbname() + '_' + ut.hashstr27(ut.to_json(relevant_aidcfg)))
    acfg_cacheinfo = acfg_cachedir, acfg_cachename, aid_cachestr
    return acfg_cacheinfo


def expand_single_acfg(ibs, aidcfg, verbose=VERB_TESTDATA):
    from ibeis.expt import annotation_configs
    if verbose:
        print('+=== EXPAND_SINGLE_ACFG ===')
        print(' * acfg = %s' %
              (ut.dict_str(annotation_configs.compress_aidcfg(aidcfg),
                           align=True),))
        print('+---------------------')
    #avail_aids = expand_to_default_aids(ibs, aidcfg)
    avail_aids = ibs._get_all_aids()
    avail_aids = filter_annots_independent(ibs, avail_aids, aidcfg)
    avail_aids = sample_annots(ibs, avail_aids, aidcfg)
    avail_aids = subindex_annots(ibs, avail_aids, aidcfg)
    aids = avail_aids
    if verbose:
        print('L___ EXPAND_SINGLE_ACFG ___')
    return aids


def expand_acfgs_consistently(ibs, acfg_combo, use_cache=None):
    """
    CommandLine:
        python -m ibeis --tf parse_acfg_combo_list  \
                -a varysize
        ibeis --tf get_annotcfg_list --db PZ_Master1 -a varysize
        #ibeis --tf get_annotcfg_list --db lynx -a default:hack_encounter=True
        ibeis --tf get_annotcfg_list --db PZ_Master1 -a varysize:qsize=None
        ibeis --tf get_annotcfg_list --db PZ_Master0 --nofilter-dups  -a varysize
        ibeis --tf get_annotcfg_list --db PZ_MTEST -a varysize --nofilter-dups
        ibeis --tf get_annotcfg_list --db PZ_Master0 --verbtd \
                --nofilter-dups -a varysize
        ibeis --tf get_annotcfg_list --db PZ_Master1 -a viewpoint_compare \
                --verbtd --nofilter-dups
        ibeis --tf get_annotcfg_list -a timectrl --db GZ_Master1 --verbtd \
                --nofilter-dups

    """
    from ibeis.expt import annotation_configs
    # Edit configs so the sample sizes are consistent
    # FIXME: requiers that smallest configs are specified first

    def tmpmin(a, b):
        if a is None:
            return b
        elif b is None:
            return a
        return min(a, b)
    expanded_aids_list = []

    # Keep track of seen samples
    min_qsize = None
    min_dsize = None

    # HACK: Find out the params being varied and disallow those from being
    # prefiltered due to the lack of heirarchical filters
    nonvaried_dict, varied_acfg_list = annotation_configs.partition_acfg_list(
        acfg_combo)
    hack_exclude_keys = list(set(ut.flatten(
        [list(ut.merge_dicts(*acfg.values()).keys())
         for acfg in varied_acfg_list])))

    for combox, acfg in enumerate(acfg_combo):
        qcfg = acfg['qcfg']
        dcfg = acfg['dcfg']

        # In some cases we may want to clamp these, but others we do not
        if qcfg['force_const_size']:
            qcfg['_orig_sample_size'] = qcfg['sample_size']
            qcfg['sample_size'] = tmpmin(qcfg['sample_size'] , min_qsize)

        if dcfg['force_const_size']:
            dcfg['_orig_sample_size'] = dcfg['sample_size']
            dcfg['sample_size'] = tmpmin(dcfg['sample_size'] , min_dsize)

        # Expand modified acfgdict
        with ut.Indenter('[%d] ' % (combox,)):
            expanded_aids = expand_acfgs(ibs, acfg, use_cache=use_cache,
                                         hack_exclude_keys=hack_exclude_keys)

            if dcfg.get('hack_extra', None):
                # SUCH HACK to get a larger database
                assert False
                _aidcfg = annotation_configs.default['dcfg']
                _aidcfg['sample_per_name'] = 1
                _aidcfg['sample_size'] = 500
                _aidcfg['min_pername'] = 1
                _aidcfg['require_viewpoint'] = True
                _aidcfg['exclude_reference'] = True
                _aidcfg['view'] = 'right'
                prefix = 'hack'
                qaids = expanded_aids[0]
                daids = expanded_aids[1]

                _extra_aids =  ibs.get_valid_aids()
                _extra_aids = ibs.remove_groundtrue_aids(
                    _extra_aids, (qaids + daids))
                _extra_aids = filter_annots_independent(
                    ibs, _extra_aids, _aidcfg, prefix)
                _extra_aids = sample_annots(
                    ibs, _extra_aids, _aidcfg, prefix)
                daids = sorted(daids + _extra_aids)
                expanded_aids = (qaids, daids)

            qsize = len(expanded_aids[0])
            dsize = len(expanded_aids[1])

            # <hack for float that should not interfere with other hacks
            if qcfg['sample_size'] != qsize:
                qcfg['_orig_sample_size'] = qcfg['sample_size']
            if dcfg['sample_size'] != dsize:
                dcfg['_orig_sample_size'] = dcfg['sample_size']
            # /-->

            if min_qsize is None:
                qcfg['sample_size'] = qsize
            if min_dsize is None:  # UNSURE
                dcfg['sample_size'] = dsize

            if qcfg['sample_size'] != qsize:
                qcfg['_true_sample_size'] = qsize
            if dcfg['sample_size'] != dsize:
                dcfg['_true_sample_size'] = dsize

            if qcfg['force_const_size']:
                min_qsize = tmpmin(min_qsize, qsize)
            if dcfg['force_const_size']:  # UNSURE
                min_dsize = tmpmin(min_dsize, dsize)

            # so hacky
            # this has to be after sample_size assignment, otherwise the filtering
            # is unstable Remove queries that have labeling errors in them.
            # TODO: fix errors AND remove labels
            #REMOVE_LABEL_ERRORS = ut.is_developer() or ut.get_argflag('--noerrors')
            REMOVE_LABEL_ERRORS = True
            #ut.is_developer() or ut.get_argflag('--noerrors')
            if REMOVE_LABEL_ERRORS:
                qaids_, daids_ = expanded_aids

                partitioned_sets = ibs.partition_annots_into_corresponding_groups(
                    qaids_, daids_)
                tup = partitioned_sets
                query_group, data_group, unknown_group, distract_group = tup

                unknown_flags  = ibs.unflat_map(
                    ibs.get_annot_tag_filterflags, unknown_group,
                    filter_kw=dict(none_match=['.*error.*']))
                #data_flags  = ibs.unflat_map(
                #    ibs.get_annot_tag_filterflags, data_group,
                #    filter_kw=dict(none_match=['.*error.*']))
                query_flags = ibs.unflat_map(
                    ibs.get_annot_tag_filterflags, query_group,
                    filter_kw=dict(none_match=['.*error.*']))

                query_noterror_flags = list(map(all, ut.list_zipflatten(
                    query_flags,
                    #data_flags,
                )))
                unknown_noterror_flags = list(map(all, unknown_flags))

                filtered_queries = ut.flatten(
                    ut.list_compress(query_group, query_noterror_flags))
                filtered_unknown = ut.flatten(
                    ut.list_compress(unknown_group, unknown_noterror_flags))

                filtered_qaids_ = sorted(filtered_queries + filtered_unknown)

                expanded_aids = (filtered_qaids_, daids_)

        #ibs.print_annotconfig_stats(*expanded_aids)
        expanded_aids_list.append(expanded_aids)

    # Sample afterwords

    return list(zip(acfg_combo, expanded_aids_list))


@profile
def expand_acfgs(ibs, aidcfg, verbose=VERB_TESTDATA, use_cache=None,
                 hack_exclude_keys=None):
    """
    Expands an annot config dict into qaids and daids
    New version of this function based on a configuration dictionary built from
    command line argumetns

    FIXME:
        The database should be created first in most circumstances, then
        the queries should be filtered to meet the database restrictions?
        I'm not sure Sometimes you need to set the query aids constant, but
        sometimes you need to set the data aids constant. Seems to depend.

    OkNewIdea:
        3 filters:
            * Common sampling - takes care of things like min time delta,
            * species, quality viewpoint etc.
            * query sampling
            * database sampling
        Basic idea is
            * Sample large pool
            * Partition pool into query and database
        Requires:
            * base sampling params
            * partition1 params
            * partition2 params
            * inter partition params?

    TODO:
        This function very much needs the idea of filter chains

    CommandLine:
        python -m ibeis.dev -e print_acfg  -a timectrl:qsize=10,dsize=10  --db PZ_MTEST --veryverbtd --nocache-aid
        python -m ibeis.dev -e print_acfg  -a timectrl:qminqual=good,qsize=10,dsize=10  --db PZ_MTEST --veryverbtd --nocache-aid

        python -m ibeis.dev -e print_acfg  -a timectrl --db PZ_MTEST --verbtd --nocache-aid
        python -m ibeis.dev -e print_acfg  -a timectrl --db PZ_Master1 --verbtd --nocache-aid
        python -m ibeis.dev -e print_acfg  -a timequalctrl --db PZ_Master1 --verbtd --nocache-aid

        python -m ibeis.dev -e rank_cdf   -a controlled:qsize=10,dsize=10,dper_name=2 -t default --db PZ_MTEST
        python -m ibeis.dev -e rank_cdf   -a controlled:qsize=10,dsize=20,dper_name=2 -t default --db PZ_MTEST
        python -m ibeis.dev -e rank_cdf   -a controlled:qsize=10,dsize=30,dper_name=2 -t default --db PZ_MTEST
        python -m ibeis.dev -e print      -a controlled:qsize=10,dsize=10             -t default --db PZ_MTEST --verbtd --nocache-aid

        python -m ibeis.dev -e latexsum -t candinvar -a viewpoint_compare  --db NNP_Master3 --acfginfo
        utprof.py -m ibeis.dev -e print -t candk -a varysize  --db PZ_MTEST --acfginfo
        utprof.py -m ibeis.dev -e latexsum -t candk -a controlled  --db PZ_Master0 --acfginfo

        python -m ibeis --tf get_annotcfg_list:0 --db NNP_Master3 -a viewpoint_compare --nocache-aid --verbtd

        python -m ibeis --tf get_annotcfg_list  --db PZ_Master1 -a timectrl:qhas_any=\(needswork,correctable,mildviewpoint\),qhas_none=\(viewpoint,photobomb,error:viewpoint,quality\) ---acfginfo --veryverbtd  --veryverbtd
        python -m ibeis --tf draw_rank_cdf --db PZ_Master1 --show -t best -a timectrl:qhas_any=\(needswork,correctable,mildviewpoint\),qhas_none=\(viewpoint,photobomb,error:viewpoint,quality\) ---acfginfo --veryverbtd


    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.init.filter_annots import *  # NOQA
    """

    from ibeis.expt import annotation_configs
    import copy
    aidcfg = copy.deepcopy(aidcfg)

    # Check if this filter has been cached
    # TODO: keep a database state config that augments the cachestr

    if use_cache is None:
        use_cache = USE_ACFG_CACHE

    save_cache = True
    if use_cache or save_cache:
        acfg_cacheinfo = get_acfg_cacheinfo(ibs, aidcfg)
        acfg_cachedir, acfg_cachename, aid_cachestr = acfg_cacheinfo
    if use_cache:
        try:
            (qaid_list, daid_list) = ut.load_cache(
                acfg_cachedir, acfg_cachename, aid_cachestr)
        except IOError:
            pass
        else:
            return qaid_list, daid_list

    comp_acfg = annotation_configs.compress_aidcfg(aidcfg)

    if verbose:
        ut.colorprint('+=== EXPAND_ACFGS ===', 'yellow')
        print(' * acfg = %s' % (ut.dict_str(comp_acfg, align=True),))
        ut.colorprint('+---------------------', 'yellow')

    # Breakup into common, query, and database configs
    qcfg = aidcfg['qcfg']
    dcfg = aidcfg['dcfg']
    common_cfg = comp_acfg['common']

    # Extract the common independent filtering params
    idenfilt_cfg_default = annotation_configs.INDEPENDENT_DEFAULTS
    idenfilt_cfg_empty = {key: None for key in idenfilt_cfg_default.keys()}
    idenfilt_cfg_common = ut.update_existing(idenfilt_cfg_empty,
                                             common_cfg, copy=True)

    if hack_exclude_keys:
        for key in hack_exclude_keys:
            if key in idenfilt_cfg_common:
                idenfilt_cfg_common[key] = None

    # Find the q/d specific filtering flags that were already taken care of in
    # common filtering. Set them all to None, so we dont rerun that filter
    qpredone_iden_keys = ut.dict_isect(qcfg, idenfilt_cfg_common).keys()
    for key in qpredone_iden_keys:
        qcfg[key] = None

    dpredone_iden_keys = ut.dict_isect(dcfg, idenfilt_cfg_common).keys()
    for key in dpredone_iden_keys:
        dcfg[key] = None

    try:
        #if aidcfg['qcfg']['hack_encounter'] is True:
        #    return ibs.get_encounter_expanded_aids()
        # Hack: Make hierarchical filters to supersede this
        initial_aids = ibs._get_all_aids()

        verbflags  = dict(verbose=verbose)
        qfiltflags = dict(prefix='q', **verbflags)
        dfiltflags = dict(prefix='d', **verbflags)

        default_aids = initial_aids

        if True:
            global_filter_chain = [
                (filter_annots_independent, idenfilt_cfg_common),
                (filter_annots_intragroup, idenfilt_cfg_common),
            ]

            partition_chains = [
                [
                    (filter_annots_independent, qcfg),
                    (filter_annots_intragroup, qcfg),
                    (sample_annots, qcfg),
                ],
                [
                    (filter_annots_independent, dcfg),
                    (filter_annots_intragroup, dcfg),
                    #(sample_annots_wrt_ref, dcfg),
                ]
            ]

            # TODO: GENERALIZE GLOBAL FILTER CHAIN
            for filtfn, filtcfg in global_filter_chain:
                default_aids = filtfn(ibs, default_aids, filtcfg, prefix='',
                                      withpre=True, **verbflags)

            # TODO: GENERALIZE PARTITION FILTER
            default_qaids = default_daids = default_aids
            partition_avail_aids = [default_qaids, default_daids]
            partition_verbflags  = [qfiltflags, dfiltflags]

            # TODO: PARITION FILTER CHAINS
            for index in range(len(partition_chains)):
                filter_chain = partition_chains[index]
                avail_aids = partition_avail_aids[index]
                _verbflags = partition_verbflags[index]
                for filtfn, filtcfg in filter_chain:
                    avail_aids = filtfn(
                        ibs, avail_aids, filtcfg, **_verbflags)
                partition_avail_aids[index] = avail_aids

            # TODO: GENERALIZE PARITION REFERENCE SAMPLE?
            # HACK:
            assert len(partition_avail_aids) == 2
            avail_aids = partition_avail_aids[1]
            _verbflags = partition_verbflags[1]
            reference_aids = partition_avail_aids[0]
            avail_aids = sample_annots_wrt_ref(
                ibs, avail_aids, dcfg, reference_aids=reference_aids,
                **_verbflags)
            partition_avail_aids[1] = avail_aids

            # TODO: GENERALIZE SUBINDEX
            subindex_cfgs = [qcfg, dcfg]
            for index in range(len(partition_avail_aids)):
                avail_aids = partition_avail_aids[index]
                _verbflags = partition_verbflags[index]
                filtcfg = subindex_cfgs[index]
                avail_aids = subindex_annots(
                    ibs, avail_aids, filtcfg, **_verbflags)
                partition_avail_aids[index] = avail_aids
            avail_qaids, avail_daids = partition_avail_aids
        else:
            # Prefilter an initial pool of aids
            default_aids = filter_annots_independent(
                ibs, default_aids, idenfilt_cfg_common, prefix='',
                withpre=True, **verbflags)
            default_aids = filter_annots_intragroup(
                ibs, default_aids, idenfilt_cfg_common, prefix='',
                withpre=True, **verbflags)
            avail_daids = avail_qaids = default_aids

            # Sample set of query annotations
            avail_qaids = filter_annots_independent(
                ibs, avail_qaids, qcfg, **qfiltflags)
            avail_qaids = filter_annots_intragroup(
                ibs, avail_qaids, qcfg, **qfiltflags)
            avail_qaids = sample_annots(
                ibs, avail_qaids, qcfg, **qfiltflags)

            # Sample set of database annotations w.r.t query annots
            avail_daids = filter_annots_independent(
                ibs, avail_daids, dcfg, **dfiltflags)
            avail_daids = filter_annots_intragroup(
                ibs, avail_daids, dcfg, **dfiltflags)
            avail_daids = sample_annots_wrt_ref(
                ibs, avail_daids, dcfg, reference_aids=avail_qaids,
                **dfiltflags)

            # Subindex if requested (typically not done)
            avail_qaids = subindex_annots(
                ibs, avail_qaids, qcfg, **qfiltflags)
            avail_daids = subindex_annots(
                ibs, avail_daids, dcfg, **dfiltflags)

    except Exception as ex:
        print('PRINTING ERROR INFO')
        print(' * acfg = %s' % (ut.dict_str(comp_acfg, align=True),))
        ut.printex(ex, 'Error expanding acfgs')
        raise

    qaid_list = sorted(avail_qaids)
    daid_list = sorted(avail_daids)

    if verbose:
        ut.colorprint('+---------------------', 'yellow')
        ibs.print_annotconfig_stats(qaid_list, daid_list)
        ut.colorprint('L___ EXPAND_ACFGS ___', 'yellow')

    # Save filter to cache
    if save_cache:
        ut.ensuredir(acfg_cachedir)
        ut.save_cache(acfg_cachedir, acfg_cachename, aid_cachestr,
                      (qaid_list, daid_list))

    return qaid_list, daid_list


def expand_species(ibs, species, avail_aids=None):
    if species == 'primary':
        species = ibs.get_primary_database_species()
    if species is None and avail_aids is not None:
        species = ibs.get_dominant_species(avail_aids)
    return species


@profile
@register_ibs_method
def filter_annots_independent(ibs, avail_aids, aidcfg, prefix='',
                              verbose=VERB_TESTDATA, withpre=False):
    r""" Filtering that doesn't have to do with a reference set of aids

    TODO make filterflags version

    Args:
        ibs (IBEISController):  ibeis controller object
        avail_aids (list):
        aidcfg (dict):
        prefix (str): (default = '')
        verbose (bool):  verbosity flag(default = False)

    Returns:
        list: avail_aids

    CommandLine:
        python -m ibeis --tf filter_annots_independent --veryverbtd

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.init.filter_annots import *  # NOQA
        >>> import ibeis
        >>> from ibeis.expt import annotation_configs
        >>> ibs = ibeis.opendb(defaultdb='PZ_MTEST')
        >>> avail_aids = input_aids = ibs.get_valid_aids()
        >>> aidcfg = annotation_configs.default['dcfg']
        >>> aidcfg['require_timestamp'] = True
        >>> aidcfg['require_quality'] = False
        >>> aidcfg['is_known'] = True
        >>> prefix = ''
        >>> verbose = True
        >>> avail_aids = filter_annots_independent(ibs, avail_aids, aidcfg,
        >>>                                        prefix, verbose)
        >>> result = ('avail_aids = %s' % (str(avail_aids),))
        >>> print(result)

    Ignore:
        # Testing tag features
        python -m ibeis --tf draw_rank_cdf --db PZ_Master1 --show -t best -a timectrl:qhas_any=\(needswork,correctable,mildviewpoint\),qhas_none=\(viewpoint,photobomb,error:viewpoint,quality\) ---acfginfo --veryverbtd
    """
    from ibeis import ibsfuncs
    if aidcfg is None:
        if verbose:
            print('No annot filter returning')
        return avail_aids

    VerbosityContext = verbose_context_factory(
        'FILTER_INDEPENDENT', aidcfg, verbose)
    VerbosityContext.startfilter(withpre=withpre)

    if aidcfg['is_known'] is True:
        with VerbosityContext('is_known'):
            avail_aids = ibs.filter_aids_without_name(
                avail_aids, invert=not aidcfg['is_known'])
        avail_aids = sorted(avail_aids)

    if aidcfg['require_timestamp'] is True:
        with VerbosityContext('require_timestamp'):
            avail_aids = ibs.filter_aids_without_timestamps(avail_aids)
        avail_aids = sorted(avail_aids)

    metadata = ut.LazyDict(
        species=lambda: expand_species(ibs, aidcfg['species'], None))

    if aidcfg['species'] is not None:
        species = metadata['species']
        with VerbosityContext('species', species=species):
            avail_aids = ibs.filter_aids_to_species(avail_aids, species)
            avail_aids = sorted(avail_aids)

    if aidcfg.get('been_adjusted', None):
        # HACK to see if the annotation has been adjusted from the default
        # value set by dbio.ingest_database
        flag_list = ibs.get_annot_been_adjusted(avail_aids)
        with VerbosityContext('been_adjusted'):
            avail_aids = ut.list_compress(avail_aids, flag_list)

    if aidcfg.get('contrib_contains', None):
        contrib_contains = aidcfg['contrib_contains']
        gid_list = ibs.get_annot_gids(avail_aids)
        tag_list = ibs.get_image_contributor_tag(gid_list)
        flag_list = [contrib_contains in tag for tag in tag_list]
        with VerbosityContext('contrib_contains'):
            avail_aids = ut.list_compress(avail_aids, flag_list)

    if aidcfg['minqual'] is not None or aidcfg['require_quality']:
        minqual = 'junk' if aidcfg['minqual'] is None else aidcfg['minqual']
        with VerbosityContext('minqual', 'require_quality'):
            # Filter quality
            avail_aids = ibs.filter_aids_to_quality(
                avail_aids, minqual, unknown_ok=not aidcfg['require_quality'])
        avail_aids = sorted(avail_aids)

    if aidcfg['max_numfeat'] is not None or aidcfg['min_numfeat'] is not None:
        max_numfeat = aidcfg['max_numfeat']
        min_numfeat = aidcfg['min_numfeat']
        if max_numfeat is None:
            max_numfeat = np.inf
        if min_numfeat is None:
            min_numfeat = 0
        numfeat_list = np.array(ibs.get_annot_num_feats(avail_aids))
        flags_list = np.logical_and(
            numfeat_list >= min_numfeat,
            numfeat_list <= max_numfeat)
        with VerbosityContext('max_numfeat', 'min_numfeat'):
            avail_aids = ut.list_compress(avail_aids, flags_list)

    if aidcfg['view'] is not None or aidcfg['require_viewpoint']:
        # Resolve base viewpoint
        if aidcfg['view'] == 'primary':
            view = ibsfuncs.get_primary_species_viewpoint(metadata['species'])
        elif aidcfg['view'] == 'primary1':
            view = ibsfuncs.get_primary_species_viewpoint(metadata['species'], 1)
        else:
            view = aidcfg['view']
        view_ext1 = (aidcfg['view_ext']
                     if aidcfg['view_ext1'] is None else
                     aidcfg['view_ext1'])
        view_ext2 = (aidcfg['view_ext']
                     if aidcfg['view_ext2'] is None else
                     aidcfg['view_ext2'])
        valid_yaws = ibsfuncs.get_extended_viewpoints(
            view, num1=view_ext1, num2=view_ext2)
        unknown_ok = not aidcfg['require_viewpoint']
        with VerbosityContext('view', 'require_viewpoint', 'view_ext',
                              'view_ext1', 'view_ext2', valid_yaws=valid_yaws):
            avail_aids = ibs.filter_aids_to_viewpoint(
                avail_aids, valid_yaws, unknown_ok=unknown_ok)
        avail_aids = sorted(avail_aids)

    if aidcfg.get('exclude_view') is not None:
        raise NotImplementedError('view tag resolution of exclude_view')
        # Filter viewpoint
        # TODO need to resolve viewpoints
        exclude_view = aidcfg.get('exclude_view')
        with VerbosityContext('exclude_view', hack=True):
            avail_aids = ibs.remove_aids_of_viewpoint(
                avail_aids, exclude_view)

    # FILTER HACK
    # TODO: further integrate
    if aidcfg.get('has_any', None) or aidcfg.get('has_none', None):
        filterkw = ut.dict_subset(aidcfg, ['has_any', 'has_none'], None)
        flags = get_annot_tag_filterflags(ibs, avail_aids, filterkw)
        with VerbosityContext('has_any', 'has_none'):
            avail_aids = ut.list_compress(avail_aids, flags)
            #avail_aids = ibs.filter_aids_without_name(
            #    avail_aids, invert=not aidcfg['is_known'])
        avail_aids = sorted(avail_aids)

    avail_aids = sorted(avail_aids)

    VerbosityContext.endfilter()
    return avail_aids


@profile
def filter_annots_intragroup(ibs, avail_aids, aidcfg, prefix='',
                             verbose=VERB_TESTDATA, withpre=False):
    """ This filters annots using information about the relationships
    between the annotations in the ``avail_aids`` group. This function is not
    independent and a second consecutive call may yield new results.
    Thus, the order in which this filter is applied matters.

    Example:

        >>> aidcfg['min_timedelta'] = 60 * 60 * 24
        >>> aidcfg['min_pername'] = 3
    """
    from ibeis import ibsfuncs

    if aidcfg is None:
        if verbose:
            print('No annot filter returning')
        return avail_aids

    VerbosityContext = verbose_context_factory(
        'FILTER_INTRAGROUP', aidcfg, verbose)
    VerbosityContext.startfilter(withpre=withpre)

    metadata = ut.LazyDict(species=lambda: expand_species(ibs, aidcfg['species'], avail_aids))

    if aidcfg['same_encounter'] is not None:
        """
        ibeis --tf get_annotcfg_list -a default:qsame_encounter=True,been_adjusted=True,excluderef=True --db lynx --veryverbtd --nocache-aid
        """
        same_encounter = aidcfg['same_encounter']
        assert same_encounter is True
        eid_list = ibs.get_annot_primary_encounter(avail_aids)
        nid_list = ibs.get_annot_nids(avail_aids)
        multiprop2_aids = ut.hierarchical_group_items(avail_aids, [nid_list, eid_list])
        qaid_list = []
        # TODO: sampling using different enouncters
        for eid, nid2_aids in multiprop2_aids.iteritems():
            if len(nid2_aids) == 1:
                pass
            else:
                aids_list = list(nid2_aids.values())
                idx = ut.list_argmax(list(map(len, aids_list)))
                qaids = aids_list[idx]
                qaid_list.extend(qaids)
        with VerbosityContext('same_encounter'):
            avail_aids = qaid_list
        avail_aids = sorted(avail_aids)

    # FIXME: This is NOT an independent filter because it depends on pairwise
    # interactions
    if aidcfg['view_pername'] is not None:
        species = metadata['species']
        # This filter removes entire names.  The avaiable aids must be from
        # names with certain viewpoint frequency properties
        prop2_nid2_aids = ibs.group_annots_by_prop_and_name(
            avail_aids, ibs.get_annot_yaw_texts)

        countstr = aidcfg['view_pername']
        primary_viewpoint = ibsfuncs.get_primary_species_viewpoint(species)
        lhs_dict = {
            'primary': primary_viewpoint,
            'primary1': ibsfuncs.get_extended_viewpoints(
                primary_viewpoint, num1=1, num2=0, include_base=False)[0]
        }
        self = CountstrParser(lhs_dict, prop2_nid2_aids)
        nid2_flag = self.parse_countstr_expr(countstr)
        nid2_aids = ibs.group_annots_by_name_dict(avail_aids)
        valid_nids = [nid for nid, flag in nid2_flag.items() if flag]
        with VerbosityContext('view_pername', countstr=countstr):
            avail_aids = ut.flatten(ut.dict_take(nid2_aids, valid_nids))
        avail_aids = sorted(avail_aids)

    if aidcfg['min_timedelta'] is not None:
        min_timedelta = ut.ensure_timedelta(aidcfg['min_timedelta'])
        with VerbosityContext('min_timedelta', min_timedelta=min_timedelta):
            avail_aids = ibs.filter_annots_using_minimum_timedelta(
                avail_aids, min_timedelta)
        avail_aids = sorted(avail_aids)

    # Each aid must have at least this number of other groundtruth aids
    min_pername = aidcfg['min_pername']
    if min_pername is not None:
        grouped_aids_ = ibs.group_annots_by_name(avail_aids,
                                                 distinguish_unknowns=True)[0]
        with VerbosityContext('min_pername'):
            avail_aids = ut.flatten([
                aids for aids in grouped_aids_ if len(aids) >= min_pername])
        avail_aids = sorted(avail_aids)

    avail_aids = sorted(avail_aids)

    VerbosityContext.endfilter()
    return avail_aids


def get_reference_preference_order(ibs, gt_ref_grouped_aids,
                                   gt_avl_grouped_aids, prop_getter, cmp_func,
                                   aggfn, rng, verbose=VERB_TESTDATA):
    r"""
    Orders preference for sampling based on some metric
    """
    import vtool as vt
    grouped_reference_unixtimes = ibs.unflat_map(
        prop_getter, gt_ref_grouped_aids)
    grouped_available_gt_unixtimes = ibs.unflat_map(
        prop_getter, gt_avl_grouped_aids)

    grouped_reference_props = grouped_reference_unixtimes
    grouped_available_gt_props = grouped_available_gt_unixtimes

    # Order the available aids by some aggregation over some metric
    preference_scores = [
        aggfn(cmp_func(ref_prop, avl_prop[:, None]), axis=1)
        for ref_prop, avl_prop in
        zip(grouped_reference_props, grouped_available_gt_props)
    ]
    # Order by increasing timedelta (metric)
    gt_preference_idx_list = vt.argsort_groups(
        preference_scores, reverse=True, rng=rng)
    return gt_preference_idx_list


@profile
def sample_annots_wrt_ref(ibs, avail_aids, aidcfg, reference_aids, prefix='',
                          verbose=VERB_TESTDATA):
    """
    Sampling when a reference set is given
    """
    sample_per_name     = aidcfg['sample_per_name']
    sample_per_ref_name = aidcfg['sample_per_ref_name']
    exclude_reference   = aidcfg['exclude_reference']
    sample_size         = aidcfg['sample_size']
    offset              = aidcfg['sample_offset']
    sample_rule_ref     = aidcfg['sample_rule_ref']
    sample_rule         = aidcfg['sample_rule']

    avail_aids = sorted(avail_aids)
    reference_aids = sorted(reference_aids)

    VerbosityContext = verbose_context_factory(
        'SAMPLE (REF)', aidcfg, verbose)
    VerbosityContext.startfilter()

    if sample_per_ref_name is None:
        sample_per_ref_name = sample_per_name

    if offset is None:
        offset = 0

    if exclude_reference:
        assert reference_aids is not None, (
            'reference_aids=%r' % (reference_aids,))
        # VerbosityContext.report_annot_stats(ibs, avail_aids, prefix, '')
        # VerbosityContext.report_annot_stats(ibs, reference_aids, prefix, '')
        with VerbosityContext('exclude_reference',
                              num_ref_aids=len(reference_aids)):
            avail_aids = ut.setdiff_ordered(avail_aids, reference_aids)
            avail_aids = sorted(avail_aids)

    if not (sample_per_ref_name is not None or sample_size is not None):
        VerbosityContext.endfilter()
        return avail_aids

    if ut.is_float(sample_size):
        # A float sample size is a interpolations between full data and small
        # data
        sample_size = int(round((len(avail_aids) * sample_size +
                                 (1 - sample_size) * len(reference_aids))))
        if verbose:
            print('Expanding sample size to: %r' % (sample_size,))

    # This function first partitions aids into a one set that corresonds with
    # the reference set and another that does not correspond with the reference
    # set. The rest of the filters operate on these sets independently
    partitioned_sets = ibs.partition_annots_into_corresponding_groups(
        reference_aids, avail_aids)
    # items
    # [0], and [1] are corresponding lists of annot groups
    # [2], and [3] are non-corresonding annot groups
    (gt_ref_grouped_aids, gt_avl_grouped_aids,
     gf_ref_grouped_aids, gf_avl_grouped_aids) = partitioned_sets

    if sample_per_ref_name is not None:
        rng = np.random.RandomState(SEED2)
        if sample_rule_ref == 'maxtimedelta':
            # Maximize time delta between query and corresponding database
            # annotations
            cmp_func = ut.absdiff
            aggfn = np.mean
            prop_getter = ibs.get_annot_image_unixtimes_asfloat
            gt_preference_idx_list = get_reference_preference_order(
                ibs, gt_ref_grouped_aids, gt_avl_grouped_aids, prop_getter,
                cmp_func, aggfn, rng)
        elif sample_rule_ref == 'random':
            gt_preference_idx_list = [ut.random_indexes(len(aids), rng=rng)
                                      for aids in gt_avl_grouped_aids]
        else:
            raise ValueError('Unknown sample_rule_ref = %r' % (
                sample_rule_ref,))
        gt_sample_idxs_list = ut.get_list_column_slice(
            gt_preference_idx_list, offset, offset + sample_per_ref_name)
        gt_sample_aids = ut.list_ziptake(gt_avl_grouped_aids,
                                         gt_sample_idxs_list)
        gt_avl_grouped_aids = gt_sample_aids

        with VerbosityContext('sample_per_ref_name', 'sample_rule_ref',
                              'sample_offset',
                              sample_per_ref_name=sample_per_ref_name):
            avail_aids = (ut.flatten(gt_avl_grouped_aids) +
                          ut.flatten(gf_avl_grouped_aids))

    if sample_per_name is not None:
        # sample rule is always random for gf right now
        rng = np.random.RandomState(SEED2)
        if sample_rule == 'random':
            gf_preference_idx_list = [ut.random_indexes(len(aids), rng=rng)
                                      for aids in gf_avl_grouped_aids]
        else:
            raise ValueError('Unknown sample_rule=%r' % (sample_rule,))
        gf_sample_idxs_list = ut.get_list_column_slice(
            gf_preference_idx_list, offset, offset + sample_per_name)
        gf_sample_aids = ut.list_ziptake(gf_avl_grouped_aids,
                                         gf_sample_idxs_list)
        gf_avl_grouped_aids = gf_sample_aids

        with VerbosityContext('sample_per_name', 'sample_rule',
                              'sample_offset'):
            avail_aids = (ut.flatten(gt_avl_grouped_aids) +
                          ut.flatten(gf_avl_grouped_aids))

    gt_avl_aids = ut.flatten(gt_avl_grouped_aids)
    gf_avl_aids = ut.flatten(gf_avl_grouped_aids)

    if sample_size is not None:
        # Keep all correct matches to the reference set
        # We have the option of keeping ground false
        num_gt = len(gt_avl_aids)
        num_gf = len(gf_avl_aids)
        num_keep_gf = sample_size - num_gt
        num_remove_gf = num_gf - num_keep_gf
        if num_remove_gf < 0:
            # Too few ground false
            print(('Warning: Cannot meet sample_size=%r. available_%saids '
                   'will be undersized by at least %d')
                  % (sample_size, prefix, -num_remove_gf,))
        if num_keep_gf < 0:
            # Too many multitons; Can never remove a multiton
            print('Warning: Cannot meet sample_size=%r. available_%saids '
                  'will be oversized by at least %d'
                  % (sample_size, prefix, -num_keep_gf,))
        rng = np.random.RandomState(SEED2)
        gf_avl_aids = ut.random_sample(gf_avl_aids, num_keep_gf, rng=rng)

        # random ordering makes for bad hashes
        with VerbosityContext('sample_size', sample_size=sample_size,
                              num_remove_gf=num_remove_gf,
                              num_keep_gf=num_keep_gf):
            avail_aids = gt_avl_aids + gf_avl_aids

    avail_aids = sorted(gt_avl_aids + gf_avl_aids)

    VerbosityContext.endfilter()
    return avail_aids


@profile
def sample_annots(ibs, avail_aids, aidcfg, prefix='', verbose=VERB_TESTDATA):
    """
    Sampling preserves input sample structure and thust does not always return
    exact values

    CommandLine:
        python -m ibeis --tf sample_annots --veryverbtd

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.init.filter_annots import *  # NOQA
        >>> import ibeis
        >>> from ibeis.expt import annotation_configs
        >>> ibs = ibeis.opendb(defaultdb='PZ_MTEST')
        >>> avail_aids = input_aids = ibs.get_valid_aids()
        >>> aidcfg = annotation_configs.default['dcfg']
        >>> aidcfg['sample_per_name'] = 3
        >>> aidcfg['sample_size'] = 10
        >>> aidcfg['min_pername'] = 2
        >>> prefix = ''
        >>> verbose = True
        >>> avail_aids = filter_annots_independent(ibs, avail_aids, aidcfg,
        >>>                                        prefix, verbose)
        >>> avail_aids = sample_annots(ibs, avail_aids, aidcfg,
        >>>                            prefix, avail_aids)
        >>> result = ('avail_aids = %s' % (str(avail_aids),))
        >>> print(result)
    """
    import vtool as vt

    VerbosityContext = verbose_context_factory(
        'SAMPLE (NOREF)', aidcfg, verbose)
    VerbosityContext.startfilter()

    sample_rule     = aidcfg['sample_rule']
    sample_per_name = aidcfg['sample_per_name']
    sample_size     = aidcfg['sample_size']
    offset          = aidcfg['sample_offset']

    unflat_get_annot_unixtimes = functools.partial(
        ibs.unflat_map, ibs.get_annot_image_unixtimes_asfloat)

    if offset is None:
        offset = 0

    if sample_per_name is not None:
        # For the query we just choose a single annot per name
        # For the database we have to do something different
        grouped_aids = ibs.group_annots_by_name(avail_aids)[0]
        # Order based on some preference (like random)
        rng = np.random.RandomState(SEED1)
        # + --- Get nested sample indicies ---
        if sample_rule == 'random':
            preference_idxs_list = [
                ut.random_indexes(len(aids), rng=rng) for aids in grouped_aids]
        elif sample_rule == 'mintime':
            unixtime_list = unflat_get_annot_unixtimes(grouped_aids)
            preference_idxs_list = vt.argsort_groups(unixtime_list,
                                                     reverse=False, rng=rng)
        elif sample_rule == 'maxtime':
            unixtime_list = unflat_get_annot_unixtimes(grouped_aids)
            preference_idxs_list = vt.argsort_groups(unixtime_list,
                                                     reverse=True, rng=rng)
        else:
            raise ValueError('Unknown sample_rule=%r' % (sample_rule,))
        # L ___
        sample_idxs_list = ut.get_list_column_slice(
            preference_idxs_list, offset, offset + sample_per_name)
        sample_aids = ut.list_ziptake(grouped_aids, sample_idxs_list)

        with VerbosityContext('sample_per_name', 'sample_rule',
                              'sample_offset'):
            avail_aids = ut.flatten(sample_aids)
        avail_aids = sorted(avail_aids)

    if sample_size is not None:
        # BUG: Should sample annots while preserving name size
        if sample_size > avail_aids:
            print('Warning sample size too large')
        rng = np.random.RandomState(SEED2)

        # Randomly sample names rather than annotations this makes sampling a
        # knapsack problem. Use a random greedy solution
        grouped_aids = ibs.group_annots_by_name(avail_aids)[0]
        # knapsack items values and weights are are num annots per name
        knapsack_items = [(len(aids), len(aids), count)
                          for count, aids  in enumerate(grouped_aids)]
        ut.deterministic_shuffle(knapsack_items, rng=rng)
        total_value, items_subset = ut.knapsack_greedy(knapsack_items,
                                                       sample_size)
        group_idx_sample = ut.get_list_column(items_subset, 2)
        subgroup_aids = ut.list_take(grouped_aids, group_idx_sample)

        with VerbosityContext('sample_size'):
            avail_aids = ut.flatten(subgroup_aids)
            #avail_aids = ut.random_sample(avail_aids, sample_size, rng=rng)
        if total_value != sample_size:
            print('Sampling could not get exactly right sample size')
        avail_aids = sorted(avail_aids)

    VerbosityContext.endfilter()
    return avail_aids


@profile
def subindex_annots(ibs, avail_aids, aidcfg, reference_aids=None,
                           prefix='', verbose=VERB_TESTDATA):
    """
    Returns exact subindex of annotations
    """
    VerbosityContext = verbose_context_factory(
        'SUBINDEX', aidcfg, verbose)
    VerbosityContext.startfilter(withpre=False)

    if aidcfg['shuffle']:
        rand_idx = ut.random_indexes(len(avail_aids), seed=SEED2)
        with VerbosityContext('shuffle', SEED2=SEED2):
            avail_aids = ut.list_take(avail_aids, rand_idx)

    if aidcfg['index'] is not None:
        indicies = ensure_flatlistlike(aidcfg['index'])
        _indexed_aids = [avail_aids[ix]
                         for ix in indicies if ix < len(avail_aids)]
        with VerbosityContext('index', subset_size=len(_indexed_aids)):
            avail_aids = _indexed_aids

    # Always sort aids to preserve hashes? (Maybe sort the vuuids instead)
    avail_aids = sorted(avail_aids)

    VerbosityContext.endfilter(withpost=False)
    return avail_aids


def ensure_flatiterable(input_):
    if isinstance(input_, six.string_types):
        input_ = ut.fuzzy_int(input_)
    if isinstance(input_, int) or not ut.isiterable(input_):
        return [input_]
    elif isinstance(input_, (list, tuple)):
        #print(input_)
        if len(input_) > 0 and ut.isiterable(input_[0]):
            return ut.flatten(input_)
        return input_
    else:
        raise TypeError('cannot ensure %r input_=%r is iterable', (
            type(input_), input_))


def ensure_flatlistlike(input_):
    #if isinstance(input_, slice):
    #    pass
    iter_ = ensure_flatiterable(input_)
    return list(iter_)


@six.add_metaclass(ut.ReloadingMetaclass)
class CountstrParser(object):
    numop = '#'
    compare_op_map = {
        '<'  : operator.lt,
        '<=' : operator.le,
        '>'  : operator.gt,
        '>=' : operator.ge,
        '='  : operator.eq,
        '!=' : operator.ne,
    }

    def __init__(self, lhs_dict, prop2_nid2_aids):
        self.lhs_dict = lhs_dict
        self.prop2_nid2_aids = prop2_nid2_aids
        pass

    def parse_countstr_binop(self, part):
        import utool as ut
        import re
        # Parse binary comparison operation
        left, op, right = re.split(ut.regex_or(('[<>]=?', '=')), part)
        # Parse length operation. Get prop_left_nids, prop_left_values
        if left.startswith(self.numop):
            varname = left[len(self.numop):]
            # Parse varname
            prop = self.lhs_dict.get(varname, varname)
            # Apply length operator to each name with the prop
            prop_left_nids = self.prop2_nid2_aids.get(prop, {}).keys()
            valiter = self.prop2_nid2_aids.get(prop, {}).values()
            prop_left_values = np.array(list(map(len, valiter)))
        # Pares number
        if right:
            prop_right_value = int(right)
        # Execute comparison
        prop_binary_result = self.compare_op_map[op](
            prop_left_values, prop_right_value)
        prop_nid2_result = dict(zip(prop_left_nids, prop_binary_result))
        return prop_nid2_result

    def parse_countstr_expr(self, countstr):
        # Split over ands for now
        and_parts = countstr.split('&')
        prop_nid2_result_list = []
        for part in and_parts:
            prop_nid2_result = self.parse_countstr_binop(part)
            prop_nid2_result_list.append(prop_nid2_result)
        # change to dict_union when parsing ors
        import functools
        andcombine = functools.partial(
            ut.dict_isect_combine, combine_op=operator.and_)
        expr_nid2_result = reduce(andcombine, prop_nid2_result_list)
        return expr_nid2_result


def verbose_context_factory(filtertype, aidcfg, verbose):
    """ closure helper """
    class VerbosityContext():
        """
        very hacky way of printing info so we dont pollute the actual function
        too much
        """

        @staticmethod
        def report_annot_stats(ibs, aids, prefix, name_suffix, statskw={}):
            if verbose > 1:
                with ut.Indenter('[%s]  ' % (prefix.upper(),)):
                    # TODO: helpx on statskw
                    #statskw = dict(per_name_vpedge=None, per_name=None)
                    dict_name = prefix + 'aid_stats' + name_suffix
                    #hashid, per_name, per_qual, per_vp, per_name_vpedge,
                    #per_image, min_name_hourdist
                    ibs.print_annot_stats(aids, prefix=prefix, label=dict_name,
                                          **statskw)

        #def report_annotconfig_stats(ref_aids, aids):
        #    with ut.Indenter('  '):
        #        ibs.print_annotconfig_stats(reference_aids, avail_aids)

        @staticmethod
        def startfilter(withpre=True):
            if verbose:
                prefix = ut.get_var_from_stack('prefix', verbose=False)
                print('[%s] * [%s] %sAIDS' % (prefix.upper(), filtertype,
                                              prefix))
                if verbose > 1 and withpre:
                    ibs    = ut.get_var_from_stack('ibs', verbose=False)
                    aids   = ut.get_var_from_stack('avail_aids', verbose=False)
                    VerbosityContext.report_annot_stats(ibs, aids, prefix,
                                                        '_pre')

        @staticmethod
        def endfilter(withpost=True):
            if verbose:
                ibs    = ut.get_var_from_stack('ibs', verbose=False)
                aids   = ut.get_var_from_stack('avail_aids', verbose=False)
                prefix = ut.get_var_from_stack('prefix', verbose=False)
                hashid = ibs.get_annot_hashid_semantic_uuid(
                    aids, prefix=prefix.upper())
                if withpost:
                    if verbose > 1:
                        VerbosityContext.report_annot_stats(ibs, aids, prefix,
                                                            '_post')
                print('[%s] * HAHID: %s' % (prefix.upper(), hashid))
                print('[%s] * [%s]: len(avail_%saids) = %r\n' % (
                    prefix.upper(), filtertype, prefix, len(aids)))

        def __init__(self, *keys, **filterextra):
            self.prefix = ut.get_var_from_stack('prefix', verbose=False)
            if verbose:
                dictkw = dict(nl=False, explicit=True, nobraces=True)
                infostr = ''
                if len(keys) > 0:
                    subdict = ut.dict_subset(aidcfg, keys)
                    infostr += '' + ut.dict_str(subdict, **dictkw)
                print('[%s] * Filter by %s' % (
                    self.prefix.upper(), infostr.strip()))
                if verbose > 1 and len(filterextra) > 0:
                    infostr2 = ut.dict_str(filterextra, nl=False, explicit=False)
                    print('[%s]      %s' % (
                        self.prefix.upper(), infostr2))

        def __enter__(self):
            aids = ut.get_var_from_stack('avail_aids', verbose=False)
            self.num_before = len(aids)

        def __exit__(self, exc_type, exc_value, exc_traceback):
            if verbose:
                aids = ut.get_var_from_stack('avail_aids', verbose=False)
                num_after = len(aids)
                num_removed = self.num_before - num_after
                if num_removed > 0 or verbose > 1:
                    print('[%s]   ... removed %d annots. %d remain' %
                          (self.prefix.upper(), num_removed, num_after))
    return VerbosityContext


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.init.filter_annots
        python -m ibeis.init.filter_annots --allexamples
        python -m ibeis.init.filter_annots --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
