from __future__ import absolute_import, division, print_function
import six  # NOQA
import functools
from ibeis import constants as const
from ibeis.control import accessor_decors
from ibeis.control.accessor_decors import (adder, ider, default_decorator,
                                           getter_1to1, getter_1toM, deleter)
import utool as ut
from ibeis.control.controller_inject import make_ibs_register_decorator
print, print_, printDBG, rrr, profile = ut.inject(__name__, '[manual_dependant]')


CLASS_INJECT_KEY, register_ibs_method = make_ibs_register_decorator(__name__)


ANNOT_ROWID   = 'annot_rowid'
CHIP_ROWID    = 'chip_rowid'
FEAT_VECS     = 'feature_vecs'
FEAT_KPTS     = 'feature_keypoints'
FEAT_NUM_FEAT = 'feature_num_feats'


@register_ibs_method
@ider
def _get_all_cids(ibs):
    """ alias """
    return _get_all_chip_rowids(ibs)


@register_ibs_method
@ider
def _get_all_fids(ibs):
    """ alias """
    return _get_all_feat_rowids(ibs)


@register_ibs_method
def _get_all_feat_rowids(ibs):
    """
    Returns:
        list_ (list): unfiltered fids (computed feature rowids) for every
    configuration (YOU PROBABLY SHOULD NOT USE THIS)"""
    all_fids = ibs.dbcache.get_all_rowids(const.FEATURE_TABLE)
    return all_fids


@register_ibs_method
def _get_all_chip_rowids(ibs):
    """
    Returns:
        list_ (list): unfiltered cids (computed chip rowids) for every
    configuration (YOU PROBABLY SHOULD NOT USE THIS) """
    all_cids = ibs.dbcache.get_all_rowids(const.CHIP_TABLE)
    return all_cids


@register_ibs_method
@adder
def add_annot_chips(ibs, aid_list, qreq_=None):
    """
    FIXME: This is a dirty dirty function
    Adds chip data to the ANNOTATION. (does not create ANNOTATIONs. first use add_annots
    and then pass them here to ensure chips are computed) """
    # Ensure must be false, otherwise an infinite loop occurs
    from ibeis.model.preproc import preproc_chip
    cid_list = ibs.get_annot_chip_rowids(aid_list, ensure=False)
    dirty_aids = ut.get_dirty_items(aid_list, cid_list)
    if len(dirty_aids) > 0:
        if ut.VERBOSE:
            print('[ibs] adding chips')
        try:
            # FIXME: Cant be lazy until chip config / delete issue is fixed
            preproc_chip.compute_and_write_chips(ibs, aid_list)
            #preproc_chip.compute_and_write_chips_lazy(ibs, aid_list)
            params_iter = preproc_chip.add_annot_chips_params_gen(ibs, dirty_aids)
        except AssertionError as ex:
            ut.printex(ex, '[!ibs.add_annot_chips]')
            print('[!ibs.add_annot_chips] ' + ut.list_dbgstr('aid_list'))
            raise
        colnames = (ANNOT_ROWID, 'config_rowid', 'chip_uri', 'chip_width', 'chip_height',)
        get_rowid_from_superkey = functools.partial(ibs.get_annot_chip_rowids, ensure=False, qreq_=qreq_)
        cid_list = ibs.dbcache.add_cleanly(const.CHIP_TABLE, colnames, params_iter, get_rowid_from_superkey)

    return cid_list


@register_ibs_method
@adder
def add_chip_feats(ibs, cid_list, force=False, qreq_=None):
    """ Computes the features for every chip without them """
    from ibeis.model.preproc import preproc_feat
    fid_list = ibs.get_chip_fids(cid_list, ensure=False, qreq_=qreq_)
    dirty_cids = ut.get_dirty_items(cid_list, fid_list)
    if len(dirty_cids) > 0:
        if ut.VERBOSE:
            print('[ibs] adding %d / %d features' % (len(dirty_cids), len(cid_list)))
        params_iter = preproc_feat.add_feat_params_gen(ibs, dirty_cids, qreq_=qreq_)
        colnames = (CHIP_ROWID, 'config_rowid', FEAT_NUM_FEAT, FEAT_KPTS, FEAT_VECS)
        get_rowid_from_superkey = functools.partial(ibs.get_chip_fids, ensure=False, qreq_=qreq_)
        fid_list = ibs.dbcache.add_cleanly(const.FEATURE_TABLE, colnames, params_iter, get_rowid_from_superkey)

    return fid_list


