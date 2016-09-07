# -*- coding: utf-8 -*-
"""
python -m utool.util_inspect check_module_usage --pat="chip_match.py"
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import copy
import numpy as np
import utool as ut
import vtool as vt
from os.path import join
from operator import xor
from vtool import matching
import six
from ibeis.algo.hots import hstypes
from ibeis.algo.hots import old_chip_match
from ibeis.algo.hots import scoring
from ibeis.algo.hots import name_scoring
from ibeis.algo.hots import _pipeline_helpers as plh  # NOQA
print, rrr, profile = ut.inject2(__name__, '[chip_match]')


class NeedRecomputeError(Exception):
    pass


DEBUG_CHIPMATCH = False

#import six

MAX_FNAME_LEN = 80 if ut.WIN32 else 200
TRUNCATE_UUIDS = ut.get_argflag(('--truncate-uuids', '--trunc-uuids'))


def safeop(op_, xs, *args, **kwargs):
    return None if xs is None else op_(xs, *args, **kwargs)


def filtnorm_op(filtnorm_, op_, *args, **kwargs):
    return (None if filtnorm_ is None else
            [safeop(op_, xs, *args, **kwargs) for xs in filtnorm_])


def extend_scores(vals, num):
    if vals is None:
        return None
    return np.append(vals, np.full(num, -np.inf))


def extend_nplists_(x_list, num, shape, dtype):
    return x_list + ([np.empty(shape, dtype=dtype)] * num)


def extend_pylist_(x_list, num, val):
    return x_list + ([None] * num)


def extend_nplists(x_list, num, shape, dtype):
    return safeop(extend_nplists_, x_list, num, shape, dtype)


def extend_pylist(x_list, num, val):
    return safeop(extend_pylist_, x_list, num, val)


def convert_numpy_lists(arr_list, dtype, dims=None):
    new_arrs = [np.array(arr, dtype=dtype) for arr in arr_list]
    if dims is not None:
        new_arrs = [vt.atleast_nd(arr, dims) for arr in new_arrs]
    return new_arrs


def safecast_numpy_lists(arr_list, dtype=None, dims=None):
    if arr_list is None:
        new_arrs = None
    else:
        new_arrs = [np.array(arr, dtype=dtype) for arr in arr_list]
        if dims is not None:
            new_arrs = [vt.ensure_shape(arr, dims) for arr in new_arrs]
    return new_arrs


def convert_numpy(arr, dtype):
    return np.array(ut.replace_nones(arr, np.nan), dtype=dtype)


def check_arrs_eq(arr1, arr2):
    if arr1 is None and arr2 is None:
        return True
    elif isinstance(arr1, np.ndarray) and isinstance(arr2, np.ndarray):
        return np.all(arr1 == arr2)
    elif len(arr1) != len(arr2):
        return False
    elif any(len(x) != len(y) for x, y in zip(arr1, arr2)):
        return False
    elif all(np.all(x == y) for x, y in zip(arr1, arr2)):
        return True
    else:
        return False


def safe_check_lens_eq(arr1, arr2, msg=None):
    """
    safe_check_lens_eq(None, 1)
    safe_check_lens_eq([3], [2, 4])
    """
    if msg is None:
        msg = 'outer lengths do not correspond'
    if arr1 is None or arr2 is None:
        return True
    else:
        assert len(arr1) == len(arr2), msg + '(%r != %r)' % (len(arr1), len(arr2))


def safe_check_nested_lens_eq(arr1, arr2):
    """
    safe_check_nested_lens_eq(None, 1)
    safe_check_nested_lens_eq([[3, 4]], [[2, 4]])
    safe_check_nested_lens_eq([[1, 2, 3], [1, 2]], [[1, 2, 3], [1, 2]])
    safe_check_nested_lens_eq([[1, 2, 3], [1, 2]], [[1, 2, 3], [1]])
    """
    if arr1 is None or arr2 is None:
        return True
    else:
        safe_check_lens_eq(arr1, arr2, 'outer lengths do not correspond')
        for count, (x, y) in enumerate(zip(arr1, arr2)):
            assert len(x) == len(y), (
                'inner lengths at position=%r do not correspond (%r != %r)' %
                (count, len(x), len(y)))


def _assert_eq_len(list1_, list2_):
    if list1_ is not None:
        ut.assert_eq_len(list1_, list2_)


def prepare_dict_uuids(class_dict, ibs):
    """
    Hacks to ensure proper uuid conversion
    """
    class_dict = class_dict.copy()
    if 'qaid' not in class_dict and 'qannot_uuid' in class_dict:
        class_dict['qaid'] = ibs.get_annot_aids_from_uuid(class_dict['qannot_uuid'])
    if 'daid_list' not in class_dict and 'dannot_uuid_list' in class_dict:
        class_dict['daid_list'] = ibs.get_annot_aids_from_uuid(class_dict['dannot_uuid_list'])
    if 'dnid_list' not in class_dict and 'dannot_uuid_list' in class_dict:
        daid_list = class_dict['daid_list']
        dnid_list = ibs.get_name_rowids_from_text(class_dict['dname_list'])
        # if anything is unknown need to set to be negative daid
        check_set = set([None, ibs.const.UNKNOWN_NAME_ROWID])
        dnid_list = [-daid if dnid in check_set else dnid
                     for daid, dnid in zip(daid_list, dnid_list)]
        class_dict['dnid_list'] = dnid_list
    if 'qnid' not in class_dict and 'qname' in class_dict:
        qnid = ibs.get_name_rowids_from_text(class_dict['qname'])
        # if anything is unknown need to set to be negative daid
        qaid = class_dict['qaid']
        qnid = -qaid if qnid == ibs.const.UNKNOWN_NAME_ROWID else qnid
        class_dict['qnid'] = qnid
    if 'unique_nids' not in class_dict and 'unique_name_list' in class_dict:
        # FIXME: there is no notion of which names belong to this nid
        # unique_nids = ibs.get_name_rowids_from_text(class_dict['unique_name_list'])
        # class_dict['unique_nids'] = unique_nids
        dnid_list = class_dict['dnid_list']
        # This will probably work... for the short term
        unique_nids_, name_groupxs_ = vt.group_indices(np.array(dnid_list))
        class_dict['unique_nids'] = unique_nids_
    return class_dict


class _ChipMatchVisualization(object):
    """
    Abstract class containing the visualization function for ChipMatch
    """

    def show_single_namematch(cm, qreq_, dnid, fnum=None, pnum=None,
                              homog=ut.get_argflag('--homog'), **kwargs):
        r"""
        CommandLine:
            python -m ibeis --tf ChipMatch.show_single_namematch --show
            python -m ibeis --tf ChipMatch.show_single_namematch --show --qaid 1
            python -m ibeis --tf ChipMatch.show_single_namematch --show --qaid 1 \
                    --dpath figures --save ~/latex/crall-candidacy-2015/figures/namematch.jpg

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> cm, qreq_ = ibeis.testdata_cm('PZ_MTEST', default_qaids=[18])
            >>> homog = False
            >>> dnid = cm.qnid
            >>> cm.show_single_namematch(qreq_, dnid)
            >>> ut.quit_if_noshow()
            >>> ut.show_if_requested()
        """
        from ibeis.viz import viz_matches
        qaid = cm.qaid
        if cm.nid2_nidx is None:
            raise AssertionError('cm.nid2_nidx has not been evaluated yet')
            #cm.score_nsum(qreq_)
        # <GET NAME GROUPXS>
        try:
            nidx = cm.nid2_nidx[dnid]
            #if nidx == 144:
            #    raise
        except KeyError:
            #def extend():
                #pass
            #cm.daid_list
            #cm.print_inspect_str(qreq_)
            #cm_orig = cm  # NOQA
            #cm_orig.assert_self(qreq_)
            #other_aids = qreq_.daids
            # Hack to get rid of key error
            print('CHIP HAS NO GROUND TRUTH MATCHES')
            cm.assert_self(verbose=False)
            cm2 = cm.extend_results(qreq_)
            cm2.assert_self(verbose=False)
            cm = cm2
            nidx = cm.nid2_nidx[dnid]
            #raise
        groupxs = cm.name_groupxs[nidx]
        daids = vt.take2(cm.daid_list, groupxs)
        dnids = vt.take2(cm.dnid_list, groupxs)
        assert np.all(dnid == dnids), (
            'inconsistent naming, dnid=%r, dnids=%r' % (dnid, dnids,))
        groupxs = groupxs.compress(daids != cm.qaid)
        # </GET NAME GROUPXS>
        # sort annots in this name by the chip score
        # HACK USE cm.annot_score_list
        group_sortx = cm.annot_score_list.take(groupxs).argsort()[::-1]
        sorted_groupxs = groupxs.take(group_sortx)
        # get the info for this name
        name_fm_list  = ut.take(cm.fm_list, sorted_groupxs)
        REMOVE_EMPTY_MATCHES = len(sorted_groupxs) > 3
        REMOVE_EMPTY_MATCHES = True
        if REMOVE_EMPTY_MATCHES:
            isvalid_list = np.array([len(fm) > 0 for fm in name_fm_list])
            MAX_MATCHES = 3
            isvalid_list = ut.make_at_least_n_items_valid(isvalid_list, MAX_MATCHES)
            name_fm_list = ut.compress(name_fm_list, isvalid_list)
            sorted_groupxs = sorted_groupxs.compress(isvalid_list)

        name_H1_list   = (None if not homog or cm.H_list is None else
                          ut.take(cm.H_list, sorted_groupxs))
        name_fsv_list  = (None if cm.fsv_list is None else
                          ut.take(cm.fsv_list, sorted_groupxs))
        name_fs_list   = (None if name_fsv_list is None else
                          [fsv.prod(axis=1) for fsv in name_fsv_list])
        name_daid_list = ut.take(cm.daid_list, sorted_groupxs)
        # find features marked as invalid by name scoring
        featflag_list  = name_scoring.get_chipmatch_namescore_nonvoting_feature_flags(
            cm, qreq_=qreq_)
        name_featflag_list = ut.take(featflag_list, sorted_groupxs)
        # Get the scores for names and chips
        name_score = cm.name_score_list[nidx]
        name_rank = ut.listfind(cm.name_score_list.argsort()[::-1].tolist(), nidx)
        name_annot_scores = cm.annot_score_list.take(sorted_groupxs)

        _ = viz_matches.show_name_matches(
            qreq_.ibs, qaid, name_daid_list, name_fm_list, name_fs_list,
            name_H1_list, name_featflag_list, name_score=name_score, name_rank=name_rank,
            name_annot_scores=name_annot_scores, qreq_=qreq_, fnum=fnum,
            pnum=pnum, **kwargs)
        return _

    def show_single_annotmatch(cm, qreq_, daid=None, fnum=None, pnum=None,
                               homog=ut.get_argflag('--homog'), aid2=None, **kwargs):
        """
        TODO: rename daid to aid2

        CommandLine:
            python -m ibeis.algo.hots.chip_match show_single_annotmatch --show

            python -m ibeis.algo.hots.chip_match show_single_annotmatch --show --qaids=5245 --daids=5161 --db PZ_Master1

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> ibs, qreq_, cm_list = plh.testdata_post_sver('PZ_MTEST', qaid_list=[18])
            >>> cm = cm_list[0]
            >>> cm.score_nsum(qreq_)
            >>> daid = cm.groundtruth_daids[0]
            >>> ut.quit_if_noshow()
            >>> cm.show_single_annotmatch(qreq_, daid)
            >>> ut.show_if_requested()

            cm.compress_top_feature_matches(num=1)
        """
        from ibeis.viz import viz_matches
        if aid2 is not None:
            assert daid is None, 'use aid2 instead of daid kwarg'
            daid = aid2

        if daid is None:
            idx = cm.argsort()[0]
            daid = cm.daid_list[idx]
        else:
            idx = cm.daid2_idx[daid]
        fm   = cm.fm_list[idx]
        H1   = None if not homog or cm.H_list is None else cm.H_list[idx]
        fsv  = None if cm.fsv_list is None else cm.fsv_list[idx]
        fs   = None if fsv is None else fsv.prod(axis=1)
        showkw = dict(fm=fm, fs=fs, H1=H1, fnum=fnum, pnum=pnum, **kwargs)
        score = None if cm.score_list is None else cm.score_list[idx]
        viz_matches.show_matches2(qreq_.ibs, cm.qaid, daid, qreq_=qreq_,
                                  score=score, **showkw)

    def show_ranked_matches(cm, qreq_, clip_top=6, *args, **kwargs):
        r"""
        Plots the ranked-list of name/annot matches using matplotlib

        Args:
            qreq_ (QueryRequest): query request object with hyper-parameters
            clip_top (int): (default = 6)

        Kwargs:
            fnum, figtitle, plottype, ...more

        SeeAlso:
            ibeis.viz.viz_matches.show_matches2
            ibeis.viz.viz_matches.show_name_matches

        CommandLine:
            python -m ibeis --tf ChipMatch.show_ranked_matches --show --qaid 1
            python -m ibeis --tf ChipMatch.show_ranked_matches --qaid 86 --colorbar_=False --show
            python -m ibeis --tf ChipMatch.show_ranked_matches:0 --qaid 86 --colorbar_=False --show

        Example:
            >>> # DISABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> from ibeis.viz import viz_matches
            >>> import ibeis
            >>> cm_list, qreq_ = ibeis.testdata_cmlist('PZ_MTEST', [1])
            >>> defaultkw = dict(ut.recursive_parse_kwargs(viz_matches.show_name_matches))
            >>> kwargs = ut.argparse_dict(defaultkw, only_specified=True)
            >>> ut.delete_dict_keys(kwargs, ['qaid'])
            >>> kwargs['plottype'] = kwargs.get('plottype', 'namematch')
            >>> cm = cm_list[0]
            >>> cm.score_nsum(qreq_)
            >>> clip_top = ut.get_argval('--clip-top', default=3)
            >>> print('kwargs = %s' % (ut.repr2(kwargs, nl=True),))
            >>> cm.show_ranked_matches(qreq_, clip_top, **kwargs)
            >>> ut.show_if_requested()

        Example:
            >>> # DISABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> from ibeis.viz import viz_matches
            >>> defaultkw = dict(ut.recursive_parse_kwargs(viz_matches.show_name_matches))
            >>> kwargs = ut.argparse_dict(defaultkw, only_specified=True)
            >>> del kwargs['qaid']
            >>> kwargs['plottype'] = kwargs.get('plottype', 'namematch')
            >>> ibs, qreq_, cm_list = plh.testdata_post_sver('PZ_MTEST', qaid_list=[1])
            >>> cm = cm_list[0]
            >>> cm.score_nsum(qreq_)
            >>> clip_top = ut.get_argval('--clip-top', default=3)
            >>> print('kwargs = %s' % (ut.repr2(kwargs, nl=True),))
            >>> cm.show_ranked_matches(qreq_, clip_top, **kwargs)
            >>> ut.show_if_requested()
        """
        idx_list  = ut.listclip(cm.argsort(), clip_top)
        cm.show_index_matches(qreq_, idx_list, *args, **kwargs)

    def show_daids_matches(cm, qreq_, daids, *args, **kwargs):
        idx_list = ut.dict_take(cm.daid2_idx, daids)
        cm.show_index_matches(qreq_, idx_list, *args, **kwargs)

    def show_index_matches(cm, qreq_, idx_list, fnum=None, figtitle=None,
                           plottype='annotmatch', **kwargs):
        import plottool as pt
        if fnum is None:
            fnum = pt.next_fnum()
        nRows, nCols  = pt.get_square_row_cols(len(idx_list), fix=False)
        if ut.get_argflag('--vert'):
            # HACK
            nRows, nCols = nCols, nRows
        next_pnum     = pt.make_pnum_nextgen(nRows, nCols)
        for idx in idx_list:
            daid  = cm.daid_list[idx]
            pnum = next_pnum()
            if plottype == 'namematch':
                dnid = qreq_.ibs.get_annot_nids(daid)
                cm.show_single_namematch(qreq_, dnid, pnum=pnum, fnum=fnum, **kwargs)
            elif plottype == 'annotmatch':
                cm.show_single_annotmatch(qreq_, daid, fnum=fnum, pnum=pnum, **kwargs)
                # FIXME:
                score = vt.trytake(cm.score_list, idx)
                annot_score = vt.trytake(cm.annot_score_list, idx)
                score_str = ('score = %.3f' % (score,)
                             if score is not None else
                             'score = None')
                annot_score_str = ('annot_score = %.3f' % (annot_score,)
                                   if annot_score is not None else
                                   'annot_score = None')
                title = score_str + '\n' + annot_score_str
                pt.set_title(title)
            else:
                raise NotImplementedError('Unknown plottype=%r' % (plottype,))
        if figtitle is not None:
            pt.set_figtitle(figtitle)

    show_matches = show_single_annotmatch  # HACK

    def ishow_single_annotmatch(cm, qreq_, aid2=None, **kwargs):
        r"""
        Iteract with a match to an individual annotation (or maybe name?)

        Args:
            qreq_ (QueryRequest):  query request object with hyper-parameters
            aid2 (int):  annotation id(default = None)

        CommandLine:
            python -m ibeis.algo.hots.chip_match --exec-ishow_single_annotmatch --show

        Example:
            >>> # DISABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> ibs, qreq_, cm_list = plh.testdata_post_sver('PZ_MTEST', qaid_list=[1])
            >>> cm = cm_list[0]
            >>> cm.score_nsum(qreq_)
            >>> aid2 = None
            >>> result = cm.ishow_single_annotmatch(qreq_, aid2, noupdate=True)
            >>> print(result)
            >>> ut.show_if_requested()
        """
        from ibeis.viz.interact import interact_matches  # NOQA
        #if aid == 'top':
        #    aid = cm.get_top_aids(ibs)
        kwshow = {
            'mode': 1,
        }
        if aid2 is None:
            aid2 = cm.get_top_aids(ntop=1)[0]
        print('[cm] ishow_single_annotmatch aids(%s, %s)' % (cm.qaid, aid2,))
        kwshow.update(**kwargs)
        try:
            inter = interact_matches.MatchInteraction(
                qreq_.ibs, cm, aid2, qreq_=qreq_, **kwshow)
            inter.start()
            return inter
        except Exception as ex:
            ut.printex(ex, 'failed in cm.show_matches', keys=['aid', 'qreq_'])
            raise
        #if not kwargs.get('noupdate', False):
        #    import plottool as pt
        #    pt.update()

    ishow_match = ishow_single_annotmatch
    ishow_matches = ishow_single_annotmatch

    def ishow_analysis(cm, qreq_, **kwargs):
        """
        CommandLine:
            python -m ibeis.algo.hots.chip_match --exec-_ChipMatchVisualization.ishow_analysis --show

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> qaid = 18
            >>> ibs, qreq_, cm_list = plh.testdata_pre_sver('PZ_MTEST', qaid_list=[qaid])
            >>> cm = cm_list[0]
            >>> cm.score_nsum(qreq_)
            >>> ut.quit_if_noshow()
            >>> cm.ishow_analysis(qreq_)
            >>> ut.show_if_requested()
        """
        from ibeis.viz.interact import interact_qres
        kwshow = {
            'show_query': False,
            'show_timedelta': True,
        }
        kwshow.update(kwargs)
        return interact_qres.ishow_analysis(qreq_.ibs, cm, qreq_=qreq_, **kwshow)

    def show_analysis(cm, qreq_, **kwargs):
        from ibeis.viz import viz_qres
        kwshow = {
            'show_query': False,
            'show_timedelta': True,
        }
        kwshow.update(kwargs)
        return viz_qres.show_qres_analysis(qreq_.ibs, cm, qreq_=qreq_, **kwshow)

    def imwrite_single_annotmatch(cm, qreq_, aid, **kwargs):
        """
        CommandLine:
            python -m ibeis.algo.hots.chip_match --exec-ChipMatch.imwrite_single_annotmatch --show

        Example:
            >>> # DISABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> kwargs = {}
            >>> kwargs['dpi'] = ut.get_argval('--dpi', int, None)
            >>> kwargs['figsize'] = ut.get_argval('--figsize', list, None)
            >>> kwargs['fpath'] = ut.get_argval('--fpath', str, None)
            >>> kwargs['draw_fmatches'] = not ut.get_argflag('--no-fmatches')
            >>> kwargs['vert'] = ut.get_argflag('--vert')
            >>> kwargs['draw_border'] = ut.get_argflag('--draw_border')
            >>> kwargs['saveax'] = ut.get_argflag('--saveax')
            >>> kwargs['in_image'] = ut.get_argflag('--in-image')
            >>> kwargs['draw_lbl'] = ut.get_argflag('--no-draw-lbl')
            >>> print('kwargs = %s' % (ut.dict_str(kwargs),))
            >>> cm, qreq_ = ibeis.testdata_cm()
            >>> aid = cm.get_top_aids()[0]
            >>> img_fpath = cm.imwrite_single_annotmatch(qreq_, aid, **kwargs)
            >>> ut.quit_if_noshow()
            >>> # show the image dumped to disk
            >>> ut.startfile(img_fpath, quote=True)
            >>> ut.show_if_requested()
        """
        import plottool as pt
        import matplotlib as mpl
        # Pop save kwargs from kwargs
        save_keys = ['dpi', 'figsize', 'saveax', 'fpath', 'fpath_strict', 'verbose']
        save_vals = ut.dict_take_pop(kwargs, save_keys, None)
        savekw = dict(zip(save_keys, save_vals))
        fpath = savekw.pop('fpath')
        if fpath is None and 'fpath_strict' not in savekw:
            savekw['usetitle'] = True
        was_interactive = mpl.is_interactive()
        if was_interactive:
            mpl.interactive(False)
        # Make new figure
        fnum = pt.ensure_fnum(kwargs.pop('fnum', None))
        #fig = pt.figure(fnum=fnum, doclf=True, docla=True)
        fig = pt.plt.figure(fnum)
        fig.clf()
        # Draw Matches
        cm.show_single_annotmatch(qreq_, aid, colorbar_=False, fnum=fnum, **kwargs)
        #if not kwargs.get('notitle', False):
        #    pt.set_figtitle(cm.make_smaller_title())
        # Save Figure
        # Setting fig=fig might make the dpi and figsize code not work
        img_fpath = pt.save_figure(fpath=fpath, fig=fig, **savekw)
        pt.plt.close(fig)  # Ensure that this figure will not pop up
        if was_interactive:
            mpl.interactive(was_interactive)
        #if False:
        #    ut.startfile(img_fpath)
        return img_fpath

    @profile
    def imwrite_single_annotmatch2(cm, qreq_, aid, fpath, **kwargs):
        """
        users newer rendering based code
        """
        import plottool as pt
        import matplotlib as mpl
        # Pop save kwargs from kwargs
        save_keys = ['dpi', 'figsize', 'saveax', 'verbose']
        save_vals = ut.dict_take_pop(kwargs, save_keys, None)
        savekw = dict(zip(save_keys, save_vals))
        was_interactive = mpl.is_interactive()
        if was_interactive:
            mpl.interactive(False)
        # Make new figure
        fnum = pt.ensure_fnum(kwargs.pop('fnum', None))
        # Create figure --- this takes about 19% - 11% of the time depending on settings
        fig = pt.plt.figure(fnum)
        fig.clf()
        #
        # Draw Matches --- this takes about 48% - 67% of the time depending on settings
        # wrapped call to show_matches2
        cm.show_single_annotmatch(qreq_, aid, colorbar_=False, fnum=fnum, **kwargs)
        # Write matplotlib axes to an image
        axes_extents = pt.extract_axes_extents(fig)
        assert len(axes_extents) == 1, 'more than one axes'
        extent = axes_extents[0]
        #with io.BytesIO() as stream:
        # This call takes 23% - 15% of the time depending on settings
        fig.savefig(fpath, bbox_inches=extent, **savekw)
        #stream.seek(0)
        #data = np.fromstring(stream.getvalue(), dtype=np.uint8)
        #image = cv2.imdecode(data, 1)
        # Ensure that this figure will not pop up
        pt.plt.close(fig)
        if was_interactive:
            mpl.interactive(was_interactive)
        #return image

    @profile
    def render_single_annotmatch(cm, qreq_, aid, **kwargs):
        """
        CommandLine:
            python -m ibeis.algo.hots.chip_match --exec-_ChipMatchVisualization.render_single_annotmatch --show
            utprof.py -m ibeis.algo.hots.chip_match --exec-_ChipMatchVisualization.render_single_annotmatch --show
            utprof.py -m ibeis.algo.hots.chip_match --exec-_ChipMatchVisualization.render_single_annotmatch --show

        Example:
            >>> # DISABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> kwargs = {}
            >>> kwargs['dpi'] = ut.get_argval('--dpi', int, None)
            >>> kwargs['draw_fmatches'] = False
            >>> kwargs['vert'] = False
            >>> kwargs['show_score'] = False
            >>> kwargs['show_timedelta'] = False
            >>> kwargs['draw_border'] = False
            >>> kwargs['in_image'] = False
            >>> kwargs['draw_lbl'] = False
            >>> print('kwargs = %s' % (ut.dict_str(kwargs),))
            >>> cm, qreq_ = ibeis.testdata_cm()
            >>> aid = cm.get_top_aids()[0]
            >>> import plottool as pt
            >>> tt = ut.tic('render image')
            >>> img = cm.render_single_annotmatch(qreq_, aid, **kwargs)
            >>> ut.toc(tt)
            >>> ut.quit_if_noshow()
            >>> pt.imshow(img)
            >>> ut.show_if_requested()
        """
        import io
        import cv2
        import plottool as pt
        import matplotlib as mpl
        # Pop save kwargs from kwargs
        save_keys = ['dpi', 'figsize', 'saveax', 'verbose']
        save_vals = ut.dict_take_pop(kwargs, save_keys, None)
        savekw = dict(zip(save_keys, save_vals))
        was_interactive = mpl.is_interactive()
        if was_interactive:
            mpl.interactive(False)
        # Make new figure
        fnum = pt.ensure_fnum(kwargs.pop('fnum', None))
        # Create figure --- this takes about 19% - 11% of the time depending on settings
        fig = pt.plt.figure(fnum)
        fig.clf()
        #
        # Draw Matches --- this takes about 48% - 67% of the time depending on settings
        # wrapped call to show_matches2
        cm.show_single_annotmatch(qreq_, aid, colorbar_=False, fnum=fnum, **kwargs)
        # Write matplotlib axes to an image
        axes_extents = pt.extract_axes_extents(fig)
        assert len(axes_extents) == 1, 'more than one axes'
        extent = axes_extents[0]
        with io.BytesIO() as stream:
            # This call takes 23% - 15% of the time depending on settings
            fig.savefig(stream, bbox_inches=extent, **savekw)
            stream.seek(0)
            data = np.fromstring(stream.getvalue(), dtype=np.uint8)
        image = cv2.imdecode(data, 1)
        # Ensure that this figure will not pop up
        pt.plt.close(fig)
        if was_interactive:
            mpl.interactive(was_interactive)
        return image

    def qt_inspect_gui(cm, ibs, ranks_top=6, qreq_=None, name_scoring=False):
        r"""
        Args:
            ibs (IBEISController):  ibeis controller object
            ranks_top (int): (default = 6)
            qreq_ (QueryRequest):  query request object with hyper-parameters(default = None)
            name_scoring (bool): (default = False)

        Returns:
            QueryResult: qres_wgt -  object of feature correspondences and scores

        CommandLine:
            python -m ibeis.algo.hots.chip_match --exec-qt_inspect_gui --show

        Example:
            >>> # DISABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> ibs, qreq_, cm_list = plh.testdata_post_sver('PZ_MTEST', qaid_list=[1])
            >>> cm = cm_list[0]
            >>> cm.score_nsum(qreq_)
            >>> ranks_top = 6
            >>> name_scoring = False
            >>> qres_wgt = cm.qt_inspect_gui(ibs, ranks_top, qreq_, name_scoring)
            >>> ut.quit_if_noshow()
            >>> import guitool
            >>> guitool.qtapp_loop(qwin=qres_wgt)
        """
        print('[cm] qt_inspect_gui')
        from ibeis.gui import inspect_gui
        import guitool
        guitool.ensure_qapp()
        cm_list = [cm]
        print('[inspect_matches] make_qres_widget')
        qres_wgt = inspect_gui.QueryResultsWidget(ibs, cm_list,
                                                  ranks_top=ranks_top,
                                                  name_scoring=name_scoring,
                                                  qreq_=qreq_)
        print('[inspect_matches] show')
        qres_wgt.show()
        print('[inspect_matches] raise')
        qres_wgt.raise_()
        return qres_wgt


class _ChipMatchScorers(object):
    """
    Score Aggregation Functions
    """

    # --- ChipSum Score

    @profile
    def evaluate_csum_score(cm, qreq_):
        csum_score_list = scoring.compute_csum_score(cm)
        cm.algo_annot_scores['csum'] = csum_score_list
        #cm.csum_score_list = csum_score_list

    @profile
    def evaluate_nsum_score(cm, qreq_):
        """ Calls name scoring logic """
        cm.evaluate_dnids(qreq_)
        nsum_nid_list, nsum_score_list = name_scoring.compute_nsum_score(cm, qreq_=qreq_)
        assert np.all(cm.unique_nids == nsum_nid_list), 'name score not in alignment'

        try:
            normsum = qreq_.qparams.normsum
        except AttributeError:
            normsum = False

        if normsum:
            # Normalize name scores
            num_unmatched = len(cm.unique_nids) - len(nsum_score_list)
            valid_scores = nsum_score_list.compress(np.isfinite(nsum_score_list))
            unmatched_score = vt.safe_min(valid_scores, 0)
            zsum = unmatched_score * num_unmatched + valid_scores.sum()
            nsum_score_list_ = nsum_score_list / zsum
            nsum_score_list = nsum_score_list_

        cm.algo_name_scores['nsum'] = nsum_score_list
        #cm.nsum_score_list = nsum_score_list

    @profile
    def score_csum(cm, qreq_):
        """
        CommandLine:
            python -m ibeis.algo.hots.chip_match --test-score_csum --show
            python -m ibeis.algo.hots.chip_match --test-score_csum --show --qaid 18

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> ibs, qreq_, cm_list = plh.testdata_post_sver()
            >>> cm = cm_list[0]
            >>> cm.score_csum(qreq_)
            >>> ut.quit_if_noshow()
            >>> cm.show_ranked_matches(qreq_, figtitle='score_csum')
            >>> ut.show_if_requested()
        """
        cm.evaluate_csum_score(qreq_)
        cm.set_cannonical_annot_score(cm.csum_score_list)

    @profile
    def score_maxcsum(cm, qreq_):
        cm.evaluate_dnids(qreq_)
        cm.score_csum(qreq_)
        cm.maxcsum_score_list = np.array([
            scores.max()
            for scores in vt.apply_grouping(cm.csum_score_list,
                                            cm.name_groupxs)
        ])
        cm.set_cannonical_name_score(cm.csum_score_list, cm.maxcsum_score_list)

    @profile
    def score_nsum(cm, qreq_):
        """
        CommandLine:
            python -m ibeis.algo.hots.chip_match --test-score_nsum --show --qaid 1
            python -m ibeis.algo.hots.chip_match --test-score_nsum --show --qaid 18 -t default:normsum=True

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> qreq_, args = plh.testdata_pre('vsone_reranking', defaultdb='PZ_MTEST', a=['default'], qaid_override=[18])
            >>> cm = args.cm_list_SVER[0]
            >>> #ibs, qreq_, cm_list = plh.testdata_post_sver('PZ_MTEST', qaid_list=[18])
            >>> #cm = cm_list[0]
            >>> cm.score_nsum(qreq_)
            >>> gt_score = cm.score_list.compress(cm.get_groundtruth_flags()).max()
            >>> cm.print_csv()
            >>> assert cm.get_top_nids()[0] == cm.unique_nids[cm.name_score_list.argmax()], 'bug in alignment'
            >>> ut.quit_if_noshow()
            >>> cm.show_ranked_matches(qreq_, figtitle='score_nsum')
            >>> ut.show_if_requested()
            >>> assert cm.get_top_nids()[0] == cm.qnid, 'is this case truely hard?'
        """
        cm.evaluate_csum_score(qreq_)
        cm.evaluate_nsum_score(qreq_)
        cm.set_cannonical_name_score(cm.csum_score_list, cm.nsum_score_list)

    # --- ChipCoverage Score

    @profile
    def evaluate_acov_score(cm, qreq_):
        daid_list, acov_score_list = scoring.compute_annot_coverage_score(
            qreq_, cm, qreq_.qparams)
        assert np.all(daid_list == np.array(cm.daid_list)), 'daids out of alignment'
        cm.acov_score_list = acov_score_list

    @profile
    def score_annot_coverage(cm, qreq_):
        """
        CommandLine:
            python -m ibeis.algo.hots.chip_match --test-score_annot_coverage --show
            python -m ibeis.algo.hots.chip_match --test-score_annot_coverage --show --qaid 18

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> ibs, qreq_, cm_list = plh.testdata_post_sver()
            >>> cm = cm_list[0]
            >>> cm.fs_list = cm.get_fs_list(col='lnbnn')
            >>> cm.score_annot_coverage(qreq_)
            >>> ut.quit_if_noshow()
            >>> cm.show_ranked_matches(qreq_, figtitle='score_annot_coverage')
            >>> ut.show_if_requested()
        """
        cm.evaluate_acov_score(qreq_)
        cm.set_cannonical_annot_score(cm.acov_score_list)

    # --- NameCoverage Score

    @profile
    def evaluate_ncov_score(cm, qreq_):
        cm.evaluate_dnids(qreq_)
        ncov_nid_list, ncov_score_list = scoring.compute_name_coverage_score(
            qreq_, cm, qreq_.qparams)
        assert np.all(cm.unique_nids == ncov_nid_list)
        cm.ncov_score_list = ncov_score_list

    @profile
    def score_name_coverage(cm, qreq_):
        """
        CommandLine:
            python -m ibeis.algo.hots.chip_match --test-score_name_coverage --show
            python -m ibeis.algo.hots.chip_match --test-score_name_coverage --show --qaid 18

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> ibs, qreq_, cm_list = plh.testdata_post_sver()
            >>> cm = cm_list[0]
            >>> cm.fs_list = cm.get_fs_list(col='lnbnn')
            >>> cm.score_name_coverage(qreq_)
            >>> ut.quit_if_noshow()
            >>> cm.show_ranked_matches(qreq_, figtitle='score_name_coverage')
            >>> ut.show_if_requested()
        """
        if cm.csum_score_list is None:
            cm.evaluate_csum_score(qreq_)
        cm.evaluate_ncov_score(qreq_)
        cm.set_cannonical_name_score(cm.csum_score_list, cm.ncov_score_list)


class MatchBaseIO(object):
    """
    """

    @classmethod
    def load_from_fpath(cls, fpath, verbose=ut.VERBOSE):
        state_dict = ut.load_cPkl(fpath, verbose=verbose)
        self = cls()
        self.__setstate__(state_dict)
        return self

    def save_to_fpath(cm, fpath, verbose=ut.VERBOSE):
        """
        CommandLine:
            python ibeis --tf MatchBaseIO.save_to_fpath --verbtest --show

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> qaid = 18
            >>> ibs, qreq_, cm_list = plh.testdata_pre_sver('PZ_MTEST', qaid_list=[qaid])
            >>> cm = cm_list[0]
            >>> cm.score_nsum(qreq_)
            >>> dpath = ut.get_app_resource_dir('ibeis')
            >>> fpath = join(dpath, 'tmp_chipmatch.cPkl')
            >>> ut.delete(fpath)
            >>> cm.save_to_fpath(fpath)
            >>> cm2 = ChipMatch.load_from_fpath(fpath)
            >>> assert cm == cm2
            >>> ut.quit_if_noshow()
            >>> cm.ishow_analysis(qreq_)
            >>> ut.show_if_requested()
        """
        #ut.save_data(fpath, cm.__getstate__(), verbose=verbose)
        ut.save_cPkl(fpath, cm.__getstate__(), verbose=verbose)

    def __getstate__(cm):
        state_dict = cm.__dict__
        return state_dict

    def __setstate__(cm, state_dict):
        cm.__dict__.update(state_dict)

    def copy(self):
        cls = self.__class__
        out = cls()
        state_dict = copy.deepcopy(self.__getstate__())
        out.__setstate__(state_dict)
        return out


class _BaseVisualization(object):

    def show_analysis(cm, qreq_, **kwargs):
        # HACK FOR ANNOT MATCH (HUMPBACKS)
        from ibeis.viz import viz_qres
        kwshow = {
            'show_query': False,
            'show_timedelta': True,
        }
        kwshow.update(kwargs)
        #print('\n')
        #print("???? HACK SHOW QRES ANALYSIS")
        return viz_qres.show_qres_analysis(qreq_.ibs, cm, qreq_=qreq_, **kwshow)

    def ishow_analysis(cm, qreq_, **kwargs):
        # HACK FOR ANNOT MATCH (HUMPBACKS)
        from ibeis.viz.interact import interact_qres
        kwshow = {
            'show_query': False,
            'show_timedelta': True,
        }
        kwshow.update(kwargs)
        return interact_qres.ishow_analysis(qreq_.ibs, cm, qreq_=qreq_, **kwshow)

    def show_single_namematch(cm, qreq_, dnid, fnum=None, pnum=None,
                              homog=ut.get_argflag('--homog'), **kwargs):
        """
        HACK FOR ANNOT MATCH
        """
        # HACK FOR ANNOT MATCH (HUMPBACKS)
        #print('\n')
        #print("???? HACK SHOW SINGLE NAME MATCH")
        from ibeis.viz import viz_matches
        qaid = cm.qaid
        if cm.nid2_nidx is None:
            raise AssertionError('cm.nid2_nidx has not been evaluated yet')
            #cm.score_nsum(qreq_)
        # <GET NAME GROUPXS>
        try:
            nidx = cm.nid2_nidx[dnid]
        except KeyError:
            #cm.print_inspect_str(qreq_)
            cm_orig = cm  # NOQA
            cm_orig.assert_self(qreq_)
            # Hack to get rid of key error
            cm.assert_self(verbose=False)
            cm2 = cm.extend_results(qreq_)
            cm2.assert_self(verbose=False)
            cm = cm2
            nidx = cm.nid2_nidx[dnid]
            #raise
        # </GET NAME GROUPXS>
        groupxs = cm.name_groupxs[nidx]
        daids = vt.take2(cm.daid_list, groupxs)
        dnids = vt.take2(cm.dnid_list, groupxs)
        assert np.all(dnid == dnids), (
            'inconsistent naming, dnid=%r, dnids=%r' % (dnid, dnids,))
        groupxs = groupxs.compress(daids != cm.qaid)
        # </GET NAME GROUPXS>
        # sort annots in this name by the chip score
        # HACK USE cm.annot_score_list
        #group_sortx = cm.csum_score_list.take(groupxs).argsort()[::-1]
        group_sortx = cm.annot_score_list.take(groupxs).argsort()[::-1]
        sorted_groupxs = groupxs.take(group_sortx)
        # get the info for this name
        name_daid_list = ut.take(cm.daid_list, sorted_groupxs)
        # find features marked as invalid by name scoring
        # Get the scores for names and chips
        name_score = cm.name_score_list[nidx]
        name_rank = ut.listfind(cm.name_score_list.argsort()[::-1].tolist(), nidx)
        #name_annot_scores = cm.csum_score_list.take(sorted_groupxs)
        name_annot_scores = cm.annot_score_list.take(sorted_groupxs)

        kwargs = kwargs.copy()
        #print('kwargs.copy = %r' % (kwargs,))
        #draw_fmatches = kwargs.get('draw_fmatches', True)
        # MEGAHACK TO DEAL WITH OLD EXPLICIT ELLIPSE FEATURES
        kwargs['draw_fmatches'] = kwargs.get('draw_ell', True)
        kwargs['show_matches'] = False

        _ = viz_matches.show_name_matches(
            qreq_.ibs, qaid, name_daid_list, None, None, None, None, name_score=name_score, name_rank=name_rank,
            name_annot_scores=name_annot_scores, qreq_=qreq_, fnum=fnum,
            pnum=pnum, **kwargs)
        return _


class _AnnotMatchConvenienceGetter(object):

    @property
    def algo_annot_scores(cm):
        attrs = [score_method + '_score_list' for score_method in cm.special_annot_scores]
        algo_annot_scores = ut.ClassAttrDictProxy(cm, cm.special_annot_scores, attrs)
        return algo_annot_scores

    @property
    def algo_name_scores(cm):
        attrs = [score_method + '_score_list' for score_method in cm.special_name_scores]
        algo_name_scores = ut.ClassAttrDictProxy(cm, cm.special_name_scores, attrs)
        return algo_name_scores

    #------------------
    # Score-Based Result Functions
    #------------------

    def get_top_scores(cm, ntop=None):
        sortx = cm.score_list.argsort()[::-1]
        _top_scores = vt.list_take_(cm.score_list, sortx)
        top_scores = ut.listclip(_top_scores, ntop)
        return top_scores

    def get_top_nids(cm, ntop=None):
        sortx_ = cm.score_list.argsort()[::-1]
        sortx = sortx_[slice(0, ntop)]
        top_nids = vt.list_take_(cm.dnid_list, sortx)
        return top_nids

    def get_top_aids(cm, ntop=None):
        sortx = cm.score_list.argsort()[::-1]
        _top_aids = vt.list_take_(cm.daid_list, sortx)
        top_aids = ut.listclip(_top_aids, ntop)
        return top_aids

    def get_top_truth_aids(cm, ibs, truth, ntop=None):
        """ top scoring aids of a certain truth value """
        sortx = cm.score_list.argsort()[::-1]
        _top_aids = vt.list_take_(cm.daid_list, sortx)
        truth_list = ibs.get_aidpair_truths([cm.qaid] * len(_top_aids), _top_aids)
        flag_list = truth_list == truth
        _top_aids = _top_aids.compress(flag_list, axis=0)
        top_truth_aids = ut.listclip(_top_aids, ntop)
        return top_truth_aids

    def get_top_gf_aids(cm, ibs, ntop=None):
        return cm.get_top_truth_aids(ibs, ibs.const.TRUTH_NOT_MATCH, ntop)

    def get_top_gt_aids(cm, ibs, ntop=None):
        return cm.get_top_truth_aids(ibs, ibs.const.TRUTH_MATCH, ntop)

    #------------------
    # Getter Functions
    #------------------

    def get_annot_scores(cm, daids, score_method=None):
        #idx_list = [cm.daid2_idx.get(daid, None) for daid in daids]
        score_list = cm.score_list
        idx_list = ut.dict_take(cm.daid2_idx, daids, None)
        score_list = [None if idx is None else score_list[idx]
                      for idx in idx_list]
        return score_list

    def get_annot_ranks(cm, daids):  # score_method=None):
        score_ranks = cm.score_list.argsort()[::-1].argsort()
        idx_list = ut.dict_take(cm.daid2_idx, daids, None)
        rank_list = [None if idx is None else score_ranks[idx]
                      for idx in idx_list]
        return rank_list

    def get_name_ranks(cm, dnids):  # score_method=None):
        score_ranks = cm.name_score_list.argsort()[::-1].argsort()
        idx_list = ut.dict_take(cm.nid2_nidx, dnids, None)
        rank_list = [None if idx is None else score_ranks[idx]
                      for idx in idx_list]
        return rank_list

    def get_groundtruth_flags(cm):
        assert cm.dnid_list is not None, 'run cm.evaluate_dnids'
        gt_flags = cm.dnid_list == cm.qnid
        return gt_flags

    def get_groundtruth_daids(cm):
        gt_flags = cm.get_groundtruth_flags()
        gt_daids = vt.list_compress_(cm.daid_list, gt_flags)
        return gt_daids

    @property
    def groundtruth_daids(cm):
        return cm.get_groundtruth_daids()

    def get_nid_scores(cm, nid_list):
        nidx_list = ut.dict_take(cm.nid2_nidx, nid_list)
        name_scores = vt.list_take_(cm.name_score_list, nidx_list)
        return name_scores

    def get_ranked_nids(cm):
        sortx = cm.name_score_list.argsort()[::-1]
        sorted_name_scores = cm.name_score_list.take(sortx, axis=0)
        sorted_nids = cm.unique_nids.take(sortx, axis=0)
        return sorted_nids, sorted_name_scores

    def get_num_matches_list(cm):
        num_matches_list = list(map(len, cm.fm_list))
        return num_matches_list

    def get_name_shortlist_aids(cm, nNameShortList, nAnnotPerName):
        """
        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> ibs, qreq_, cm_list = plh.testdata_pre_sver('PZ_MTEST', qaid_list=[18])
            >>> cm = cm_list[0]
            >>> cm.score_nsum(qreq_)
            >>> top_daids = cm.get_name_shortlist_aids(5, 2)
            >>> assert cm.qnid in ibs.get_annot_name_rowids(top_daids)
        """
        top_daids = scoring.get_name_shortlist_aids(
            cm.daid_list, cm.dnid_list, cm.annot_score_list,
            cm.name_score_list, cm.nid2_nidx, nNameShortList, nAnnotPerName)
        return top_daids

    def get_chip_shortlist_aids(cm, num_shortlist):
        """
        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> ibs, qreq_, cm_list = plh.testdata_pre_sver('PZ_MTEST', qaid_list=[18])
            >>> cm = cm_list[0]
            >>> cm.score_nsum(qreq_)
            >>> top_daids = cm.get_chip_shortlist_aids(5 * 2)
            >>> assert cm.qnid in ibs.get_annot_name_rowids(top_daids)
        """
        sortx = np.array(cm.annot_score_list).argsort()[::-1]
        topx = sortx[:min(num_shortlist, len(sortx))]
        top_daids = cm.daid_list[topx]
        return top_daids

    def get_ranked_nids_and_aids(cm):
        """ Hacky func

        Returns:
            ibeis.algo.hots.name_scoring.NameScoreTup
        """
        sortx = cm.name_score_list.argsort()[::-1]
        sorted_name_scores = cm.name_score_list.take(sortx, axis=0)
        sorted_nids = cm.unique_nids.take(sortx, axis=0)
        sorted_groupxs = ut.take(cm.name_groupxs, sortx)
        sorted_daids = vt.apply_grouping(cm.daid_list,  sorted_groupxs)
        sorted_annot_scores = vt.apply_grouping(cm.annot_score_list,  sorted_groupxs)
        # do subsorting
        subsortx_list = [scores.argsort()[::-1] for scores in sorted_annot_scores]
        subsorted_daids = vt.ziptake(sorted_daids, subsortx_list)
        subsorted_annot_scores = vt.ziptake(sorted_annot_scores, subsortx_list)
        nscoretup = name_scoring.NameScoreTup(sorted_nids, sorted_name_scores,
                                              subsorted_daids,
                                              subsorted_annot_scores)
        return nscoretup

    @property
    def num_daids(cm):
        return None if cm.daid_list is None else len(cm.daid_list)

    @property
    def ranks(cm):
        sortx = cm.argsort()
        return sortx.argsort()

    @property
    def unique_name_ranks(cm):
        sortx = cm.name_argsort()
        return sortx.argsort()

    def argsort(cm):
        assert cm.score_list is not None, 'no annot scores computed'
        sortx = np.argsort(cm.score_list)[::-1]
        return sortx

    def name_argsort(cm):
        assert cm.name_score_list is not None, 'no name scores computed'
        return np.argsort(cm.name_score_list)[::-1]


class AnnotMatch(MatchBaseIO, ut.NiceRepr, _BaseVisualization, _AnnotMatchConvenienceGetter):
    """
    This implements part the match between whole annotations and the other
    annotaions / names. This does not include algorithm specific feature
    matches.
    """

    _attr_names = [
        'qaid',
        'qnid',
        'daid_list',
        'dnid_list',
        'H_list',
        'score_list',
        'annot_score_list',
        'unique_nids',
        'name_score_list',
    ]

    def __init__(cm, *args, **kwargs):
        cm.qaid = None
        cm.qnid = None
        cm.daid_list  = None
        # This is aligned with daid list, do not confuse with unique_nids
        cm.dnid_list  = None
        cm.H_list     = None
        cm.score_list = None
        # standard groupings
        # TODO: rename unique_nids to indicate it is aligned with name_groupxs
        # Annot scores
        cm.annot_score_list = None
        # Name scores
        cm.unique_nids = None  # belongs to name_groupxs
        cm.name_score_list = None
        # TODO: have subclass or dict for special scores
        # Special annot scores
        cm.special_annot_scores = [
            'csum',
            'acov',
        ]
        for score_method in cm.special_annot_scores:
            setattr(cm, score_method + '_score_list', None)
        #cm.csum_score_list = None
        #cm.acov_score_list = None
        # Special name scores
        cm.special_name_scores = [
            'nsum',
            'maxcsum',
            'ncov',
        ]
        # TODO: use a dictionary instaed of attrs
        for score_method in cm.special_name_scores:
            setattr(cm, score_method + '_score_list', None)
        #cm.nsum_score_list = None
        #cm.maxcsum_score_list = None
        #cm.ncov_score_list = None
        # Re-evaluatables (for convinience only)
        cm.daid2_idx = None  # maps onto cm.daid_list
        cm.nid2_nidx = None  # maps onto cm.unique_nids
        cm.name_groupxs = None

    def __nice__(cm):
        return 'qaid=%s nD=%s' % (cm.qaid, cm.num_daids)

    def initialize(cm, qaid=None, daid_list=None, score_list=None,
                   dnid_list=None, qnid=None,
                   unique_nids=None, name_score_list=None,
                   annot_score_list=None, autoinit=True):
        """
        qaid and daid_list are not optional. fm_list and fsv_list are strongly
        encouraged and will probalby break things if they are not there.
        """
        cm.qaid         = qaid
        cm.daid_list    = safeop(np.array, daid_list, dtype=hstypes.INDEX_TYPE)
        cm.score_list   = safeop(np.array, score_list, dtype=hstypes.FLOAT_TYPE)
        # name info
        cm.qnid = qnid
        cm.dnid_list = safeop(np.array, dnid_list, dtype=hstypes.INDEX_TYPE)
        cm.unique_nids = safeop(np.array, unique_nids, dtype=hstypes.INDEX_TYPE)
        cm.name_score_list = safeop(np.array, name_score_list, dtype=hstypes.FLOAT_TYPE)
        cm.annot_score_list = safeop(np.array, annot_score_list, dtype=hstypes.FLOAT_TYPE)

        # TODO: have subclass or dict for special scores
        if autoinit:
            cm._update_daid_index()
            if cm.dnid_list is not None:
                cm._update_unique_nid_index()
            if DEBUG_CHIPMATCH:
                cm.assert_self(verbose=True)

    def to_dict(cm, ibs=None):
        class_dict = cm.__getstate__()
        if ibs is not None:
            assert ibs is not None, 'need ibs to convert uuids'
            class_dict['dannot_uuid_list'] = ibs.get_annot_uuids(cm.daid_list)
            class_dict['dname_list'] = ibs.get_name_texts(cm.dnid_list)
            class_dict['qannot_uuid'] = ibs.get_annot_uuids(cm.qaid)
            class_dict['qname'] = ibs.get_name_texts(cm.qnid)
        return class_dict

    @classmethod
    def from_dict(cls, class_dict, ibs=None):
        r"""
        Convert dict of arguments back to ChipMatch object
        """

        key_list = ut.get_kwargs(cls.initialize)[0]  # HACKY
        key_list.remove('autoinit')
        if ut.VERBOSE:
            other_keys = list(set(class_dict.keys()) - set(key_list))
            if len(other_keys) > 0:
                print('Not unserializing extra attributes: %s' % (
                    ut.list_str(other_keys)))

        if ibs is not None:
            class_dict = prepare_dict_uuids(class_dict, ibs)

        dict_subset = ut.dict_subset(class_dict, key_list)
        dict_subset['score_list'] = convert_numpy(dict_subset['score_list'],
                                                  hstypes.FS_DTYPE)

        cm = cls()
        cm.initialize(**dict_subset)
        return cm

    def _update_daid_index(cm):
        """
        Rebuilds inverted index from aid to internal index
        """
        cm.daid2_idx = safeop(ut.make_index_lookup, cm.daid_list)

    def _update_unique_nid_index(cm):
        """
        Rebuilds inverted index from nid to internal (name) index
        """
        #assert cm.unique_nids is not None
        unique_nids_, name_groupxs_ = vt.group_indices(cm.dnid_list)
        #assert unique_nids_.dtype == hstypes.INTEGER_TYPE
        if cm.unique_nids is None:
            assert cm.name_score_list is None, 'name score is misaligned'
            cm.unique_nids = unique_nids_
        cm.nid2_nidx = ut.make_index_lookup(cm.unique_nids)
        nidx_list = np.array(ut.dict_take(cm.nid2_nidx, unique_nids_))
        inverse_idx_list = nidx_list.argsort()
        cm.name_groupxs = ut.take(name_groupxs_, inverse_idx_list)

    def evaluate_dnids(cm, qreq_=None, ibs=None):
        if qreq_ is not None:
            #cm.qnid = qreq_.qannots.loc([cm.qaid]).nids[0]
            #dnid_list = qreq_.dannots.loc(cm.daid_list).nids
            cm.qnid = qreq_.get_qreq_annot_nids(cm.qaid)
            dnid_list = qreq_.get_qreq_annot_nids(cm.daid_list)
            #ibs = qreq_.ibs
        elif ibs is not None:
            cm.qnid = ibs.get_annot_name_rowids(cm.qaid)
            dnid_list = ibs.get_annot_name_rowids(cm.daid_list)
        else:
            assert False, 'no source of dnids'
        cm.dnid_list = np.array(dnid_list, dtype=hstypes.INDEX_TYPE)
        cm._update_unique_nid_index()

    #------------------
    # State Modification Functions
    #------------------

    # Cannonical Setters

    @profile
    def set_cannonical_annot_score(cm, annot_score_list):
        cm.annot_score_list = annot_score_list
        #cm.name_score_list  = None
        cm.score_list       = annot_score_list

    @profile
    def set_cannonical_name_score(cm, annot_score_list, name_score_list):
        cm.annot_score_list = safeop(np.array, annot_score_list, dtype=hstypes.FLOAT_TYPE)
        cm.name_score_list  = safeop(np.array, name_score_list, dtype=hstypes.FLOAT_TYPE)
        # align with score_list
        cm.score_list = name_scoring.align_name_scores_with_annots(
            cm.annot_score_list, cm.daid_list, cm.daid2_idx, cm.name_groupxs,
            cm.name_score_list)


class _ChipMatchConvenienceGetter(object):

    #------------------
    # Getter Functions
    #------------------

    def get_flat_fm_info(cm, flags=None):
        r"""
        Returns:
            dict: info_

        CommandLine:
            python -m ibeis.algo.hots.chip_match --exec-get_flat_fm_info --show

        Example:
            >>> # DISABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> ibs, qreq_, cm_list = plh.testdata_pre_sver(
            >>>     defaultdb='PZ_MTEST', qaid_list=[18])
            >>> cm = cm_list[0]
            >>> info_ = cm.get_flat_fm_info()
            >>> ut.assert_all_eq(ut.lmap(len, info_.values()))
            >>> result = ('info_ = %s' % (ut.repr3(info_, precision=2),))
            >>> print(result)
        """
        import vtool as vt
        if flags is None:
            flags = [True] * len(cm.daid_list)
            # flags = cm.score_list > 0
        # Compress to desired info
        fsv_list  = ut.compress(cm.fsv_list, flags)
        fm_list   = ut.compress(cm.fm_list, flags)
        daid_list = ut.compress(cm.daid_list, flags)
        # Flatten on a feature level
        len_list = [fm.shape[0] for fm in fm_list]
        info_ = {}
        nfilt = len(cm.fsv_col_lbls)
        info_['fsv'] = vt.safe_cat(fsv_list, axis=0, default_shape=(0, nfilt))
        info_['fm'] = vt.safe_cat(fm_list, axis=0, default_shape=(0, 2),
                                  default_dtype=hstypes.FM_DTYPE)
        info_['aid1'] = np.full(sum(len_list), cm.qaid,
                                dtype=hstypes.INDEX_TYPE)
        info_['aid2'] = vt.safe_cat(
            [np.array([daid] * n, dtype=hstypes.INDEX_TYPE)
             for daid, n in zip(daid_list, len_list)],
            default_shape=(0,), default_dtype=hstypes.INDEX_TYPE)
        return info_

    def get_num_feat_score_cols(cm):
        return len(cm.fsv_col_lbls)

    def get_fsv_prod_list(cm):
        return [fsv.prod(axis=1) for fsv in cm.fsv_list]

    def get_annot_fm(cm, daid):
        idx = ut.dict_take(cm.daid2_idx, daid)
        fm  = ut.take(cm.fm_list, idx)
        return fm

    def get_fs_list(cm, colx=None, col=None):
        assert xor(colx is None, col is None)
        if col is not None:
            colx = cm.fsv_col_lbls.index(col)
        fs_list = [fsv.T[colx].T for fsv in cm.fsv_list]
        return fs_list

    @property
    def qfxs_list(cm):
        return [fm.T[0] for fm in cm.fm_list]

    @property
    def dfxs_list(cm):
        return [fm.T[1] for fm in cm.fm_list]

    @property
    def nfxs_list(cm):
        nfxs_list = cm.filtnorm_fxs[0]
        return nfxs_list

    @property
    def naids_list(cm):
        naids_list = cm.filtnorm_aids[0]
        return naids_list


class _ChipMatchDebugger(object):
    #------------------
    # String Functions
    #------------------

    def print_inspect_str(cm, qreq_):
        print(cm.get_inspect_str(qreq_))

    def print_rawinfostr(cm):
        print(cm.get_rawinfostr())

    def print_csv(cm, *args, **kwargs):
        print(cm.get_cvs_str(*args, **kwargs))

    def inspect_difference(cm, other):
        print('Checking difference')
        raw_infostr1 = cm.get_rawinfostr(colored=False)
        raw_infostr2 = other.get_rawinfostr(colored=False)
        difftext = ut.get_textdiff(raw_infostr1, raw_infostr2, num_context_lines=4)
        if len(difftext) == 0:
            print('no difference')
            return True
        else:
            ut.print_difftext(difftext)
            return False

    def get_inspect_str(cm, qreq_):
        r"""
        Args:
            qreq_ (QueryRequest):  query request object with hyper-parameters

        Returns:
            str: varinfo

        CommandLine:
            python -m ibeis.algo.hots.chip_match --exec-get_inspect_str

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> cm, qreq_ = ibeis.testdata_cm('PZ_MTEST', a='default:dindex=0:10,qindex=0:1', t='best:SV=False')
            >>> varinfo = cm.get_inspect_str(qreq_)
            >>> result = ('varinfo = %s' % (str(varinfo),))
            >>> print(result)
        """
        #cm.assert_self(qreq_)

        top_lbls = [' top aids', ' scores', ' ranks']

        ibs = qreq_.ibs

        top_aids   = np.array(cm.get_top_aids(6), dtype=np.int32)
        top_scores = np.array(cm.get_annot_scores(top_aids), dtype=np.float64)
        #top_rawscores = np.array(cm.get_aid_scores(top_aids, rawscore=True), dtype=np.float64)
        top_ranks  = np.arange(len(top_aids))
        top_list   = [top_aids, top_scores, top_ranks]

        top_lbls += [' isgt']
        istrue = ibs.get_aidpair_truths([cm.qaid] * len(top_aids), top_aids)
        top_list.append(np.array(istrue, dtype=np.int32))

        top_lbls = ['top nid'] + top_lbls
        top_list = [ibs.get_annot_name_rowids(top_aids)] + top_list

        top_stack = np.vstack(top_list)
        #top_stack = np.array(top_stack, dtype=object)
        top_stack = np.array(top_stack, dtype=np.float)
        #np.int32)
        top_str = np.array_str(top_stack, precision=3, suppress_small=True, max_line_width=200)

        top_lbl = '\n'.join(top_lbls)
        inspect_list = ['QueryResult', qreq_.get_cfgstr(), ]
        if ibs is not None:
            gt_aids = cm.get_top_gt_aids(qreq_.ibs)
            gt_ranks  = cm.get_annot_ranks(gt_aids)
            gt_scores = cm.get_annot_scores(gt_aids)
            inspect_list.append('len(cm.daid_list) = %r' % len(cm.daid_list))
            inspect_list.append('len(cm.unique_nids) = %r' % len(cm.unique_nids))
            inspect_list.append('gt_ranks = %r' % gt_ranks)
            inspect_list.append('gt_aids = %r' % gt_aids)
            inspect_list.append('gt_scores = %r' % gt_scores)

        inspect_list.extend([
            'qaid=%r ' % cm.qaid,
            'qnid=%r ' % cm.qnid,
            ut.hz_str(top_lbl, ' ', top_str),
            #'num feat matches per annotation stats:',
            #ut.indent(ut.dict_str(nFeatMatch_stats)),
            #ut.indent(nFeatMatch_stats_str),
        ])

        inspect_str = '\n'.join(inspect_list)

        #inspect_str = ut.indent(inspect_str, '[INSPECT] ')
        return inspect_str

    def get_rawinfostr(cm, colored=None):
        r"""
        Returns:
            str: varinfo

        CommandLine:
            python -m ibeis.algo.hots.chip_match --exec-get_rawinfostr --show --cex

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> cm, qreq_ = ibeis.testdata_cm('PZ_MTEST', a='default:dindex=0:10,qindex=0:1', t='best:SV=False')
            >>> varinfo = cm.get_rawinfostr()
            >>> result = ('varinfo = %s' % (varinfo,))
            >>> print(result)
        """
        def varinfo(varname, onlyrepr=False, canshowrepr=True, cm=cm, varcolor='yellow'):
            varval = getattr(cm, varname.replace('cm.', ''))
            varinfo_list = []
            print_summary = not onlyrepr and ut.isiterable(varval)
            show_repr = True
            show_repr = show_repr or (onlyrepr or not print_summary)
            symbol = '*'
            if colored is not False and ut.util_dbg.COLORED_EXCEPTIONS:
                varname = ut.color_text(varname, varcolor)
            if show_repr:
                varval_str = ut.repr2(varval, precision=2)
                if len(varval_str) > 100:
                    varval_str = '<omitted>'
                varval_str = ut.truncate_str(varval_str, maxlen=50)
                varinfo_list += ['    * %s = %s' % (varname, varval_str)]
                symbol = '+'
            if print_summary:
                depth = ut.depth_profile(varval)
                if not show_repr:
                    varinfo_list += [
                        # '    %s varinfo(%s):' % (symbol, varname,),
                        '    %s %s = <not shown!>' % (symbol, varname,),
                    ]
                varinfo_list += [
                    '          len = %r' % (len(varval),)]
                if depth != len(varval):
                    depth_str = ut.truncate_str(str(depth), maxlen=70)
                    varinfo_list += [
                        '          depth = %s' % (depth_str,)]
                varinfo_list += [
                    '          types = %s' % (ut.list_type_profile(varval),)]
                #varinfo = '\n'.join(ut.align_lines(varinfo_list, '='))
            aligned_varinfo_list = ut.align_lines(varinfo_list, '=')
            varinfo = '\n'.join(aligned_varinfo_list)
            return varinfo
        str_list = []
        append = str_list.append
        attr_order = [
            'cm.qaid',
            'cm.qnid',
            'cm.unique_nids',
            'cm.daid_list',
            'cm.dnid_list',
            'cm.fs_list',
            'cm.fm_list',
            'cm.fk_list',
            'cm.fsv_list',
            'cm.fsv_col_lbls',
            'cm.filtnorm_aids',
            'cm.filtnorm_fxs',
            'cm.H_list',
            'cm.score_list',
            'cm.annot_score_list',
            'cm.csum_score_list',
            'cm.acov_score_list',
            'cm.name_score_list',
            'cm.nsum_score_list',
            'cm.ncov_score_list',
            'cm.nid2_nidx',
            'cm.daid2_idx',
        ]
        attrs_ = [attr.replace('cm.', '') for attr in attr_order]
        unspecified_attrs = ut.setdiff(cm.__dict__.keys(), attrs_)

        append('ChipMatch:')
        for attr in attr_order:
            append(varinfo(attr))
        for attr in unspecified_attrs:
            append(varinfo(attr, varcolor='red'))
        infostr = '\n'.join(str_list)
        return infostr

    def get_cvs_str(cm,  numtop=6, ibs=None, sort=True):
        r"""
        Args:
            numtop (int): (default = 6)
            ibs (IBEISController):  ibeis controller object(default = None)
            sort (bool): (default = True)

        Returns:
            str: csv_str

        Notes:
            Very weird that it got a score
            qaid 6 vs 41 has
                [72, 79, 0, 17, 6, 60, 15, 36, 63]
                [72, 79, 0, 17, 6, 60, 15, 36, 63]
                [72, 79, 0, 17, 6, 60, 15, 36, 63]
                [0.060, 0.053, 0.0497, 0.040, 0.016, 0, 0, 0, 0]
                [7, 40, 41, 86, 103, 88, 8, 101, 35]
            makes very little sense

        CommandLine:
            python -m ibeis.algo.hots.chip_match --test-get_cvs_str --force-serial

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> ibs, qreq_, cm_list = plh.testdata_post_sver()
            >>> cm = cm_list[0]
            >>> numtop = 6
            >>> ibs = None
            >>> sort = True
            >>> csv_str = cm.get_cvs_str(numtop, ibs, sort)
            >>> result = ('csv_str = \n%s' % (str(csv_str),))
            >>> print(result)
        """
        if not sort or cm.score_list is None:
            if sort:
                print('Warning: cm.score_list is None and sort is True')
            sortx = list(range(len(cm.daid_list)))
        else:
            sortx = ut.list_argsort(cm.score_list, reverse=True)
        if ibs is not None:
            qnid = ibs.get_annot_nids(cm.qaid)
            dnid_list = ibs.get_annot_nids(cm.daid_list)
        else:
            qnid = cm.qnid
            dnid_list = cm.dnid_list
        # Build columns for the csv, filtering out unavailable information
        column_lbls_ = ['daid', 'dnid', 'score', 'num_matches', 'annot_scores',
                        'fm_depth', 'fsv_depth']
        column_list_ = [
            vt.list_take_(cm.daid_list,  sortx),
            None if dnid_list is None else vt.list_take_(dnid_list, sortx),
            None if cm.score_list is None else vt.list_take_(cm.score_list, sortx),
            vt.list_take_(cm.get_num_matches_list(), sortx),
            None if cm.annot_score_list is None else vt.list_take_(cm.annot_score_list, sortx),
            #None if cm.name_score_list is None else vt.list_take_(cm.name_score_list, sortx),
            ut.lmap(str, ut.depth_profile(vt.list_take_(cm.fm_list,  sortx))),
            ut.lmap(str, ut.depth_profile(vt.list_take_(cm.fsv_list, sortx))),
        ]
        isnone_list = ut.flag_None_items(column_list_)
        column_lbls = ut.filterfalse_items(column_lbls_, isnone_list)
        column_list = ut.filterfalse_items(column_list_, isnone_list)
        # Clip to the top results
        if numtop is not None:
            column_list = [ut.listclip(col, numtop) for col in column_list]
        # hard case for python text parsing
        # better know about quoted hash symbols
        header = ut.codeblock(
            '''
            # qaid = {qaid}
            # qnid = {qnid}
            # fsv_col_lbls = {fsv_col_lbls}
            '''
        ).format(qaid=cm.qaid, qnid=qnid, fsv_col_lbls=cm.fsv_col_lbls)

        csv_str = ut.make_csv_table(column_list, column_lbls, header, comma_repl=';')
        return csv_str

    #------------------
    # Testing Functions
    #------------------

    def assert_self(cm, qreq_=None, ibs=None, strict=False, assert_feats=True,
                    verbose=ut.NOT_QUIET):
        # return list1_ is None or len(list1_) == len(list2_)
        try:
            assert cm.qaid is not None, 'must have qaid'
            assert cm.daid_list is not None, 'must give daids'
            _assert_eq_len(cm.fm_list, cm.daid_list)
            _assert_eq_len(cm.fsv_list, cm.daid_list)
            _assert_eq_len(cm.fk_list, cm.daid_list)
            _assert_eq_len(cm.H_list, cm.daid_list)
            _assert_eq_len(cm.score_list, cm.daid_list)
            _assert_eq_len(cm.dnid_list, cm.daid_list)
        except AssertionError as ex:
            cm.print_rawinfostr()
            raise

        if ibs is None and qreq_ is not None:
            ibs = qreq_.ibs

        testlog = TestLogger(verbose=verbose)

        with testlog.context('lookup score by daid'):
            if cm.score_list is None:
                testlog.skip_test()
            else:
                daids = cm.get_top_aids()
                scores = cm.get_top_scores()
                scores_ = cm.get_annot_scores(daids)
                if not np.all(scores == scores_):
                    testlog.log_failed('score mappings are NOT ok')

        with testlog.context('dnid_list = name(daid_list)'):
            if strict or ibs is not None and cm.dnid_list is not None:
                nid_list = ibs.get_annot_name_rowids(cm.daid_list)
                if not np.all(cm.dnid_list == nid_list):
                    testlog.log_failed('annot aligned nids are NOT ok')
            else:
                testlog.skip_test()

        if strict or cm.unique_nids is not None:
            with testlog.context('unique nid mapping'):
                assert cm.nid2_nidx is not None, 'name mappings are not built'
                nidx_list = ut.dict_take(cm.nid2_nidx, cm.unique_nids)
                assert nidx_list == list(range(len(nidx_list)))
                assert np.all(cm.unique_nids[nidx_list] == cm.unique_nids)

            with testlog.context('allsame(grouped(dnid_list))'):
                grouped_nids = vt.apply_grouping(cm.dnid_list, cm.name_groupxs)
                for nids in grouped_nids:
                    if not ut.allsame(nids):
                        testlog.log_failed('internal dnid name grouping is NOT consistent')

            with testlog.context('allsame(name(grouped(daid_list)))'):
                if ibs is None:
                    testlog.skip_test()
                else:
                    # this might fail if this result is old and the names have changed
                    grouped_aids = vt.apply_grouping(cm.daid_list, cm.name_groupxs)
                    grouped_mapped_nids = ibs.unflat_map(
                        ibs.get_annot_name_rowids, grouped_aids)
                    for nids in grouped_mapped_nids:
                        if not ut.allsame(nids):
                            testlog.log_failed(
                                'internal daid name grouping is NOT consistent')

            with testlog.context('dnid_list - unique_nid alignment'):
                grouped_nids = vt.apply_grouping(cm.dnid_list, cm.name_groupxs)
                for nids, nid in zip(grouped_nids, cm.unique_nids):
                    if not np.all(nids == nid):
                        testlog.log_failed(
                            'cm.unique_nids is NOT aligned with '
                            'vt.apply_grouping(cm.dnid_list, cm.name_groupxs). '
                            ' nids=%r, nid=%r' % (nids, nid)
                        )
                        break

            if ibs is not None:
                testlog.start_test('daid_list - unique_nid alignment')
                for nids, nid in zip(grouped_mapped_nids, cm.unique_nids):
                    if not np.all(nids == nid):
                        testlog.log_failed(
                            'cm.unique_nids is NOT aligned with '
                            'vt.apply_grouping(name(cm.daid_list), cm.name_groupxs). '
                            ' name(aids)=%r, nid=%r' % (nids, nid)
                        )
                        break
                testlog.end_test()

        assert len(testlog.failed_list) == 0, '\n'.join(testlog.failed_list)
        testlog.log_passed('lengths are ok')

        try:
            with testlog.context('check fm_shape'):
                if cm.fm_list is None:
                    testlog.skip_test()
                else:
                    assert ut.list_all_eq_to([fm.shape[1] for fm in cm.fm_list], 2), (
                        'fm arrs must be Nx2 dimensions')

            with testlog.context('fsv_col_lbls agree with fsv shape'):
                if cm.fsv_list is None:
                    testlog.skip_test()
                else:
                    if cm.fsv_col_lbls is not None or strict:
                        assert cm.fsv_col_lbls is not None, (
                            'need to specify the names of the columns')
                        num_col_lbls = len(cm.fsv_col_lbls)
                    else:
                        if len(cm.fsv_list) == 0:
                            num_col_lbls = 0
                        else:
                            num_col_lbls = cm.fsv_list[0].shape[1]
                    assert ut.list_all_eq_to(
                        [fsv.shape[1] for fsv in cm.fsv_list], num_col_lbls), (
                            'num_col_lbls=%r' % (num_col_lbls,))

            with testlog.context('filtnorm checks'):
                if cm.filtnorm_aids is None and cm.filtnorm_fxs is None:
                    testlog.skip_test()
                else:
                    with testlog.context('num_col_lbls agree with filtnorm_arrs'):
                        assert len(cm.filtnorm_aids) == num_col_lbls, (
                            'bad len %r != %r' % (len(cm.filtnorm_aids), num_col_lbls))
                        assert len(cm.filtnorm_fxs) == num_col_lbls
                    with testlog.context('len(fsvs) agree with filtnorm_arrs'):
                        assert all([
                            aids_list is None or
                            all([len(fsv) == len(aids)
                                 for aids, fsv in zip(aids_list, cm.fsv_list)])
                            for aids_list in cm.filtnorm_aids
                        ]), 'norm aid indicies do not agree with featscores'
                        assert all([
                            fxs_list is None or
                            all([len(fsv) == len(fxs)
                                 for fxs, fsv in zip(fxs_list, cm.fsv_list)])
                            for fxs_list in cm.filtnorm_fxs
                        ]), 'norm fx indicies do not agree with featscores'
        except Exception as ex:
            cm.print_rawinfostr()
            raise

        # testlog.log_passed('filtkey and fsv shapes are ok')

        if assert_feats and (strict or qreq_ is not None):
            external_qaids = qreq_.qaids.tolist()
            external_daids = qreq_.daids.tolist()
            proot = getattr(qreq_.qparams, 'pipeline_root', None)
            if proot == 'vsone':
                assert len(external_qaids) == 1, 'only one external qaid for vsone'
                if strict or qreq_.indexer is not None:
                    nExternalQVecs = qreq_.ibs.get_annot_vecs(
                        external_qaids[0],
                        config2_=qreq_.extern_query_config2).shape[0]
                    assert qreq_.indexer.idx2_vec.shape[0] == nExternalQVecs, (
                        'did not index query descriptors properly')
                testlog.log_passed('vsone daids are ok are ok')

            nFeats1 = qreq_.ibs.get_annot_num_feats(
                cm.qaid, config2_=qreq_.extern_query_config2)
            nFeats2_list = np.array(
                qreq_.ibs.get_annot_num_feats(
                    cm.daid_list, config2_=qreq_.extern_data_config2))
            if False:
                # This does not need to be the case especially if the daid_list
                # was exteneded
                try:
                    assert ut.list_issubset(cm.daid_list, external_daids), (
                        'cmtup_old must be subset of daids')
                except AssertionError as ex:
                    ut.printex(ex, keys=['daid_list', 'external_daids'])
                    raise
            try:
                fm_list = cm.fm_list
                fx2s_list = [fm_.T[1] for fm_ in fm_list]
                fx1s_list = [fm_.T[0] for fm_ in fm_list]
                max_fx1_list = np.array([
                    -1 if len(fx1s) == 0 else fx1s.max()
                    for fx1s in fx1s_list])
                max_fx2_list = np.array([
                    -1 if len(fx2s) == 0 else fx2s.max()
                    for fx2s in fx2s_list])
                ut.assert_lessthan(max_fx2_list, nFeats2_list,
                                   'max feat index must be less than num feats')
                ut.assert_lessthan(max_fx1_list, nFeats1,
                                   'max feat index must be less than num feats')
            except AssertionError as ex:
                ut.printex(ex, keys=['qaid', 'daid_list', 'nFeats1',
                                     'nFeats2_list', 'max_fx1_list',
                                     'max_fx2_list', ])
                raise
            testlog.log_passed('nFeats are ok in fm')
        else:
            testlog.log_skipped('nFeat check')

        if qreq_ is not None:
            pass


@six.add_metaclass(ut.ReloadingMetaclass)
class ChipMatch(_ChipMatchVisualization,
                AnnotMatch,
                _ChipMatchScorers,
                old_chip_match._OldStyleChipMatchSimulator,
                _ChipMatchConvenienceGetter,
                _ChipMatchDebugger):
    """
    behaves as as the ChipMatchOldTup named tuple until we
    completely replace the old structure
    """

    # Standard Contstructor

    def __init__(cm, *args, **kwargs):
        """
        qaid and daid_list are not optional. fm_list and fsv_list are strongly
        encouraged and will probalby break things if they are not there.

        SeeAlso: initialize
        """
        try:
            super(ChipMatch, cm).__init__(*args, **kwargs)
        except TypeError:
            # Hack for ipython reload
            print('id(cm.__class__) = %r' % (id(cm.__class__),))
            print('id(ChipMatch) = %r' % (id(ChipMatch),))
            #import utool
            #utool.embed()
            #assert id(cm.__class__) > id(ChipMatch)
            super(cm.__class__, cm).__init__(*args, **kwargs)
            if ut.STRICT:
                raise
        cm.fm_list      = None
        cm.fsv_list     = None
        cm.fk_list      = None
        cm.fsv_col_lbls = None
        cm.fs_list      = None
        # Hacks for norm
        cm.filtnorm_aids = None
        cm.filtnorm_fxs = None
        if len(args) + len(kwargs) > 0:
            cm.initialize(*args, **kwargs)

    def initialize(cm, qaid=None, daid_list=None, fm_list=None, fsv_list=None,
                   fk_list=None, score_list=None, H_list=None,
                   fsv_col_lbls=None, dnid_list=None, qnid=None,
                   unique_nids=None, name_score_list=None,
                   annot_score_list=None, autoinit=True,
                   filtnorm_aids=None, filtnorm_fxs=None):
        """
        qaid and daid_list are not optional. fm_list and fsv_list are strongly
        encouraged and will probalby break things if they are not there.
        """
        if DEBUG_CHIPMATCH:
            msg = 'incompatable data'
            assert daid_list is not None, 'must give daids'
            assert fm_list is None or len(fm_list) == len(daid_list), msg
            assert fsv_list is None or len(fsv_list) == len(daid_list), msg
            assert fk_list is None or len(fk_list) == len(daid_list), msg
            assert H_list is None or len(H_list) == len(daid_list), msg
            assert score_list is None or len(score_list) == len(daid_list), msg
            assert dnid_list is None or len(dnid_list) == len(daid_list), msg
        cm.qaid         = qaid
        cm.daid_list    = safeop(np.array, daid_list, dtype=hstypes.INDEX_TYPE)
        cm.score_list   = safeop(np.array, score_list, dtype=hstypes.FLOAT_TYPE)
        cm.H_list       = H_list
        # name info
        cm.qnid = qnid
        cm.dnid_list = safeop(np.array, dnid_list, dtype=hstypes.INDEX_TYPE)
        cm.unique_nids = safeop(np.array, unique_nids, dtype=hstypes.INDEX_TYPE)
        cm.name_score_list = safeop(np.array, name_score_list, dtype=hstypes.FLOAT_TYPE)
        cm.annot_score_list = safeop(np.array, annot_score_list, dtype=hstypes.FLOAT_TYPE)

        cm.fm_list  = fm_list
        cm.fsv_list = fsv_list
        cm.fk_list  = (fk_list if fk_list is not None else
                       [np.zeros(fm.shape[0]) for fm in cm.fm_list]
                       if cm.fm_list is not None else None)
        cm.fsv_col_lbls = fsv_col_lbls
        # HACKY normalizer info
        cm.filtnorm_aids = filtnorm_aids
        cm.filtnorm_fxs = filtnorm_fxs
        # TODO: have subclass or dict for special scores
        if autoinit:
            cm._update_daid_index()
            if cm.dnid_list is not None:
                cm._update_unique_nid_index()
            if DEBUG_CHIPMATCH:
                cm.assert_self(verbose=True)

    def arraycast_self(cm):
        """
        Ensures internal structure is in numpy array formats
        TODO: come up with better name
        Remove old initialize method and rename to initialize?
        """
        cm.daid_list    = safeop(np.array, cm.daid_list,  dtype=hstypes.INDEX_TYPE)
        cm.score_list   = safeop(np.array, cm.score_list, dtype=hstypes.FLOAT_TYPE)
        # name info
        cm.dnid_list        = safeop(np.array, cm.dnid_list,        dtype=hstypes.INDEX_TYPE)
        cm.unique_nids      = safeop(np.array, cm.unique_nids,      dtype=hstypes.INDEX_TYPE)
        cm.name_score_list  = safeop(np.array, cm.name_score_list,  dtype=hstypes.FLOAT_TYPE)
        cm.annot_score_list = safeop(np.array, cm.annot_score_list, dtype=hstypes.FLOAT_TYPE)

        ncols = None if cm.fsv_col_lbls is None else len(cm.fsv_col_lbls)

        cm.H_list   = safecast_numpy_lists(cm.H_list,   dtype=hstypes.FLOAT_TYPE)
        cm.fm_list  = safecast_numpy_lists(cm.fm_list,  dtype=hstypes.INDEX_TYPE, dims=(None, 2))
        cm.fsv_list = safecast_numpy_lists(cm.fsv_list, dtype=hstypes.FLOAT_TYPE, dims=(None, ncols))
        cm.fk_list  = safecast_numpy_lists(cm.fk_list,  dtype=hstypes.INDEX_TYPE)

    def _empty_hack(cm):
        if cm.daid_list is None:
            cm.daid_list = np.empty(0, dtype=np.int)
        assert len(cm.daid_list) == 0
        cm.fsv_col_lbls = []
        cm.fm_list = []
        cm.fsv_list = []
        cm.fk_list = []
        cm.H_list = []
        cm.daid2_idx = {}
        cm.fs_list = []
        cm.dnid_list = np.empty(0, dtype=hstypes.INDEX_TYPE)
        cm.unique_nids = np.empty(0, dtype=hstypes.INDEX_TYPE)
        cm.score_list = np.empty(0)
        cm.name_score_list = np.empty(0)
        cm.annot_score_list = np.empty(0)

    def __eq__(cm, other):
        # if isinstance(other, cm.__class__):
        try:
            flag = True
            flag &= len(cm.fm_list) == len(other.fm_list)
            flag &= cm.qaid == other.qaid
            flag &= cm.qnid == other.qnid
            flag &= check_arrs_eq(cm.fm_list, other.fm_list)
            flag &= check_arrs_eq(cm.fs_list, other.fs_list)
            flag &= check_arrs_eq(cm.fk_list, other.fk_list)
            flag &= check_arrs_eq(cm.daid_list, other.daid_list)
            flag &= check_arrs_eq(cm.dnid_list, other.dnid_list)
            flag &= check_arrs_eq(cm.unique_nids, other.unique_nids)
            return flag
        except AttributeError:
            return False
        # else:
        #     return False

    #------------------
    # Modification / Evaluation Functions
    #------------------

    def _cast_scores(cm, dtype=np.float):
        cm.fsv_list = [fsv.astype(dtype) for fsv in cm.fsv_list]

    def extend_results(cm, qreq_, other_aids=None):
        """
        Return a new ChipMatch containing empty data for an extended set of
        aids

        Args:
            qreq_ (ibeis.QueryRequest):  query request object with hyper-parameters
            other_aids (None): (default = None)

        Returns:
            ibeis.ChipMatch: out

        CommandLine:
            python -m ibeis.algo.hots.chip_match --exec-extend_results --show

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> import ibeis
            >>> cm, qreq_ = ibeis.testdata_cm('PZ_MTEST',
            >>>                               a='default:dindex=0:10,qindex=0:1',
            >>>                               t='best:SV=False')
            >>> assert len(cm.daid_list) == 9
            >>> cm.assert_self(qreq_)
            >>> other_aids = qreq_.ibs.get_valid_aids()
            >>> out = cm.extend_results(qreq_, other_aids)
            >>> assert len(out.daid_list) == 118
            >>> out.assert_self(qreq_)
        """
        if other_aids is None:
            other_aids = qreq_.daids
        ibs = qreq_.ibs
        other_aids_ = other_aids
        other_aids_ = np.setdiff1d(other_aids_, cm.daid_list)
        other_aids_ = np.setdiff1d(other_aids_, [cm.qaid])
        other_nids_ = ibs.get_annot_nids(other_aids_)
        other_unique_nids = np.setdiff1d(np.unique(other_nids_),
                                         cm.unique_nids)
        num = len(other_aids_)
        num2 = len(other_unique_nids)

        daid_list = np.append(cm.daid_list, other_aids_)
        dnid_list = np.append(cm.dnid_list, other_nids_)

        score_list = extend_scores(cm.score_list, num)
        annot_score_list = extend_scores(cm.annot_score_list, num)

        unique_nids  = np.append(cm.unique_nids, other_unique_nids)
        name_score_list = extend_scores(cm.name_score_list, num2)

        qaid         = cm.qaid
        qnid         = cm.qnid
        fsv_col_lbls = cm.fsv_col_lbls

        # <feat correspondence>
        nVs = 0 if fsv_col_lbls is None else len(fsv_col_lbls)

        fm_list  = extend_nplists(cm.fm_list, num, (0, 2), hstypes.FM_DTYPE)
        fk_list  = extend_nplists(cm.fk_list, num, (0), hstypes.FK_DTYPE)
        fs_list  = extend_nplists(cm.fs_list, num, (0), hstypes.FS_DTYPE)
        fsv_list = extend_nplists(cm.fsv_list, num, (0, nVs), hstypes.FS_DTYPE)
        H_list   = extend_pylist(cm.H_list, num, None)

        filtnorm_aids = filtnorm_op(cm.filtnorm_aids, extend_nplists, num, (0),
                                    hstypes.INDEX_TYPE)
        filtnorm_fxs = filtnorm_op(cm.filtnorm_fxs, extend_nplists, num, (0),
                                   hstypes.INDEX_TYPE)
        # </feat correspondence>

        out = ChipMatch(
            qaid, daid_list, fm_list, fsv_list, fk_list, score_list, H_list,
            fsv_col_lbls, dnid_list, qnid, unique_nids, name_score_list,
            annot_score_list, filtnorm_fxs=filtnorm_fxs,
            filtnorm_aids=filtnorm_aids, autoinit=False)
        out.fs_list = fs_list
        # attrs should be dicts
        for key in cm.algo_annot_scores.keys():
            out.algo_annot_scores[key] = extend_scores(cm.algo_annot_scores[key], num)
        for key in cm.algo_name_scores.keys():
            out.algo_name_scores[key] = extend_scores(cm.algo_name_scores[key], num2)
        out._update_daid_index()
        out._update_unique_nid_index()
        return out

    @classmethod
    def combine_cms(cls, cm_list):
        """
        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.core_annots import *  # NOQA
            >>> ibs, depc, aid_list = testdata_core(size=4)
            >>> request = depc.new_request('vsone', [1], [2, 3, 4], {'dim_size': 450})
            >>> rawres_list2 = request.execute(postprocess=False)
            >>> cm_list = ut.take_column(rawres_list2, 1)
            >>> cls = ChipMatch
            >>> out = ChipMatch.combine_cms(cm_list)
            >>> out.score_nsum(request)
            >>> ut.quit_if_noshow()
            >>> out.ishow_analysis(request)
            >>> ut.show_if_requested()
        """
        new_attrs = {}
        common_attrs = [
            'qaid', 'qnid', 'fsv_col_lbls'
        ]
        for attr in common_attrs:
            values = ut.list_getattr(cm_list, 'qaid')
            assert ut.allsame(values)
            new_attrs[attr] = values[0]
        # assumes disjoint
        attrs = [
            'daid_list',
            'dnid_list',
            'score_list',
            'annot_score_list',
            'H_list',
            'fm_list',
            'fsv_list',
            'fk_list',
            'filtnorm_aids',
            'filtnorm_fxs',
        ]
        new_attrs['qaid'] = cm_list[0].qaid
        new_attrs['qnid'] = cm_list[0].qnid
        new_attrs['fsv_col_lbls'] = cm_list[0].fsv_col_lbls
        for attr in attrs:
            values = ut.list_getattr(cm_list, attr)
            if ut.list_all_eq_to(values, None):
                new_attrs[attr] = None
            else:
                new_attrs[attr] = ut.flatten(values)
        out = cls(**new_attrs)
        out._update_daid_index()
        out._update_unique_nid_index()
        return out

    def take_annots(cm, idx_list, inplace=False, keepscores=True):
        """
        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> cm, qreq_ = ibeis.testdata_cm('PZ_MTEST',
            >>>                               a='default:dindex=0:10,qindex=0:1',
            >>>                               t='best:sv=false')
            >>> idx_list = list(range(cm.num_daids))
            >>> inplace = False
            >>> keepscores = True
            >>> other = out = cm.take_annots(idx_list, inplace, keepscores)
            >>> result = ('out = %s' % (ut.repr2(out),))
            >>> assert cm.inspect_difference(out), 'should be no difference'
            >>> print(result)

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> cm, qreq_ = ibeis.testdata_cm('PZ_MTEST',
            >>>                               a='default:dindex=0:10,qindex=0:1',
            >>>                               t='best:SV=False')
            >>> idx_list = [0, 2]
            >>> inplace = False
            >>> keepscores = True
            >>> other = out = cm.take_annots(idx_list, inplace, keepscores)
            >>> result = ('out = %s' % (ut.repr2(out),))
            >>> print(result)
        """
        if inplace:
            out = cm
        else:
            out = ChipMatch(qaid=cm.qaid, qnid=cm.qnid,
                            fsv_col_lbls=cm.fsv_col_lbls)

        out.daid_list     = vt.take2(cm.daid_list, idx_list)
        out.dnid_list     = safeop(vt.take2, cm.dnid_list, idx_list)
        out.H_list        = safeop(ut.take, cm.H_list, idx_list)
        out.fm_list       = safeop(ut.take, cm.fm_list, idx_list)
        out.fsv_list      = safeop(ut.take, cm.fsv_list, idx_list)
        out.fk_list       = safeop(ut.take, cm.fk_list, idx_list)
        out.filtnorm_aids = filtnorm_op(cm.filtnorm_aids, ut.take, idx_list)
        out.filtnorm_fxs  = filtnorm_op(cm.filtnorm_fxs, ut.take, idx_list)

        if keepscores:
            # Annot Scores
            out.score_list = safeop(vt.take2, cm.score_list, idx_list)
            out.annot_score_list = safeop(vt.take2, cm.annot_score_list, idx_list)
            for key in out.algo_annot_scores.keys():
                out.algo_annot_scores[key] = safeop(vt.take2, cm.algo_annot_scores[key], idx_list)

            # Name Scores
            # TODO; remove score of names that were removed?
            out.nid2_nidx = cm.nid2_nidx
            out.unique_nids = cm.unique_nids
            out.name_score_list = cm.name_score_list
            for key in out.algo_name_scores.keys():
                out.algo_name_scores[key] = cm.algo_name_scores[key]
        out._update_daid_index()
        out._update_unique_nid_index()
        return out

    def take_feature_matches(cm, indicies_list, inplace=False, keepscores=True):
        r"""
        Removes outlier feature matches
        TODO: rectify with shortlist_subset

        Args:
            indicies_list (list): list of lists of indicies to keep.
                    if an item is None, the match to the corresponding daid is
                    removed.
            inplace (bool): (default = False)

        Returns:
            ibeis.ChipMatch: out

        CommandLine:
            python -m ibeis.algo.hots.chip_match --exec-take_feature_matches --show

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> cm, qreq_ = ibeis.testdata_cm('PZ_MTEST', a='default:dindex=0:10,qindex=0:1', t='best:SV=False')
            >>> indicies_list = [list(range(i + 1)) for i in range(cm.num_daids)]
            >>> inplace = False
            >>> keepscores = True
            >>> out = cm.take_feature_matches(indicies_list, inplace, keepscores)
            >>> assert not cm.inspect_difference(out), 'should be different'
            >>> result = ('out = %s' % (ut.repr2(out),))
            >>> print(result)
        """
        assert len(indicies_list) == len(cm.daid_list), 'must correspond to daids'

        flags = ut.flag_not_None_items(indicies_list)

        # Remove disgarded matches
        out = cm.compress_annots(flags, inplace=inplace, keepscores=keepscores)
        indicies_list2 = ut.compress(indicies_list, flags)

        out.fm_list = safeop(vt.ziptake, out.fm_list, indicies_list2, axis=0)
        out.fs_list = safeop(vt.ziptake, out.fs_list, indicies_list2, axis=0)
        out.fsv_list = safeop(vt.ziptake, out.fsv_list, indicies_list2, axis=0)
        out.fk_list = safeop(vt.ziptake, out.fk_list, indicies_list2, axis=0)

        out.filtnorm_aids = filtnorm_op(out.filtnorm_aids, vt.ziptake, indicies_list2, axis=0)
        out.filtnorm_fxs = filtnorm_op(out.filtnorm_fxs, vt.ziptake, indicies_list2, axis=0)

        # out.assert_self(verbose=False)
        return out

    def shortlist_subset(cm, top_aids):
        """ returns a new cmtup_old with only the requested daids
        TODO: rectify with take_feature_matches
        """
        idx_list = ut.dict_take(cm.daid2_idx, top_aids)
        out = cm.take_annots(idx_list, keepscores=False)
        return out

    def compress_annots(cm, flags, inplace=False, keepscores=True):
        idx_list = np.where(flags)[0]
        out = cm.take_annots(idx_list, inplace, keepscores)
        return out

    def append_featscore_column(cm, filtkey, filtweight_list, inplace=True):
        assert inplace, 'this is always inplace right now'
        assert filtkey not in cm.fsv_col_lbls, 'already have filtkey=%r' % (cm.filtkey,)
        cm.fsv_col_lbls.append(filtkey)
        cm.fsv_list = vt.zipcat(cm.fsv_list, filtweight_list, axis=1)

    def compress_top_feature_matches(cm, num=10, rng=np.random, use_random=True):
        """
        DO NOT USE

        FIXME: Use boolean lists

        Removes all but the best feature matches for testing purposes
        rng = np.random.RandomState(0)
        """
        #num = 10
        fs_list = cm.get_fsv_prod_list()
        score_sortx = [fs.argsort()[::-1] for fs in fs_list]
        if use_random:
            # keep jagedness
            score_sortx_filt = [
                sortx[0:min(rng.randint(num // 2, num), len(sortx))]
                for sortx in score_sortx]
        else:
            score_sortx_filt = [sortx[0:min(num, len(sortx))]
                                for sortx in score_sortx]

        # cm.take_feature_matches()

        cm.fsv_list = vt.ziptake(cm.fsv_list, score_sortx_filt, axis=0)
        cm.fm_list = vt.ziptake(cm.fm_list, score_sortx_filt, axis=0)
        cm.fk_list = vt.ziptake(cm.fk_list, score_sortx_filt, axis=0)
        if cm.fs_list is not None:
            cm.fs_list = vt.ziptake(cm.fs_list, score_sortx_filt, axis=0)
        cm.H_list = None
        cm.fs_list = None

    def sortself(cm):
        """ reorders the internal data using cm.score_list """
        print('Warning using sortself')
        sortx = cm.argsort()
        cm.daid_list = vt.trytake(cm.daid_list, sortx)
        cm.dnid_list = vt.trytake(cm.dnid_list, sortx)
        cm.fm_list = vt.trytake(cm.fm_list, sortx)
        cm.fsv_list = vt.trytake(cm.fsv_list, sortx)
        cm.fs_list = vt.trytake(cm.fs_list, sortx)
        cm.fk_list = vt.trytake(cm.fk_list, sortx)
        cm.score_list = vt.trytake(cm.score_list, sortx)
        # FIXME: Not all properties covered
        cm.algo_annot_scores['csum'] = vt.trytake(cm.algo_annot_scores['csum'], sortx)
        cm.H_list = vt.trytake(cm.H_list, sortx)
        cm._update_daid_index()

    # ---

    # Alternative Cosntructors / Convertors

    @classmethod
    @profile
    def from_unscored(cls, prior_cm, fm_list, fs_list, H_list=None,
                      fsv_col_lbls=None):
        qaid = prior_cm.qaid
        daid_list = prior_cm.daid_list
        fsv_list = matching.ensure_fsv_list(fs_list)
        if fsv_col_lbls is None:
            fsv_col_lbls = ['unknown']
            #fsv_col_lbls = [str(count) for count in range(num_cols)]
            #fsv_col_lbls
        #score_list = [fsv.prod(axis=1).sum() for fsv in fsv_list]
        score_list = [-1 for fsv in fsv_list]
        #fsv.prod(axis=1).sum() for fsv in fsv_list]
        cm = cls(qaid, daid_list, fm_list, fsv_list, None, score_list, H_list,
                 fsv_col_lbls)
        cm.fs_list = fs_list
        return cm

    @classmethod
    @profile
    def from_vsmany_match_tup(cls, vmt, qaid=None, fsv_col_lbls=None):
        r"""
        Args:
            vmt (ibeis.algo.hots.pipeline.ValidMatchTup_): valid_match_tup
            qaid (int):  query annotation id
            fsv_col_lbls (None):

        Returns:
            ibeis.ChipMatch: cm
        """
        # NOTE: CONTIGUOUS ARRAYS MAKE A HUGE DIFFERENCE
        valid_fm = np.concatenate((vmt.qfx[:, None],
                                   vmt.dfx[:, None]), axis=1)
        assert valid_fm.flags.c_contiguous, 'non-contiguous'
        # valid_fm = np.ascontiguousarray(valid_fm)
        daid_list, daid_groupxs = vt.group_indices(vmt.daid)

        fm_list  = vt.apply_grouping(valid_fm, daid_groupxs)
        fsv_list = vt.apply_grouping(vmt.scorevec, daid_groupxs)
        fk_list  = vt.apply_grouping(vmt.rank, daid_groupxs)

        filtnorm_aids = [
            None  # [None] * len(daid_groupxs)
            if aids is None else vt.apply_grouping(aids, daid_groupxs)
            for aids in vmt.norm_aids]

        filtnorm_fxs = [
            None  # [None] * len(daid_groupxs)
            if fxs is None else vt.apply_grouping(fxs, daid_groupxs)
            for fxs in vmt.norm_fxs]

        # assert len(filtnorm_aids) == len(fsv_col_lbls), 'bad normer'
        # assert len(filtnorm_fxs) == len(fsv_col_lbls), 'bad normer'

        cm = cls(qaid, daid_list, fm_list, fsv_list, fk_list,
                 fsv_col_lbls=fsv_col_lbls, filtnorm_aids=filtnorm_aids,
                 filtnorm_fxs=filtnorm_fxs)
        return cm

    @classmethod
    @profile
    def from_vsone_match_tup(cls, vmt_list, daid_list=None,
                             qaid=None, fsv_col_lbls=None):
        r"""
        Args:
            vmt_list (list of ValidMatchTup_): list of valid_match_tups
            qaid (int):  query annotation id
            fsv_col_lbls (None):

        Returns:
            ibeis.ChipMatch: cm
        """
        assert all(list(map(ut.allsame,
                            ut.get_list_column(vmt_list, 0)))), (
            'internal daids should not have different daids for vsone')
        qfx_list = ut.get_list_column(vmt_list, 1)
        dfx_list = ut.get_list_column(vmt_list, 2)
        # fm_list  = [np.vstack((dfx, qfx)).T
        #             for dfx, qfx in zip(dfx_list, qfx_list)]
        fm_list = [np.concatenate((dfx[:, None], qfx[:, None]), axis=1)
                   for dfx, qfx in zip(dfx_list, qfx_list)]
        fsv_list = ut.get_list_column(vmt_list, 3)
        fk_list  = ut.get_list_column(vmt_list, 4)

        filtnorm_aids = ut.list_transpose(ut.get_list_column(vmt_list, 5))
        filtnorm_fxs = ut.list_transpose(ut.get_list_column(vmt_list, 6))

        filtnorm_aids = [
            None if all([aids is None for aids in aids_list]) else aids_list
            for aids_list in filtnorm_aids
        ]

        filtnorm_fxs = [
            None if all([fxs is None for fxs in fxs_list]) else fxs_list
            for fxs_list in filtnorm_fxs
        ]

        # assert len(filtnorm_aids) == len(fsv_col_lbls), 'bad normer %r %r' % (len(filtnorm_aids), len(fsv_col_lbls))
        # assert len(filtnorm_fxs) == len(fsv_col_lbls), 'bad normer %r %r' % (len(filtnorm_aids), len(fsv_col_lbls))

        cm = cls(qaid, daid_list, fm_list, fsv_list, fk_list,
                 fsv_col_lbls=fsv_col_lbls, filtnorm_aids=filtnorm_aids,
                 filtnorm_fxs=filtnorm_fxs)
        return cm

    @classmethod
    def from_json(cls, json_str):
        r"""
        Convert json string back to ChipMatch object

        CommandLine:
            # FIXME; util_test is broken with classmethods
            python -m ibeis.algo.hots.chip_match --test-from_json --show

        Example:
            >>> # ENABLE_DOCTEST
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> cls = ChipMatch
            >>> cm1, qreq_ = ibeis.testdata_cm()
            >>> json_str = cm1.to_json()
            >>> cm = ChipMatch.from_json(json_str)
            >>> ut.quit_if_noshow()
            >>> cm.score_nsum(qreq_)
            >>> cm.show_single_namematch(qreq_, 1)
            >>> ut.show_if_requested()
        """
        class_dict = ut.from_json(json_str)
        return cls.from_dict(class_dict)

    @classmethod
    def from_dict(cls, class_dict, ibs=None):
        r"""
        Convert dict of arguments back to ChipMatch object
        """

        key_list = ut.get_kwargs(cls.initialize)[0]  # HACKY
        key_list.remove('autoinit')
        if ut.VERBOSE:
            other_keys = list(set(class_dict.keys()) - set(key_list))
            if len(other_keys) > 0:
                print('Not unserializing extra attributes: %s' % (
                    ut.list_str(other_keys)))

        if ibs is not None:
            class_dict = prepare_dict_uuids(class_dict, ibs)

        dict_subset = ut.dict_subset(class_dict, key_list)
        dict_subset['fm_list'] = convert_numpy_lists(dict_subset['fm_list'],
                                                     hstypes.FM_DTYPE, dims=2)
        dict_subset['fsv_list'] = convert_numpy_lists(dict_subset['fsv_list'],
                                                      hstypes.FS_DTYPE, dims=2)
        dict_subset['score_list'] = convert_numpy(dict_subset['score_list'],
                                                  hstypes.FS_DTYPE)
        safe_check_nested_lens_eq(dict_subset['fm_list'], dict_subset['fsv_list'])
        safe_check_lens_eq(dict_subset['score_list'], dict_subset['fsv_list'])
        safe_check_lens_eq(dict_subset['score_list'], dict_subset['fm_list'])

        cm = cls(**dict_subset)
        return cm

    @profile
    def to_json(cm):
        r"""
        Serialize ChipMatch object as JSON string

        CommandLine:
            python -m ibeis.algo.hots.chip_match --test-ChipMatch.to_json:0
            python -m ibeis.algo.hots.chip_match --test-ChipMatch.to_json
            python -m ibeis.algo.hots.chip_match --test-ChipMatch.to_json:1 --show

        Example:
            >>> # ENABLE_DOCTEST
            >>> # Simple doctest demonstrating the json format
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> cm, qreq_ = ibeis.testdata_cm()
            >>> cm.compress_top_feature_matches(num=4, rng=np.random.RandomState(0))
            >>> # Serialize
            >>> print('\n\nRaw ChipMatch JSON:\n')
            >>> json_str = cm.to_json()
            >>> print(json_str)
            >>> print('\n\nPretty ChipMatch JSON:\n')
            >>> # Pretty String Formatting
            >>> dictrep = ut.from_json(json_str)
            >>> dictrep = ut.delete_dict_keys(dictrep, [key for key, val in dictrep.items() if val is None])
            >>> result  = ut.repr2_json(dictrep, nl=2, precision=2, key_order_metric='strlen')
            >>> print(result)

        Example:
            >>> # ENABLE_DOCTEST
            >>> # test to convert back and forth from json
            >>> from ibeis.algo.hots.chip_match import *  # NOQA
            >>> import ibeis
            >>> cm, qreq_ = ibeis.testdata_cm()
            >>> cm1 = cm
            >>> # Serialize
            >>> json_str = cm.to_json()
            >>> print(repr(json_str))
            >>> # Unserialize
            >>> cm = ChipMatch.from_json(json_str)
            >>> # Show if it works
            >>> ut.quit_if_noshow()
            >>> cm.score_nsum(qreq_)
            >>> cm.show_single_namematch(qreq_, 1)
            >>> ut.show_if_requested()
            >>> # result = ('json_str = \n%s' % (str(json_str),))
            >>> # print(result)
        """
        json_str = ut.to_json(cm.__dict__)
        return json_str

    # --- IO

    def get_fpath(cm, qreq_):
        dpath = qreq_.get_qresdir()
        fname = get_chipmatch_fname(cm.qaid, qreq_)
        fpath = join(dpath, fname)
        return fpath

    def save(cm, qreq_, verbose=None):
        fpath = cm.get_fpath(qreq_)
        cm.save_to_fpath(fpath, verbose=verbose)

    #@classmethod
    #def load(cls, qreq_, qaid, dpath=None, verbose=None):
    #    fname = get_chipmatch_fname(qaid, qreq_)
    #    if dpath is None:
    #        dpath = qreq_.get_qresdir()
    #    fpath = join(dpath, fname)
    #    cm = cls.load_from_fpath(fpath, verbose=verbose)
    #    return cm

    @classmethod
    def load_from_fpath(cls, fpath, verbose=None):
        #state_dict = ut.load_data(fpath, verbose=verbose)
        state_dict = ut.load_cPkl(fpath, verbose=verbose)
        if 'filtnorm_aids' not in state_dict:
            raise NeedRecomputeError('old version of chipmatch')
        cm = cls()
        cm.__setstate__(state_dict)
        return cm


# -----
# Misc
# -----


class TestLogger(object):
    def __init__(testlog, verbose=True):
        testlog.test_out = ut.ddict(list)
        testlog.current_test = None
        testlog.failed_list = []
        testlog.verbose = verbose

    def start_test(testlog, name):
        testlog.current_test = name

    def log_skipped(testlog, msg):
        if testlog.verbose:
            print('[cm] skip: ' + msg)

    def log_passed(testlog, msg):
        if testlog.verbose:
            print('[cm] pass: ' + msg)

    def skip_test(testlog):
        testlog.log_skipped(testlog.current_test)
        testlog.current_test = None

    def log_failed(testlog, msg):
        testlog.test_out[testlog.current_test].append(msg)
        testlog.failed_list.append(msg)
        print('[cm] FAILED!: ' + msg)

    def end_test(testlog):
        if len(testlog.test_out[testlog.current_test]) == 0:
            testlog.log_passed(testlog.current_test)
        else:
            testlog.log_failed(testlog.current_test)
        testlog.current_test = None

    def context(testlog, name):
        testlog.start_test(name)
        return testlog

    def __enter__(testlog):
        return testlog

    def __exit__(testlog, type_, value, trace):
        if testlog.current_test is not None:
            if trace is not None:
                testlog.log_failed('error occured')
            testlog.end_test()


def testdata_cm():
    ibs, qreq_, cm_list = plh.testdata_pre_sver('PZ_MTEST',
                                                qaid_list=[18])
    cm = cm_list[0]
    cm.score_nsum(qreq_)
    return cm, qreq_


@profile
def get_chipmatch_fname(qaid, qreq_, qauuid=None, cfgstr=None,
                        TRUNCATE_UUIDS=TRUNCATE_UUIDS,
                        MAX_FNAME_LEN=MAX_FNAME_LEN):
    r"""
    CommandLine:
        python -m ibeis.algo.hots.chip_match --test-get_chipmatch_fname

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.chip_match import *  # NOQA
        >>> qreq_, args = plh.testdata_pre('spatial_verification',
        >>>                                defaultdb='PZ_MTEST', qaid_override=[18],
        >>>                                p='default:sqrd_dist_on=True')
        >>> cm_list = args.cm_list_FILT
        >>> cm = cm_list[0]
        >>> fname = get_chipmatch_fname(cm.qaid, qreq_, qauuid=None,
        >>>                             TRUNCATE_UUIDS=False, MAX_FNAME_LEN=200)
        >>> result = fname
        >>> print(result)

        qaid=18_cm_cvgrsbnffsgifyom_quuid=a126d459-b730-573e-7a21-92894b016565.cPkl
    """
    if qauuid is None:
        print('[chipmatch] Warning qasuuid should be given')
        qauuid = qreq_.ibs.get_annot_semantic_uuids(qaid)
    if cfgstr is None:
        print('[chipmatch] Warning cfgstr should be passed given')
        cfgstr = qreq_.get_cfgstr(with_input=True)
    #print('cfgstr = %r' % (cfgstr,))
    fname_fmt = 'qaid={qaid}_cm_{cfgstr}_quuid={qauuid}{ext}'
    text_type = six.text_type
    #text_type = str
    qauuid_str = text_type(qauuid)[0:8] if TRUNCATE_UUIDS else text_type(qauuid)
    fmt_dict = dict(cfgstr=cfgstr, qaid=qaid, qauuid=qauuid_str, ext='.cPkl')
    fname = ut.long_fname_format(fname_fmt, fmt_dict, ['cfgstr'],
                                 max_len=MAX_FNAME_LEN, hack27=True)
    return fname


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.algo.hots.chip_match
        python -m ibeis.algo.hots.chip_match --allexamples
        python -m ibeis.algo.hots.chip_match --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
