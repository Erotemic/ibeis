# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals
import utool as ut
import numpy as np
from six.moves import zip, map, filter, range  # NOQA
from functools import partial  # NOQA
from ibeis.control import controller_inject
print, rrr, profile = ut.inject2(__name__, '[annotmatch_funcs]')

# Create dectorator to inject functions in this module into the IBEISController
CLASS_INJECT_KEY, register_ibs_method = controller_inject.make_ibs_register_decorator(__name__)


@register_ibs_method
@profile
def get_annotmatch_rowids_from_aid1(ibs, aid1_list, eager=True, nInput=None):
    """
    TODO autogenerate

    Returns a list of the aids that were reviewed as candidate matches to the input aid

    aid_list = ibs.get_valid_aids()
    Args:
        ibs (IBEISController):  ibeis controller object
        aid1_list (list):
        eager (bool): (default = True)
        nInput (None): (default = None)

    Returns:
        list: annotmatch_rowid_list
    """
    from ibeis.control import _autogen_annotmatch_funcs
    colnames = (_autogen_annotmatch_funcs.ANNOTMATCH_ROWID,)
    # FIXME: col_rowid is not correct
    params_iter = zip(aid1_list)
    if True:
        # HACK IN INDEX
        ibs.db.connection.execute(
            '''
            CREATE INDEX IF NOT EXISTS aid1_to_am ON {ANNOTMATCH_TABLE} (annot_rowid1);
            '''.format(ANNOTMATCH_TABLE=ibs.const.ANNOTMATCH_TABLE,
                       annot_rowid1=_autogen_annotmatch_funcs.ANNOT_ROWID1)).fetchall()
    andwhere_colnames = [_autogen_annotmatch_funcs.ANNOT_ROWID1]
    annotmatch_rowid_list = ibs.db.get_where2(
        ibs.const.ANNOTMATCH_TABLE, colnames, params_iter, andwhere_colnames,
        eager=eager, nInput=nInput, unpack_scalars=False)
    annotmatch_rowid_list = list(map(sorted, annotmatch_rowid_list))
    return annotmatch_rowid_list


@register_ibs_method
@profile
def get_annotmatch_rowids_from_aid2(ibs, aid2_list, eager=True, nInput=None,
                                    force_method=None):
    """
    # This one is slow because aid2 is the second part of the index
    Returns a list of the aids that were reviewed as candidate matches to the input aid
    """
    from ibeis.control import _autogen_annotmatch_funcs
    if nInput is None:
        nInput = len(aid2_list)
    if True:
        # HACK IN INDEX
        ibs.db.connection.execute(
            '''
            CREATE INDEX IF NOT EXISTS aid2_to_am ON {ANNOTMATCH_TABLE} (annot_rowid2);
            '''.format(ANNOTMATCH_TABLE=ibs.const.ANNOTMATCH_TABLE,
                       annot_rowid2=_autogen_annotmatch_funcs.ANNOT_ROWID2)).fetchall()
    colnames = (_autogen_annotmatch_funcs.ANNOTMATCH_ROWID,)
    # FIXME: col_rowid is not correct
    params_iter = zip(aid2_list)
    andwhere_colnames = [_autogen_annotmatch_funcs.ANNOT_ROWID2]
    annotmatch_rowid_list = ibs.db.get_where2(
        ibs.const.ANNOTMATCH_TABLE, colnames, params_iter, andwhere_colnames,
        eager=eager, nInput=nInput, unpack_scalars=False)
    annotmatch_rowid_list = list(map(sorted, annotmatch_rowid_list))
    return annotmatch_rowid_list