@register_ibs_method
@deleter
def delete_annot_chip_thumbs(ibs, aid_list, quiet=False):
    """ Removes chip thumbnails from disk """
    thumbpath_list = ibs.get_annot_chip_thumbpath(aid_list)
    #ut.remove_fpaths(thumbpath_list, quiet=quiet, lbl='chip_thumbs')
    ut.remove_existing_fpaths(thumbpath_list, quiet=quiet, lbl='chip_thumbs')


@register_ibs_method
@deleter
def delete_annot_chips(ibs, aid_list, qreq_=None):
    """ Clears annotation data but does not remove the annotation """
    _cid_list = ibs.get_annot_chip_rowids(aid_list, ensure=False, qreq_=qreq_)
    cid_list = ut.filter_Nones(_cid_list)
    ibs.delete_chips(cid_list)
    # HACK FIX: if annot chips are None then the image thumbnail
    # will not be invalidated
    if len(_cid_list) != len(cid_list):
        aid_list_ = [aid for aid, _cid in zip(aid_list, _cid_list) if _cid is None]
        gid_list_ = ibs.get_annot_gids(aid_list_)
        ibs.delete_image_thumbs(gid_list_)


@register_ibs_method
@deleter
#@cache_invalidator(const.CHIP_TABLE)
def delete_chips(ibs, cid_list, verbose=ut.VERBOSE, qreq_=None):
    """ deletes images from the database that belong to gids"""
    from ibeis.model.preproc import preproc_chip
    if verbose:
        print('[ibs] deleting %d annotation-chips' % len(cid_list))
    # Delete chip-images from disk
    #preproc_chip.delete_chips(ibs, cid_list, verbose=verbose)
    preproc_chip.on_delete(ibs, cid_list, verbose=verbose)
    # Delete chip features from sql
    _fid_list = ibs.get_chip_fids(cid_list, ensure=False, qreq_=qreq_)
    fid_list = ut.filter_Nones(_fid_list)
    ibs.delete_features(fid_list)
    # Delete chips from sql
    ibs.dbcache.delete_rowids(const.CHIP_TABLE, cid_list)


@register_ibs_method
@deleter
@accessor_decors.cache_invalidator(const.FEATURE_TABLE)
def delete_features(ibs, fid_list):
    """ deletes images from the database that belong to fids"""
    if ut.VERBOSE:
        print('[ibs] deleting %d features' % len(fid_list))
    ibs.dbcache.delete_rowids(const.FEATURE_TABLE, fid_list)


@register_ibs_method
@getter_1to1
def get_chip_aids(ibs, cid_list):
    aid_list = ibs.dbcache.get(const.CHIP_TABLE, (ANNOT_ROWID,), cid_list)
    return aid_list


@register_ibs_method
@default_decorator
def get_chip_config_rowid(ibs, qreq_=None):
    """ # FIXME: Configs are still handled poorly

    This method deviates from the rest of the controller methods because it
    always returns a scalar instead of a list. I'm still not sure how to
    make it more ibeisy
    """
    if qreq_ is not None:
        # TODO store config_rowid in qparams
        # Or find better way to do this in general
        chip_cfg_suffix = qreq_.qparams.chip_cfgstr
    else:
        chip_cfg_suffix = ibs.cfg.chip_cfg.get_cfgstr()
    chip_cfg_rowid = ibs.add_config(chip_cfg_suffix)
    return chip_cfg_rowid


@register_ibs_method
@getter_1to1
def get_chip_configids(ibs, cid_list):
    config_rowid_list = ibs.dbcache.get(const.CHIP_TABLE, ('config_rowid',), cid_list)
    return config_rowid_list


@register_ibs_method
@getter_1to1
def get_chip_detectpaths(ibs, cid_list):
    """
    Returns:
        new_gfpath_list (list): a list of image paths resized to a constant area for detection
    """
    from ibeis.model.preproc import preproc_detectimg
    new_gfpath_list = preproc_detectimg.compute_and_write_detectchip_lazy(ibs, cid_list)
    return new_gfpath_list


@register_ibs_method
def get_chip_feat_rowids(ibs, cid_list, ensure=True, eager=True, nInput=None, qreq_=None):
    # alias for get_chip_fids
    return get_chip_fids(ibs, cid_list, ensure=ensure, eager=eager, nInput=nInput, qreq_=qreq_)


@register_ibs_method
@getter_1to1
@accessor_decors.dev_cache_getter(const.CHIP_TABLE, 'feature_rowid')
def get_chip_fids(ibs, cid_list, ensure=True, eager=True, nInput=None, qreq_=None):
    if ensure:
        ibs.add_chip_feats(cid_list, qreq_=qreq_)
    feat_config_rowid = ibs.get_feat_config_rowid(qreq_=qreq_)
    colnames = ('feature_rowid',)
    where_clause = CHIP_ROWID + '=? AND config_rowid=?'
    params_iter = ((cid, feat_config_rowid) for cid in cid_list)
    fid_list = ibs.dbcache.get_where(const.FEATURE_TABLE, colnames, params_iter,
                                     where_clause, eager=eager,
                                     nInput=nInput)
    return fid_list


