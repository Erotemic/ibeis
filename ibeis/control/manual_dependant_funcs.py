from __future__ import absolute_import, division, print_function
import six  # NOQA
import functools
from ibeis import constants as const
from ibeis.control.accessor_decors import (adder, ider, default_decorator, getter_1to1, getter_1toM, deleter)
import utool as ut
from ibeis.control.controller_inject import make_ibs_register_decorator
print, print_, printDBG, rrr, profile = ut.inject(__name__, '[manual_dependant]')


CLASS_INJECT_KEY, register_ibs_method = make_ibs_register_decorator(__name__)


@register_ibs_method
@default_decorator
def get_chip_config_rowid(ibs):
    """ # FIXME: Configs are still handled poorly

    This method deviates from the rest of the controller methods because it
    always returns a scalar instead of a list. I'm still not sure how to
    make it more ibeisy
    """
    chip_cfg_suffix = ibs.cfg.chip_cfg.get_cfgstr()
    chip_cfg_rowid = ibs.add_config(chip_cfg_suffix)
    return chip_cfg_rowid


@register_ibs_method
@default_decorator
def get_feat_config_rowid(ibs):
    """
    Returns the feature configuration id based on the cfgstr
    defined by ibs.cfg.feat_cfg.get_cfgstr()

    # FIXME: Configs are still handled poorly
    used in ibeis.model.preproc.preproc_feats in the param
    generator. (that should probably be moved into the controller)
    """
    feat_cfg_suffix = ibs.cfg.feat_cfg.get_cfgstr()
    feat_cfg_rowid = ibs.add_config(feat_cfg_suffix)
    return feat_cfg_rowid


@register_ibs_method
@ider
def _get_all_cids(ibs):
    """
    Returns:
        list_ (list): unfiltered cids (computed chip rowids) for every
    configuration (YOU PROBABLY SHOULD NOT USE THIS) """
    all_cids = ibs.dbcache.get_all_rowids(const.CHIP_TABLE)
    return all_cids


@register_ibs_method
@ider
def _get_all_fids(ibs):
    """
    Returns:
        list_ (list): unfiltered fids (computed feature rowids) for every
    configuration (YOU PROBABLY SHOULD NOT USE THIS)"""
    all_fids = ibs.dbcache.get_all_rowids(const.FEATURE_TABLE)
    return all_fids

_get_all_feat_rowids = _get_all_fids
_get_all_chip_rowids = _get_all_cids


@register_ibs_method
@ider
def get_valid_cids(ibs):
    """ Valid chip rowids of the current configuration """
    # FIXME: configids need reworking
    chip_config_rowid = ibs.get_chip_config_rowid()
    cid_list = ibs.dbcache.get_all_rowids_where(const.FEATURE_TABLE, 'config_rowid=?', (chip_config_rowid,))
    return cid_list


@register_ibs_method
@ider
def get_valid_fids(ibs):
    """ Valid feature rowids of the current configuration """
    # FIXME: configids need reworking
    feat_config_rowid = ibs.get_feat_config_rowid()
    fid_list = ibs.dbcache.get_all_rowids_where(const.FEATURE_TABLE, 'config_rowid=?', (feat_config_rowid,))
    return fid_list

# --- ADDERS ---


@register_ibs_method
@adder
def add_chips(ibs, aid_list):
    """
    FIXME: This is a dirty dirty function
    Adds chip data to the ANNOTATION. (does not create ANNOTATIONs. first use add_annots
    and then pass them here to ensure chips are computed) """
    # Ensure must be false, otherwise an infinite loop occurs
    from ibeis.model.preproc import preproc_chip
    cid_list = ibs.get_annot_cids(aid_list, ensure=False)
    dirty_aids = ut.get_dirty_items(aid_list, cid_list)
    if len(dirty_aids) > 0:
        if not ut.QUIET:
            print('[ibs] adding chips')
        try:
            # FIXME: Cant be lazy until chip config / delete issue is fixed
            preproc_chip.compute_and_write_chips(ibs, aid_list)
            #preproc_chip.compute_and_write_chips_lazy(ibs, aid_list)
            params_iter = preproc_chip.add_chips_params_gen(ibs, dirty_aids)
        except AssertionError as ex:
            ut.printex(ex, '[!ibs.add_chips]')
            print('[!ibs.add_chips] ' + ut.list_dbgstr('aid_list'))
            raise
        colnames = ('annot_rowid', 'config_rowid', 'chip_uri', 'chip_width', 'chip_height',)
        get_rowid_from_superkey = functools.partial(ibs.get_annot_cids, ensure=False)
        cid_list = ibs.dbcache.add_cleanly(const.CHIP_TABLE, colnames, params_iter, get_rowid_from_superkey)

    return cid_list


@register_ibs_method
@adder
def add_feats(ibs, cid_list, force=False):
    """ Computes the features for every chip without them """
    from ibeis.model.preproc import preproc_feat
    fid_list = ibs.get_chip_fids(cid_list, ensure=False)
    dirty_cids = ut.get_dirty_items(cid_list, fid_list)
    if len(dirty_cids) > 0:
        if ut.VERBOSE:
            print('[ibs] adding %d / %d features' % (len(dirty_cids), len(cid_list)))
        params_iter = preproc_feat.add_feat_params_gen(ibs, dirty_cids)
        colnames = ('chip_rowid', 'config_rowid', 'feature_num_feats', 'feature_keypoints',
                    'feature_vecs')
        get_rowid_from_superkey = functools.partial(ibs.get_chip_fids, ensure=False)
        fid_list = ibs.dbcache.add_cleanly(const.FEATURE_TABLE, colnames, params_iter, get_rowid_from_superkey)

    return fid_list