@register_ibs_method
@profile
def get_annotmatch_rowids_from_aid(ibs, aid_list, eager=True, nInput=None,
                                   force_method=None):
    """
    Undirected version
    Returns a list of the aids that were reviewed as candidate matches to the input aid
    aid_list = ibs.get_valid_aids()

    CommandLine:
        python -m ibeis.annotmatch_funcs --exec-get_annotmatch_rowids_from_aid
        python -m ibeis.annotmatch_funcs --exec-get_annotmatch_rowids_from_aid:1 --show

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.annotmatch_funcs import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb(defaultdb='testdb1')
        >>> ut.exec_funckw(ibs.get_annotmatch_rowids_from_aid, globals())
        >>> aid_list = ibs.get_valid_aids()[0:4]
        >>> annotmatch_rowid_list = ibs.get_annotmatch_rowids_from_aid(aid_list,
        >>>                                                        eager, nInput)
        >>> result = ('annotmatch_rowid_list = %s' % (str(annotmatch_rowid_list),))
        >>> print(result)
    """
    #from ibeis.control import _autogen_annotmatch_funcs
    if nInput is None:
        nInput = len(aid_list)
    if nInput == 0:
        return []
    rowids1 = ibs.get_annotmatch_rowids_from_aid1(aid_list)
    rowids2 = ibs.get_annotmatch_rowids_from_aid2(aid_list)
    annotmatch_rowid_list = [ut.unique(ut.flatten(p))
                             for p in zip(rowids1, rowids2)]
    # Ensure funciton output is consistent
    annotmatch_rowid_list = list(map(sorted, annotmatch_rowid_list))
    return annotmatch_rowid_list


@register_ibs_method
@profile
def get_annotmatch_rowid_from_undirected_superkey(ibs, aids1, aids2):
    # The directed nature of this makes a few things difficult and may cause
    # odd behavior
    am_rowids = ibs.get_annotmatch_rowid_from_superkey(aids1, aids2)
    idxs = ut.where([r is None for r in am_rowids])
    # Check which ones are None
    aids1_ = ut.take(aids1, idxs)
    aids2_ = ut.take(aids2, idxs)
    am_rowids_ = ibs.get_annotmatch_rowid_from_superkey(aids2_, aids1_)
    # Use the other rowid if found
    for idx, rowid in zip(idxs, am_rowids_):
        am_rowids[idx] = rowid
    return am_rowids


@register_ibs_method
def get_annotmatch_rowids_in_cliques(ibs, aids_list):
    # Equivalent call:
    #ibs.get_annotmatch_rowids_between_groups(ibs, aids_list, aids_list)
    import itertools
    ams_list = [ibs.get_annotmatch_rowid_from_undirected_superkey(*zip(*itertools.combinations(aids, 2)))
                for aids in ut.ProgIter(aids_list, lbl='loading clique am rowids')]
    ams_list = [[] if ams is None else ut.filter_Nones(ams) for ams in ams_list]
    return ams_list


@register_ibs_method
def get_annotmatch_rowids_between_groups(ibs, aids1_list, aids2_list):
    ams_list = []
    lbl = 'loading between group am rowids'
    for aids1, aids2 in ut.ProgIter(list(zip(aids1_list, aids2_list)), lbl=lbl):
        if len(aids1) * len(aids2) > 5000:
            am_rowids1 = ut.flatten(ibs.get_annotmatch_rowids_from_aid(aids1))
            am_rowids2 = ut.flatten(ibs.get_annotmatch_rowids_from_aid(aids2))
            am_rowids1 = ut.filter_Nones(am_rowids1)
            am_rowids2 = ut.filter_Nones(am_rowids2)
            ams = ut.isect(am_rowids1, am_rowids2)
        else:
            edges = list(ut.product_nonsame(aids1, aids2))
            if len(edges) == 0:
                ams = []
            else:
                aids1_, aids2_ = ut.listT(edges)
                ams = ibs.get_annotmatch_rowid_from_undirected_superkey(aids1_, aids2_)
                if ams is None:
                    ams = []
                ams = ut.filter_Nones(ams)
        ams_list.append(ams)
    return ams_list