@register_ibs_method
@getter_1to1
def get_chip_uris(ibs, cid_list):
    """

    Returns:
        chip_fpath_list (list): a list of chip paths by their aid
    """
    chip_fpath_list = ibs.dbcache.get(const.CHIP_TABLE, ('chip_uri',), cid_list)
    return chip_fpath_list


@register_ibs_method
@getter_1to1
#@cache_getter('const.CHIP_TABLE', 'chip_size')
def get_chip_sizes(ibs, cid_list):
    chipsz_list  = ibs.dbcache.get(const.CHIP_TABLE, ('chip_width', 'chip_height',), cid_list)
    return chipsz_list


@register_ibs_method
@getter_1to1
def get_chips(ibs, cid_list, ensure=True):
    """
    Returns:
        chip_list (list): a list cropped images in numpy array form by their cid
    """
    from ibeis.model.preproc import preproc_chip
    if ensure:
        try:
            ut.assert_all_not_None(cid_list, 'cid_list')
        except AssertionError as ex:
            ut.printex(ex, 'Invalid cid_list', key_list=[
                'ensure', 'cid_list'])
            raise
    aid_list = ibs.get_chip_aids(cid_list)
    chip_list = preproc_chip.compute_or_read_annotation_chips(ibs, aid_list, ensure=ensure)
    return chip_list


@register_ibs_method
@default_decorator
def get_feat_config_rowid(ibs, qreq_=None):
    """
    Returns the feature configuration id based on the cfgstr
    defined by ibs.cfg.feat_cfg.get_cfgstr()

    # FIXME: Configs are still handled poorly
    used in ibeis.model.preproc.preproc_feats in the param
    generator. (that should probably be moved into the controller)
    """
    if qreq_ is not None:
        # TODO store config_rowid in qparams
        # Or find better way to do this in general
        feat_cfg_suffix = qreq_.qparams.feat_cfgstr
    else:
        feat_cfg_suffix = ibs.cfg.feat_cfg.get_cfgstr()
    feat_cfg_rowid = ibs.add_config(feat_cfg_suffix)
    return feat_cfg_rowid


@register_ibs_method
@getter_1toM
@accessor_decors.cache_getter(const.FEATURE_TABLE, FEAT_KPTS)
def get_feat_kpts(ibs, fid_list, eager=True, nInput=None):
    """
    Returns:
        kpts_list (list): chip keypoints in [x, y, iv11, iv21, iv22, ori] format
    """
    kpts_list = ibs.dbcache.get(const.FEATURE_TABLE, (FEAT_KPTS,), fid_list, eager=eager, nInput=nInput)
    return kpts_list


@register_ibs_method
@getter_1toM
@accessor_decors.cache_getter(const.FEATURE_TABLE, FEAT_VECS)
def get_feat_vecs(ibs, fid_list, eager=True, nInput=None):
    """
    Returns:
        vecs_list (list): chip SIFT descriptors
    """
    vecs_list = ibs.dbcache.get(const.FEATURE_TABLE, (FEAT_VECS,), fid_list, eager=eager, nInput=nInput)
    return vecs_list


@register_ibs_method
@getter_1to1
@accessor_decors.cache_getter(const.FEATURE_TABLE, FEAT_NUM_FEAT)
def get_num_feats(ibs, fid_list, eager=True, nInput=None):
    """
    Returns:
        nFeats_list (list): the number of keypoint / descriptor pairs
    """
    nFeats_list = ibs.dbcache.get(const.FEATURE_TABLE, (FEAT_NUM_FEAT,), fid_list, eager=True, nInput=None)
    nFeats_list = [(-1 if nFeats is None else nFeats) for nFeats in nFeats_list]
    return nFeats_list


@register_ibs_method
@ider
def get_valid_cids(ibs, qreq_=None):
    """ Valid chip rowids of the current configuration """
    # FIXME: configids need reworking
    chip_config_rowid = ibs.get_chip_config_rowid(qreq_=qreq_)
    cid_list = ibs.dbcache.get_all_rowids_where(const.FEATURE_TABLE, 'config_rowid=?', (chip_config_rowid,))
    return cid_list


