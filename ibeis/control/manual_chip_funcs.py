"""
Functions for chips:
    to work on autogeneration

python -c "import utool as ut; ut.write_modscript_alias('Tgen.sh', 'ibeis.control.template_generator')"
sh Tgen.sh --key chip --Tcfg with_setters=False with_getters=True  with_adders=True
sh Tgen.sh --key chip

"""
from __future__ import absolute_import, division, print_function
import six  # NOQA
import functools
from os.path import join
from ibeis import constants as const
#from ibeis.control import accessor_decors
from ibeis.control.accessor_decors import (adder, ider, default_decorator,
                                           getter_1to1, deleter)
import utool as ut
from ibeis.control.controller_inject import make_ibs_register_decorator
print, print_, printDBG, rrr, profile = ut.inject(__name__, '[manual_chips]')


CLASS_INJECT_KEY, register_ibs_method = make_ibs_register_decorator(__name__)


ANNOT_ROWID   = 'annot_rowid'
CHIP_ROWID    = 'chip_rowid'
FEAT_VECS     = 'feature_vecs'
FEAT_KPTS     = 'feature_keypoints'
FEAT_NUM_FEAT = 'feature_num_feats'
CONFIG_ROWID  = 'config_rowid'

# ---------------------
# ROOT LEAF FUNCTIONS
# ---------------------


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

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.control.manual_chip_funcs import *  # NOQA
        >>> ibs, qreq_ = testdata_ibs()
        >>> aid_list = ibs._get_all_aids()[::3]
        >>> chip_rowid_list = ibs.add_annot_chips(aid_list, qreq_=qreq_)
        >>> assert len(chip_rowid_list) == len(aid_list)
        >>> ut.assert_all_not_None(chip_rowid_list)
    """
    from ibeis.model.preproc import preproc_chip
    # Get requested configuration id
    config_rowid = ibs.get_chip_config_rowid(qreq_=qreq_)
    # Find leaf rowids that need to be computed
    chip_rowid_list = get_annot_chip_rowids_(ibs, aid_list, qreq_=qreq_)
    # Get corresponding "dirty" parent rowids
    dirty_aid_list = ut.get_dirty_items(aid_list, chip_rowid_list)
    if len(dirty_aid_list) > 0:
        if ut.VERBOSE:
            print('[ibs] adding %d / %d chip' %
                  (len(dirty_aid_list), len(aid_list)))
        # Dependant columns do not need true from_superkey getters.
        # We can use the Tgetter_pl_dependant_rowids_ instead
        get_rowid_from_superkey = functools.partial(
            ibs.get_annot_chip_rowids_, qreq_=qreq_)
        proptup_gen = preproc_chip.generate_chip_properties(ibs, aid_list)
        params_iter = (
            (aid, config_rowid, chip_uri, chip_width, chip_height)
            for aid, (chip_uri, chip_width, chip_height,) in
            zip(aid_list, proptup_gen)
        )
        colnames = ['annot_rowid', 'config_rowid',
                    'chip_uri', 'chip_width', 'chip_height']
        chip_rowid_list = ibs.dbcache.add_cleanly(
            const.CHIP_TABLE, colnames, params_iter, get_rowid_from_superkey)
    return chip_rowid_list


@register_ibs_method
def get_annot_chip_rowids(ibs, aid_list, qreq_=None, ensure=False, eager=True, nInput=None):
    """ chip_rowid_list <- annot.chip.rowids[aid_list]

    get chip rowids of annot under the current state configuration
    if ensure is True, this function is equivalent to add_annot_chips

    Args:
        aid_list (list):
        ensure (bool): default false

    Returns:
        list: chip_rowid_list

    TemplateInfo:
        Tgetter_pl_dependant_rowids
        parent = annot
        leaf = chip

    Timeit:
        >>> from ibeis.control.manual_chip_funcs import *  # NOQA
        >>> ibs, qreq_ = testdata_ibs()
        >>> # Test to see if there is any overhead to injected vs native functions
        >>> %timeit get_annot_chip_rowids(ibs, aid_list)
        >>> %timeit ibs.get_annot_chip_rowids(aid_list)

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.control.manual_chip_funcs import *  # NOQA
        >>> ibs, qreq_ = testdata_ibs()
        >>> aid_list = ibs._get_all_aids()
        >>> ensure = False
        >>> chip_rowid_list = ibs.get_annot_chip_rowids(aid_list, qreq_, ensure)
        >>> assert len(chip_rowid_list) == len(aid_list)
    """
    if ensure:
        chip_rowid_list = add_annot_chips(ibs, aid_list, qreq_=qreq_)
    else:
        chip_rowid_list = get_annot_chip_rowids_(
            ibs, aid_list, qreq_=qreq_, eager=eager, nInput=nInput)
    return chip_rowid_list


@register_ibs_method
def get_annot_chip_rowids_(ibs, aid_list, qreq_=None, eager=True, nInput=None):
    """
    equivalent to get_annot_chip_rowids_ except ensure is constrained
    to be False.

    Also you save a stack frame because get_annot_chip_rowids just
    calls this function if ensure is False

    TemplateInfo:
        Tgetter_pl_dependant_rowids_
    """
    colnames = (CHIP_ROWID,)
    config_rowid = ibs.get_chip_config_rowid(qreq_=qreq_)
    andwhere_colnames = (ANNOT_ROWID, CONFIG_ROWID,)
    params_iter = ((aid, config_rowid,) for aid in aid_list)
    chip_rowid_list = ibs.dbcache.get_where2(
        const.CHIP_TABLE, colnames, params_iter, andwhere_colnames, eager=eager, nInput=nInput)
    return chip_rowid_list


@register_ibs_method
@getter_1to1
def get_annot_chip_fpaths(ibs, aid_list, ensure=True, qreq_=None):
    """
    Returns the cached chip uri based off of the current
    configuration.

    Returns:
        chip_fpath_list (list): cfpaths defined by ANNOTATIONs
    """
    cid_list  = ibs.get_annot_chip_rowids(aid_list, ensure=ensure, qreq_=qreq_)
    chip_fpath_list = ibs.get_chip_uris(cid_list)
    return chip_fpath_list


@register_ibs_method
@getter_1to1
def get_annot_chip_thumbpath(ibs, aid_list, thumbsize=None, qreq_=None):
    """
    just constructs the path. does not compute it. that is done by
    api_thumb_delegate
    """
    if thumbsize is None:
        thumbsize = ibs.cfg.other_cfg.thumb_size
    thumb_dpath = ibs.thumb_dpath
    thumb_suffix = '_' + str(thumbsize) + const.CHIP_THUMB_SUFFIX
    annot_uuid_list = ibs.get_annot_visual_uuids(aid_list)
    thumbpath_list = [join(thumb_dpath, const.__STR__(uuid) + thumb_suffix)
                      for uuid in annot_uuid_list]
    return thumbpath_list


@register_ibs_method
@getter_1to1
def get_annot_chip_thumbtup(ibs, aid_list, thumbsize=None, qreq_=None):
    """ get chip thumb info

    Args:
        aid_list  (list):
        thumbsize (int):

    Returns:
        list: thumbtup_list - [(thumb_path, img_path, imgsize, bboxes, thetas)]

    CommandLine:
        python -m ibeis.control.manual_chip_funcs --test-get_annot_chip_thumbtup

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.control.manual_chip_funcs import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> aid_list = ibs.get_valid_aids()
        >>> thumbsize = 128
        >>> result = get_annot_chip_thumbtup(ibs, aid_list, thumbsize)
        >>> print(result)
    """
    #isiterable = isinstance(aid_list, (list, tuple, np.ndarray))
    #if not isiterable:
    #   aid_list = [aid_list]
    # HACK TO MAKE CHIPS COMPUTE
    #cid_list = ibs.get_annot_chip_rowids(aid_list, ensure=True)  # NOQA
    #thumbsize = 256
    if thumbsize is None:
        thumbsize = ibs.cfg.other_cfg.thumb_size
    thumb_gpaths = ibs.get_annot_chip_thumbpath(aid_list, thumbsize=thumbsize, qreq_=qreq_)
    #print(thumb_gpaths)
    chip_paths = ibs.get_annot_chip_fpaths(aid_list, ensure=True, qreq_=qreq_)
    chipsize_list = ibs.get_annot_chip_sizes(aid_list, ensure=False, qreq_=qreq_)
    thumbtup_list = [
        (thumb_path, chip_path, chipsize, [], [])
        for (thumb_path, chip_path, chipsize) in
        zip(thumb_gpaths, chip_paths, chipsize_list,)
    ]
    #if not isiterable:
    #    return thumbtup_list[0]
    return thumbtup_list


@register_ibs_method
@getter_1to1
def get_annot_chips(ibs, aid_list, ensure=True, qreq_=None):
    r"""
    Args:
        ibs (IBEISController):  ibeis controller object
        aid_list (int):  list of annotation ids
        ensure (bool):  eager evaluation if True
        qreq_ (QueryRequest):  query request object with hyper-parameters

    Returns:
        list: chip_list

    CommandLine:
        python -m ibeis.control.manual_chip_funcs --test-get_annot_chips

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.control.manual_chip_funcs import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> aid_list = ibs.get_valid_aids()[0:5]
        >>> ensure = True
        >>> qreq_ = None
        >>> chip_list = get_annot_chips(ibs, aid_list, ensure, qreq_)
        >>> chip_sum_list = list(map(np.sum, chip_list))
        >>> ut.assert_almost_eq(chip_sum_list, [96053500, 65152954, 67223241, 109358624, 73995960], 100)
        >>> print(chip_sum_list)
    """
    ut.assert_all_not_None(aid_list, 'aid_list')
    cid_list = ibs.get_annot_chip_rowids(aid_list, ensure=ensure, qreq_=qreq_)
    chip_list = ibs.get_chips(cid_list, ensure=ensure)
    return chip_list


@register_ibs_method
@getter_1to1
#@cache_getter(const.ANNOTATION_TABLE, 'chipsizes')
def get_annot_chip_sizes(ibs, aid_list, ensure=True, qreq_=None):
    """
    Args:
        ibs (IBEISController):  ibeis controller object
        aid_list (int):  list of annotation ids
        ensure (bool):  eager evaluation if True

    Returns:
        list: chipsz_list - the (width, height) of computed annotation chips.

    CommandLine:
        python -m ibeis.control.manual_chip_funcs --test-get_annot_chip_sizes

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.control.manual_chip_funcs import *  # NOQA
        >>> import ibeis
        >>> # build test data
        >>> ibs = ibeis.opendb('testdb1')
        >>> aid_list = ibs.get_valid_aids()[0:3]
        >>> ensure = True
        >>> # execute function
        >>> chipsz_list = get_annot_chip_sizes(ibs, aid_list, ensure)
        >>> # verify results
        >>> result = str(chipsz_list)
        >>> print(result)
        [(545, 372), (603, 336), (520, 390)]
    """
    cid_list  = ibs.get_annot_chip_rowids(aid_list, ensure=ensure, qreq_=qreq_)
    chipsz_list = ibs.get_chip_sizes(cid_list)
    return chipsz_list


@register_ibs_method
def get_annot_chip_dlensqrd(ibs, aid_list, qreq_=None):
    r"""
    Args:
        ibs (IBEISController):  ibeis controller object
        aid_list (list):

    Returns:
        list: topx2_dlen_sqrd

    CommandLine:
        python -m ibeis.control.manual_chip_funcs --test-get_annot_chip_dlensqrd

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.control.manual_chip_funcs import *  # NOQA
        >>> import ibeis
        >>> # build test data
        >>> ibs = ibeis.opendb('testdb1')
        >>> aid_list = ibs.get_valid_aids()
        >>> qreq_ = None
        >>> # execute function
        >>> topx2_dlen_sqrd = ibs.get_annot_chip_dlensqrd(aid_list, qreq_=qreq_)
        >>> # verify results
        >>> result = str(topx2_dlen_sqrd)
        >>> print(result)
        [435409, 476505, 422500, 422500, 422500, 437924, 405000, 405000, 447805, 420953, 405008, 406265, 512674]
    """
    topx2_dlen_sqrd = [
        ((w ** 2) + (h ** 2))
        for (w, h) in ibs.get_annot_chip_sizes(aid_list, qreq_=qreq_)
    ]
    return topx2_dlen_sqrd


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


# ---------------------
# NATIVE CHIP FUNCTIONS
# ---------------------


@register_ibs_method
def _get_all_chip_rowids(ibs):
    """ all_chip_rowids <- chip.get_all_rowids()

    Returns:
        list_ (list): unfiltered chip_rowids

    TemplateInfo:
        Tider_all_rowids
        tbl = chip

    Example:
        >>> # ENABLE_DOCTEST
        >>> ibs, qreq_ = testdata_ibs()
        >>> ibs._get_all_chip_rowids()
    """
    all_chip_rowids = ibs.dbcache.get_all_rowids(const.CHIP_TABLE)
    return all_chip_rowids


@register_ibs_method
@ider
def get_valid_cids(ibs, qreq_=None):
    """ Valid chip rowids of the current configuration """
    # FIXME: configids need reworking
    chip_config_rowid = ibs.get_chip_config_rowid(qreq_=qreq_)
    cid_list = ibs.dbcache.get_all_rowids_where(const.FEATURE_TABLE, 'config_rowid=?', (chip_config_rowid,))
    return cid_list


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
def get_chip_detectpaths(ibs, cid_list):
    """
    Returns:
        new_gfpath_list (list): a list of image paths resized to a constant area for detection
    """
    from ibeis.model.preproc import preproc_detectimg
    new_gfpath_list = preproc_detectimg.compute_and_write_detectchip_lazy(ibs, cid_list)
    return new_gfpath_list


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

    Args:
        cid_list (list):
        ensure (bool):  eager evaluation if True

    Returns:
        list: chip_list
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


def testdata_ibs():
    import ibeis
    ibs = ibeis.opendb('testdb1')
    qreq_ = None
    return ibs, qreq_


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.control.manual_feat_funcs
        python -m ibeis.control.manual_feat_funcs --allexamples
        python -m ibeis.control.manual_feat_funcs --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