@register_ibs_method
def add_annotmatch_undirected(ibs, aids1, aids2):
    am_rowids = ibs.get_annotmatch_rowid_from_undirected_superkey(aids1, aids2)
    idxs = ut.where([r is None for r in am_rowids])
    # Check which ones are None
    aids1_ = ut.take(aids1, idxs)
    aids2_ = ut.take(aids2, idxs)
    # Create anything that is None
    am_rowids_ = ibs.add_annotmatch(aids2_, aids1_)
    # Use the other rowid if found
    for idx, rowid in zip(idxs, am_rowids_):
        am_rowids[idx] = rowid
    return am_rowids


@register_ibs_method
def get_annot_pair_timdelta(ibs, aid_list1, aid_list2):
    r"""
    Args:
        ibs (IBEISController):  ibeis controller object
        aid_list1 (int):  list of annotation ids
        aid_list2 (int):  list of annotation ids

    Returns:
        list: timedelta_list

    CommandLine:
        python -m ibeis.annotmatch_funcs --test-get_annot_pair_timdelta

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.annotmatch_funcs import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('PZ_MTEST')
        >>> aid_list = ibs.get_valid_aids(hasgt=True)
        >>> unixtimes = ibs.get_annot_image_unixtimes(aid_list)
        >>> aid_list = ut.compress(aid_list, np.array(unixtimes) != -1)
        >>> gt_aids_list = ibs.get_annot_groundtruth(aid_list, daid_list=aid_list)
        >>> aid_list1 = [aid for aid, gt_aids in zip(aid_list, gt_aids_list) if len(gt_aids) > 0][0:5]
        >>> aid_list2 = [gt_aids[0] for gt_aids in gt_aids_list if len(gt_aids) > 0][0:5]
        >>> timedelta_list = ibs.get_annot_pair_timdelta(aid_list1, aid_list2)
        >>> result = ut.repr2(timedelta_list, precision=2)
        >>> print(result)
        np.array([  7.57e+07,   7.57e+07,   2.41e+06,   1.98e+08,   9.69e+07])
    """
    unixtime_list1 = ibs.get_annot_image_unixtimes_asfloat(aid_list1)
    unixtime_list2 = ibs.get_annot_image_unixtimes_asfloat(aid_list2)
    timedelta_list = np.abs(unixtime_list1 - unixtime_list2)
    return timedelta_list


@register_ibs_method
def get_annot_has_reviewed_matching_aids(ibs, aid_list, eager=True, nInput=None):
    num_reviewed_list = ibs.get_annot_num_reviewed_matching_aids(aid_list)
    has_reviewed_list = [num_reviewed > 0 for num_reviewed in num_reviewed_list]
    return has_reviewed_list


@register_ibs_method
def get_annot_num_reviewed_matching_aids(ibs, aid1_list, eager=True, nInput=None):
    r"""
    Args:
        aid_list (int):  list of annotation ids
        eager (bool):
        nInput (None):

    Returns:
        list: num_annot_reviewed_list

    CommandLine:
        python -m ibeis.annotmatch_funcs --test-get_annot_num_reviewed_matching_aids

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.annotmatch_funcs import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb2')
        >>> aid1_list = ibs.get_valid_aids()
        >>> eager = True
        >>> nInput = None
        >>> num_annot_reviewed_list = get_annot_num_reviewed_matching_aids(ibs, aid_list, eager, nInput)
        >>> result = str(num_annot_reviewed_list)
        >>> print(result)
    """
    aids_list = ibs.get_annot_reviewed_matching_aids(aid1_list, eager=eager, nInput=nInput)
    num_annot_reviewed_list = list(map(len, aids_list))
    return num_annot_reviewed_list