@register_ibs_method
@ider
def get_valid_fids(ibs, qreq_=None):
    """ Valid feature rowids of the current configuration """
    # FIXME: configids need reworking
    feat_config_rowid = ibs.get_feat_config_rowid(qreq_=qreq_)
    fid_list = ibs.dbcache.get_all_rowids_where(const.FEATURE_TABLE, 'config_rowid=?', (feat_config_rowid,))
    return fid_list


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.control.manual_dependant_funcs
        python -m ibeis.control.manual_dependant_funcs --allexamples
        python -m ibeis.control.manual_dependant_funcs --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()


@register_ibs_method
@adder
def add_annot_chips(ibs, aid_list, qreq_=None):
    """ annot.chip.add(aid_list)

    CRITICAL FUNCTION MUST EXIST FOR ALL DEPENDANTS
    Adds / ensures / computes a dependant property

    Args:
         aid_list

    Returns:
        returns chip_rowid_list of added (or already existing chips)

    TemplateInfo:
        Tadder_pl_dependant
        parent = annot
        leaf = chip

    CommandLine:
        python -m ibeis.control.manual_chip_funcs --test-add_annot_chips

    Example1:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.control.manual_chip_funcs import *  # NOQA
        >>> ibs, qreq_ = testdata_ibs()
        >>> aid_list = ibs._get_all_aids()[::3]
        >>> chip_rowid_list = ibs.add_annot_chips(aid_list, qreq_=qreq_)
        >>> assert len(chip_rowid_list) == len(aid_list)
        >>> ut.assert_all_not_None(chip_rowid_list)

    Example2:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.control.manual_chip_funcs import *  # NOQA
        >>> ibs, qreq_ = testdata_ibs()
        >>> aid_list = ibs._get_all_aids()[0:10]
        >>> sub_aid_list1 = aid_list[0:6]
        >>> sub_aid_list2 = aid_list[5:7]
        >>> sub_aid_list3 = aid_list[0:7]
        >>> sub_cid_list1 = ibs.get_annot_chip_rowids(sub_aid_list1, qreq_=qreq_, ensure=True)
        >>> ut.assert_all_not_None(sub_cid_list1)
        >>> ibs.delete_annot_chips(sub_aid_list2)
        >>> sub_cid_list3 = ibs.get_annot_chip_rowids(sub_aid_list3, qreq_=qreq_, ensure=False)
        >>> # Only the last two should be None
        >>> ut.assert_all_not_None(sub_cid_list3)
        >>> assert sub_cid_list3[5:7] == [None, None]
        >>> sub_cid_list3_ensured = ibs.get_annot_chip_rowids(sub_aid_list3, qreq_=qreq_, ensure=True)
        >>> # Only two params should have been computed here
        >>> ut.assert_all_not_None(sub_cid_list3_ensured)

    """
    from ibeis.model.preproc import preproc_chip
    ut.assert_all_not_None(aid_list, 'aid_list')
    # Get requested configuration id
    config_rowid = ibs.get_chip_config_rowid(qreq_=qreq_)
    # Find leaf rowids that need to be computed
    initial_chip_rowid_list = get_annot_chip_rowids_(ibs, aid_list, qreq_=qreq_)
    # Get corresponding "dirty" parent rowids
    isdirty_list = ut.flag_None_items(initial_chip_rowid_list)
    dirty_aid_list = ut.filter_items(aid_list, isdirty_list)
    num_dirty = len(dirty_aid_list)
    if num_dirty > 0:
        #if ut.VERBOSE:
        print('[add_annot_chips] adding %d / %d new chips' % (len(dirty_aid_list), len(aid_list)))
        # Dependant columns do not need true from_superkey getters.
        # We can use the Tgetter_pl_dependant_rowids_ instead
        get_rowid_from_superkey = functools.partial(
            ibs.get_annot_chip_rowids_, qreq_=qreq_)
        proptup_gen = preproc_chip.generate_chip_properties(ibs, dirty_aid_list)
        dirty_params_iter = (
            (aid, config_rowid, chip_uri, chip_width, chip_height)
            for aid, (chip_uri, chip_width, chip_height,) in
            zip(dirty_aid_list, proptup_gen)
        )
        dirty_params_iter = list(dirty_params_iter)
        colnames = ['annot_rowid', 'config_rowid',
                    'chip_uri', 'chip_width', 'chip_height']
        #chip_rowid_list = ibs.dbcache.add_cleanly(
        #    const.CHIP_TABLE, colnames, params_iter, get_rowid_from_superkey)
        ibs.dbcache._add(const.CHIP_TABLE, colnames, dirty_params_iter)
        # Now that the dirty params are added get the correct order of rowids
        chip_rowid_list = get_rowid_from_superkey(aid_list)
    else:
        chip_rowid_list = initial_chip_rowid_list
    return chip_rowid_list