# GETTERS::.CHIP_TABLE


@register_ibs_method
@getter_1to1
def get_chips(ibs, cid_list, ensure=True):
    """
    Returns:
        chip_list (list): a list cropped images in numpy array form by their cid
    """
    from ibeis.model.preproc import preproc_chip
    aid_list = ibs.get_chip_aids(cid_list)
    chip_list = preproc_chip.compute_or_read_annotation_chips(ibs, aid_list, ensure=ensure)
    return chip_list


@register_ibs_method
@getter_1to1
def get_chip_detectpaths(ibs, cid_list):
    """
    Returns:
        new_gfpath_list (list): a list of image paths resized to a constant area for detection """
    from ibeis.model.preproc import preproc_detectimg
    new_gfpath_list = preproc_detectimg.compute_and_write_detectchip_lazy(ibs, cid_list)
    return new_gfpath_list


@register_ibs_method
@getter_1to1
def get_chip_aids(ibs, cid_list):
    aid_list = ibs.dbcache.get(const.CHIP_TABLE, ('annot_rowid',), cid_list)
    return aid_list


@register_ibs_method
@getter_1to1
def get_chip_paths(ibs, cid_list):
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
def get_chip_fids(ibs, cid_list, ensure=True, eager=True, nInput=None, qreq_=None):
    if ensure:
        ibs.add_feats(cid_list)
    feat_config_rowid = ibs.get_feat_config_rowid()
    colnames = ('feature_rowid',)
    where_clause = 'chip_rowid=? AND config_rowid=?'
    params_iter = ((cid, feat_config_rowid) for cid in cid_list)
    fid_list = ibs.dbcache.get_where(const.FEATURE_TABLE, colnames, params_iter,
                                     where_clause, eager=eager,
                                     nInput=nInput)
    return fid_list

get_chip_feat_rowids = get_chip_fids


@register_ibs_method
@getter_1to1
def get_chip_configids(ibs, cid_list):
    config_rowid_list = ibs.dbcache.get(const.CHIP_TABLE, ('config_rowid',), cid_list)
    return config_rowid_list

#
# GETTERS::.FEATURE_TABLE


@register_ibs_method
@getter_1toM
#@cache_getter(const.FEATURE_TABLE, 'feature_keypoints')
def get_feat_kpts(ibs, fid_list, eager=True, nInput=None):
    """
    Returns:
        kpts_list (list): chip keypoints in [x, y, iv11, iv21, iv22, ori] format """
    kpts_list = ibs.dbcache.get(const.FEATURE_TABLE, ('feature_keypoints',), fid_list, eager=eager, nInput=nInput)
    return kpts_list


@register_ibs_method
@getter_1toM
#@cache_getter(const.FEATURE_TABLE, 'feature_vecs')
def get_feat_vecs(ibs, fid_list, eager=True, nInput=None):
    """
    Returns:
        vecs_list (list): chip SIFT descriptors """
    vecs_list = ibs.dbcache.get(const.FEATURE_TABLE, ('feature_vecs',), fid_list, eager=eager, nInput=nInput)
    return vecs_list


@register_ibs_method
@getter_1to1
#@cache_getter(const.FEATURE_TABLE, 'feature_num_feats')
def get_num_feats(ibs, fid_list, eager=True, nInput=None):
    """
    Returns:
        nFeats_list (list): the number of keypoint / descriptor pairs """
    nFeats_list = ibs.dbcache.get(const.FEATURE_TABLE, ('feature_num_feats',), fid_list, eager=True, nInput=None)
    nFeats_list = [(-1 if nFeats is None else nFeats) for nFeats in nFeats_list]
    return nFeats_list


# DELETERS


@register_ibs_method
@deleter
#@cache_invalidator(const.FEATURE_TABLE)
def delete_features(ibs, fid_list):
    """ deletes images from the database that belong to fids"""
    if ut.VERBOSE:
        print('[ibs] deleting %d features' % len(fid_list))
    ibs.dbcache.delete_rowids(const.FEATURE_TABLE, fid_list)


@register_ibs_method
@deleter
def delete_annot_chips(ibs, aid_list):
    """ Clears annotation data but does not remove the annotation """
    _cid_list = ibs.get_annot_cids(aid_list, ensure=False)
    cid_list = ut.filter_Nones(_cid_list)
    ibs.delete_chips(cid_list)
    gid_list = ibs.get_annot_gids(aid_list)
    ibs.delete_image_thumbs(gid_list)  # why is this done here?
    ibs.delete_annot_chip_thumbs(aid_list)


@register_ibs_method
@deleter
def delete_annot_chip_thumbs(ibs, aid_list, quiet=False):
    """ Removes chip thumbnails from disk """
    thumbpath_list = ibs.get_annot_chip_thumbpath(aid_list)
    ut.remove_file_list(thumbpath_list, quiet=quiet)


@register_ibs_method
@deleter
#@cache_invalidator(const.CHIP_TABLE)
def delete_chips(ibs, cid_list, verbose=ut.VERBOSE):
    """ deletes images from the database that belong to gids"""
    from ibeis.model.preproc import preproc_chip
    if verbose:
        print('[ibs] deleting %d annotation-chips' % len(cid_list))
    # Delete chip-images from disk
    #preproc_chip.delete_chips(ibs, cid_list, verbose=verbose)
    preproc_chip.on_delete(ibs, cid_list, verbose=verbose)
    # Delete chip features from sql
    _fid_list = ibs.get_chip_fids(cid_list, ensure=False)
    fid_list = ut.filter_Nones(_fid_list)
    ibs.delete_features(fid_list)
    # Delete chips from sql
    ibs.dbcache.delete_rowids(const.CHIP_TABLE, cid_list)


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