@register_ibs_method
def get_annot_reviewed_matching_aids(ibs, aid_list, eager=True, nInput=None):
    """
    Returns a list of the aids that were reviewed as candidate matches to the input aid
    """
    ANNOT_ROWID1 = 'annot_rowid1'
    ANNOT_ROWID2 = 'annot_rowid2'
    params_iter = [(aid,) for aid in aid_list]
    colnames = (ANNOT_ROWID2,)
    andwhere_colnames = (ANNOT_ROWID1,)
    aids_list = ibs.db.get_where2(ibs.const.ANNOTMATCH_TABLE, colnames,
                                  params_iter,
                                  andwhere_colnames=andwhere_colnames,
                                  eager=eager, unpack_scalars=False,
                                  nInput=nInput)
    return aids_list


@register_ibs_method
def get_annot_pair_truth(ibs, aid1_list, aid2_list):
    """
    CAREFUL: uses annot match table for truth, so only works if reviews have happend
    """
    annotmatch_rowid_list = ibs.get_annotmatch_rowid_from_undirected_superkey(aid1_list, aid2_list)
    annotmatch_truth_list = ibs.get_annotmatch_truth(annotmatch_rowid_list)
    return annotmatch_truth_list


@register_ibs_method
def get_annot_pair_is_reviewed(ibs, aid1_list, aid2_list):
    r"""
    Args:
        aid1_list (list):
        aid2_list (list):

    Returns:
        list: annotmatch_reviewed_list

    CommandLine:
        python -m ibeis.annotmatch_funcs --test-get_annot_pair_is_reviewed

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.annotmatch_funcs import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb2')
        >>> aid_list = ibs.get_valid_aids()
        >>> pairs = list(ut.product(aid_list, aid_list))
        >>> aid1_list = ut.get_list_column(pairs, 0)
        >>> aid2_list = ut.get_list_column(pairs, 1)
        >>> annotmatch_reviewed_list = get_annot_pair_is_reviewed(ibs, aid1_list, aid2_list)
        >>> reviewed_pairs = ut.compress(pairs, annotmatch_reviewed_list)
        >>> result = len(reviewed_pairs)
        >>> print(result)
        104
    """
    am_rowids = ibs.get_annotmatch_rowid_from_undirected_superkey(aid1_list, aid2_list)
    return ibs.get_annotmatch_reviewed(am_rowids)


@register_ibs_method
def set_annot_pair_as_reviewed(ibs, aid1, aid2):
    """ denote that this match was reviewed and keep whatever status it is given """
    isunknown1, isunknown2 = ibs.is_aid_unknown([aid1, aid2])
    if isunknown1 or isunknown2:
        truth = ibs.const.TRUTH_UNKNOWN
    else:
        nid1, nid2 = ibs.get_annot_name_rowids((aid1, aid2))
        truth = ibs.const.TRUTH_MATCH if (nid1 == nid2) else ibs.const.TRUTH_NOT_MATCH

    # Ensure a row exists for this pair
    annotmatch_rowids = ibs.add_annotmatch_undirected([aid1], [aid2])

    # Old functionality, remove. Reviewing should not set truth
    confidence  = 0.5
    #ibs.add_or_update_annotmatch(aid1, aid2, truth, confidence)
    ibs.set_annotmatch_reviewed(annotmatch_rowids, [True])
    ibs.set_annotmatch_truth(annotmatch_rowids, [truth])
    ibs.set_annotmatch_confidence(annotmatch_rowids, [confidence])
    print('... set truth=%r' % (truth,))


@register_ibs_method
def set_annot_pair_as_positive_match(ibs, aid1, aid2, dryrun=False,
                                     on_nontrivial_merge=None, logger=None):
    """
    Safe way to perform links. Errors on invalid operations.

    TODO: ELEVATE THIS FUNCTION
    Change into make_task_set_annot_pair_as_positive_match and it returns what
    needs to be done.

    Need to test several cases:
        uknown, unknown
        knownA, knownA
        knownB, knownA
        unknown, knownA
        knownA, unknown

    Args:
        ibs (IBEISController):  ibeis controller object
        aid1 (int):  query annotation id
        aid2 (int):  matching annotation id

    CommandLine:
        python -m ibeis.annotmatch_funcs --test-set_annot_pair_as_positive_match

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.annotmatch_funcs import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> aid1, aid2 = ibs.get_valid_aids()[0:2]
        >>> dryrun = True
        >>> status = set_annot_pair_as_positive_match(ibs, aid1, aid2, dryrun)
        >>> print(status)
    """
    def _set_annot_name_rowids(aid_list, nid_list):
        if not ut.QUIET:
            print('... _set_annot_name_rowids(aids=%r, nids=%r)' % (aid_list, nid_list))
            print('... names = %r' % (ibs.get_name_texts(nid_list)))
        assert len(aid_list) == len(nid_list), 'list must correspond'
        if not dryrun:
            if logger is not None:
                log = logger.info
                previous_names = ibs.get_annot_names(aid_list)
                new_names = ibs.get_name_texts(nid_list)
                annot_uuids = ibs.get_annot_uuids(aid_list)
                annot_uuid_pair = ibs.get_annot_uuids((aid1, aid2))
                log((
                    'REVIEW_PAIR AS TRUE: (annot_uuid_pair=%r) '
                    'CHANGE NAME of %d (annot_uuids=%r) '
                    'WITH (previous_names=%r) to (new_names=%r)' ) % (
                        annot_uuid_pair, len(annot_uuids), annot_uuids,
                        previous_names, new_names))

            ibs.set_annot_name_rowids(aid_list, nid_list)
            ibs.set_annot_pair_as_reviewed(aid1, aid2)
        # Return the new annots in this name
        _aids_list = ibs.get_name_aids(nid_list)
        _combo_aids_list = [_aids + [aid] for _aids, aid, in zip(_aids_list, aid_list)]
        status = _combo_aids_list
        return status
    print('[marking_match] aid1 = %r, aid2 = %r' % (aid1, aid2))

    nid1, nid2 = ibs.get_annot_name_rowids([aid1, aid2])
    if nid1 == nid2:
        print('...images already matched')
        #truth = get_annot_pair_truth([aid1], [aid2])[0]
        #if truth != ibs.const.TRUTH_MATCH:
        status = None
        ibs.set_annot_pair_as_reviewed(aid1, aid2)
        if logger is not None:
            log = logger.info
            annot_uuid_pair = ibs.get_annot_uuids((aid1, aid2))
            log('REVIEW_PAIR AS TRUE: (annot_uuid_pair=%r) NO CHANGE' % annot_uuid_pair)
    else:
        isunknown1, isunknown2 = ibs.is_aid_unknown([aid1, aid2])
        if isunknown1 and isunknown2:
            print('...match unknown1 to unknown2 into 1 new name')
            next_nids = ibs.make_next_nids(num=1)
            status =  _set_annot_name_rowids([aid1, aid2], next_nids * 2)
        elif not isunknown1 and not isunknown2:
            print('...merge known1 into known2')
            aid1_and_groundtruth = ibs.get_annot_groundtruth(aid1, noself=False)
            aid2_and_groundtruth = ibs.get_annot_groundtruth(aid2, noself=False)
            trivial_merge = len(aid1_and_groundtruth) == 1 and len(aid2_and_groundtruth) == 1
            if not trivial_merge:
                if on_nontrivial_merge is None:
                    raise Exception('no function is set up to handle nontrivial merges!')
                else:
                    on_nontrivial_merge(ibs, aid1, aid2)
            status =  _set_annot_name_rowids(aid1_and_groundtruth, [nid2] *
                                             len(aid1_and_groundtruth))
        elif isunknown2 and not isunknown1:
            print('...match unknown2 into known1')
            status =  _set_annot_name_rowids([aid2], [nid1])
        elif isunknown1 and not isunknown2:
            print('...match unknown1 into known2')
            status =  _set_annot_name_rowids([aid1], [nid2])
        else:
            raise AssertionError('impossible state')
    return status


@register_ibs_method
def set_annot_pair_as_negative_match(ibs, aid1, aid2, dryrun=False,
                                     on_nontrivial_split=None, logger=None):
    """
    TODO: ELEVATE THIS FUNCTION

    Args:
        ibs (IBEISController):  ibeis controller object
        aid1 (int):  annotation id
        aid2 (int):  annotation id
        dryrun (bool):

    CommandLine:
        python -m ibeis.annotmatch_funcs --test-set_annot_pair_as_negative_match

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.annotmatch_funcs import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> aid1, aid2 = ibs.get_valid_aids()[0:2]
        >>> dryrun = True
        >>> result = set_annot_pair_as_negative_match(ibs, aid1, aid2, dryrun)
        >>> print(result)
    """
    def _set_annot_name_rowids(aid_list, nid_list):
        print('... _set_annot_name_rowids(%r, %r)' % (aid_list, nid_list))
        if not dryrun:
            if logger is not None:
                log = logger.info
                previous_names = ibs.get_annot_names(aid_list)
                new_names = ibs.get_name_texts(nid_list)
                annot_uuids = ibs.get_annot_uuids(aid_list)
                annot_uuid_pair = ibs.get_annot_uuids((aid1, aid2))
                log((
                    'REVIEW_PAIR AS FALSE: (annot_uuid_pair=%r) '
                    'CHANGE NAME of %d (annot_uuids=%r) '
                    'WITH (previous_names=%r) to (new_names=%r)' ) % (
                        annot_uuid_pair, len(annot_uuids), annot_uuids,
                        previous_names, new_names))
            ibs.set_annot_name_rowids(aid_list, nid_list)
            ibs.set_annot_pair_as_reviewed(aid1, aid2)
    nid1, nid2 = ibs.get_annot_name_rowids([aid1, aid2])
    if nid1 == nid2:
        print('images are marked as having the same name... we must tread carefully')
        aid1_groundtruth = ibs.get_annot_groundtruth(aid1, noself=True)
        if len(aid1_groundtruth) == 1 and aid1_groundtruth == [aid2]:
            # this is the only safe case for same name split
            # Change so the names are not the same
            next_nids = ibs.make_next_nids(num=1)
            status =  _set_annot_name_rowids([aid1], next_nids)
        else:
            if on_nontrivial_split is None:
                raise Exception('no function is set up to handle nontrivial splits!')
            else:
                on_nontrivial_split(ibs, aid1, aid2)
    else:
        isunknown1, isunknown2 = ibs.is_aid_unknown([aid1, aid2])
        if isunknown1 and isunknown2:
            print('...nomatch unknown1 and unknown2 into 2 new names')
            next_nids = ibs.make_next_nids(num=2)
            status =  _set_annot_name_rowids([aid1, aid2], next_nids)
        elif not isunknown1 and not isunknown2:
            print('...nomatch known1 and known2... nothing to do (yet)')
            ibs.set_annot_pair_as_reviewed(aid1, aid2)
            status = None
            if logger is not None:
                log = logger.info
                annot_uuid_pair = ibs.get_annot_uuids((aid1, aid2))
                log('REVIEW_PAIR AS FALSE: (annot_uuid_pair=%r) NO CHANGE' % annot_uuid_pair)
        elif isunknown2 and not isunknown1:
            print('...nomatch unknown2 -> newname and known1')
            next_nids = ibs.make_next_nids(num=1)
            status =  _set_annot_name_rowids([aid2], next_nids)
        elif isunknown1 and not isunknown2:
            print('...nomatch unknown1 -> newname and known2')
            next_nids = ibs.make_next_nids(num=1)
            status =  _set_annot_name_rowids([aid1], next_nids)
        else:
            raise AssertionError('impossible state')
    return status


#@register_ibs_method
#def set_annot_pair_as_unknown_match(ibs, aid1, aid2, dryrun=False, on_nontrivial_merge=None):
#    pass


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.annotmatch_funcs
        python -m ibeis.annotmatch_funcs --allexamples
        python -m ibeis.annotmatch_funcs --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
