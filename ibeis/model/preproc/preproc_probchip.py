"""
Preprocess Probability Chips

Uses random forests code to detect the probability that pixel belongs to the
forground.

TODO:
    * Create a probchip controller table.
    * Integrate into the the controller using autogen functions.
        - get_probchip_fpaths, get_annot_probchip_fpath, add_annot_probchip

    * User should be able to manually paint on a chip to denote the foreground
      when the randomforest algorithm messes up.
"""
from __future__ import absolute_import, division, print_function
from six.moves import zip
from ibeis.model.preproc import preproc_chip
from ibeis.model.detect import randomforest
from os.path import splitext
import utool  # NOQA
import utool as ut
import vtool
import numpy as np
import vtool as vt
from os.path import exists
import vtool.chip as ctool
import vtool.image as gtool
# VTool
#import vtool.chip as ctool
#import vtool.image as gtool
(print, print_, printDBG, rrr, profile) = ut.inject(
    __name__, '[preproc_probchip]', DEBUG=False)


def postprocess_dev():
    """
    References:
        http://opencv-python-tutroals.readthedocs.org/en/latest/py_tutorials/py_imgproc/py_morphological_ops/py_morphological_ops.html

    CommandLine:
        python -m ibeis.model.preproc.preproc_probchip --test-postprocess_dev
        python -m ibeis.model.preproc.preproc_probchip --test-postprocess_dev --db Elephants_drop1_ears

    CommandLine:
        python -m ibeis.model.preproc.preproc_probchip --test-postprocess_dev

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.model.preproc.preproc_probchip import *  # NOQA
        >>> # build test data
        >>> # execute function
        >>> result = postprocess_dev()
        >>> # verify results
        >>> print(result)
    """
    from plottool import df2 as df2
    import cv2
    import numpy as np  # NOQA

    #fpath = '/media/raid/work/GZ_ALL/_ibsdb/figures/nsum_hard/qaid=420_res_5ujbs8h&%vw1olnx_quuid=31cfdc3e/probchip_aid=478_auuid=5c327c5d-4bcc-22e4-764e-535e5874f1c7_CHIP(sz450)_FEATWEIGHT(ON,uselabel,rf)_CHIP()_zebra_grevys.png.png'
    import ibeis
    ibs = ibeis.opendb(defaultdb='PZ_MTEST')
    aid_list = ibs.get_valid_aids()

    def test_grabcut_on_aid(aid):
        chip_fpath = ibs.get_annot_chip_fpath(aid)
        probchip_fpath = ibs.get_annot_probchip_fpath(aid)

        chip_img = cv2.imread(chip_fpath)
        probchip_img = cv2.imread(probchip_fpath, flags=cv2.IMREAD_GRAYSCALE)

        label_values = [cv2.GC_BGD, cv2.GC_PR_BGD, cv2.GC_PR_FGD, cv2.GC_FGD]

        def probchip_to_grabcut_labels(probchip_img, w, h):
            scaled_probchip = cv2.resize(probchip_img, dsize=(w, h))
            mask = (len(label_values) * (scaled_probchip / 255)).astype(np.uint8)
            # No certainty
            mask[mask == 3] = 2
            # Except for one center pixel
            #mask[mask.shape[0] // 2, mask.shape[1] // 2] = 3
            label_mask = mask.copy()
            for index, value in enumerate(label_values):
                label_mask[mask == index] = value
            return label_mask

        def grabcut_labels_to_probchip(label_mask):
            image_mask = label_mask.copy()
            label_colors = np.linspace(0, 255, len(label_values)).astype(np.uint8)
            for value, color in zip(label_values, label_colors):
                image_mask[label_mask == value] = (color)
            return image_mask

        def grabcut_from_probchip(chip_img, label_mask):
            rect = (0, 0, w, h)
            bgd_model = np.zeros((1, 13 * 5), np.float64)
            fgd_model = np.zeros((1, 13 * 5), np.float64)
            num_iters = 5
            mode = cv2.GC_INIT_WITH_MASK
            # label_mask is an outvar
            label_mask_ = label_mask.copy()
            cv2.grabCut(chip_img, label_mask_, rect, bgd_model, fgd_model, num_iters, mode=mode)
            #is_foreground = (label_mask == cv2.GC_FGD) + (label_mask == cv2.GC_PR_FGD)
            #is_foreground = (label_mask_ == cv2.GC_FGD)  # + (label_mask == cv2.GC_PR_FGD)
            return label_mask_

        (h, w) = chip_img.shape[0:2]
        label_mask = probchip_to_grabcut_labels(probchip_img, w, h)
        label_mask_ = grabcut_from_probchip(chip_img, label_mask)
        float_mask = grabcut_labels_to_probchip(label_mask_) / 255.0
        segmented_chip = chip_img * float_mask[:, :, None]

        next_pnum = df2.make_pnum_nextgen(2, 3)
        df2.imshow(chip_img,                               fnum=1, pnum=next_pnum())
        df2.imshow(probchip_img,                           fnum=1, pnum=next_pnum())
        df2.imshow(grabcut_labels_to_probchip(label_mask), fnum=1, pnum=next_pnum())
        df2.imshow(segmented_chip,                         fnum=1, pnum=next_pnum())
        df2.imshow(255 * (float_mask),                  fnum=1, pnum=next_pnum())
        df2.imshow(chip_img * (float_mask > .6)[:, :, None],   fnum=1, pnum=next_pnum())
        df2.present()
    aid = aid_list[0]
    for aid in ut.InteractiveIter(aid_list):
        test_grabcut_on_aid(aid)
        #input('press enter to continue')
    #kernel = np.ones((5, 5), np.uint8)
    #blur = cv2.GaussianBlur(img, (5, 5), 1.6)
    #dilation = cv2.dilate(img, kernel, iterations=10)
    #df2.imshow(blur, fnum=2)
    #df2.imshow(dilation, fnum=3)
    #cv2.floodFill(image, mask, seedPoint, newVal)
    #closing = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel, iterations=5)
    #df2.imshow(closing, fnum=4)
    pass


def group_aids_by_featweight_species(ibs, aid_list, config2_=None):
    """ helper

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.preproc.preproc_probchip import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> config2_ = None
        >>> aid_list = ibs.get_valid_aids()
        >>> grouped_aids, unique_species = group_aids_by_featweight_species(ibs, aid_list, config2_)
    """
    if config2_ is None:
        featweight_species = ibs.cfg.featweight_cfg.featweight_species
    else:
        featweight_species = config2_.get('featweight_species')
        assert featweight_species is not None
    if featweight_species == 'uselabel':
        # Use the labeled species for the detector
        species_list = ibs.get_annot_species_texts(aid_list)
    else:
        species_list = [featweight_species]
    aid_list = np.array(aid_list)
    species_list = np.array(species_list)
    species_rowid = np.array(ibs.get_species_rowids_from_text(species_list))
    unique_species_rowids, groupxs = vtool.group_indices(species_rowid)
    grouped_aids    = vtool.apply_grouping(aid_list, groupxs)
    grouped_species = vtool.apply_grouping(species_list, groupxs)
    unique_species = ut.get_list_column(grouped_species, 0)
    return grouped_aids, unique_species, groupxs


def get_probchip_fname_fmt(ibs, config2_=None, species=None):
    """ Returns format of probability chip file names

    Args:
        ibs (IBEISController):
        suffix (None):

    Returns:
        probchip_fname_fmt

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.preproc.preproc_probchip import *  # NOQA
        >>> from ibeis.model.preproc import preproc_chip
        >>> ibs, aid_list = preproc_chip.testdata_ibeis()
        >>> config2_ = None
        >>> probchip_fname_fmt = get_probchip_fname_fmt(ibs)
        >>> #want = 'probchip_aid=%d_bbox=%s_CHIP(sz450)_FEATWEIGHT(ON,uselabel,rf)_CHIP().png'
        >>> #assert probchip_fname_fmt == want, probchip_fname_fmt
        >>> result = probchip_fname_fmt
        >>> print(result)
        probchip_avuuid={avuuid}_CHIP(sz450)_FEATWEIGHT(OFF).png

        probchip_avuuid={avuuid}_CHIP(sz450)_FEATWEIGHT(ON,uselabel,rf).png


    probchip_aid=%d_bbox=%s_theta=%s_gid=%d_CHIP(sz450)_FEATWEIGHT(ON,uselabel,rf)_CHIP().png
    """
    cfname_fmt = preproc_chip.get_chip_fname_fmt(ibs, config2_=config2_)

    if config2_ is None:
        # FIXME FIXME FIXME: ugly, bad code that wont generalize at all.
        # you can compute probchips correctly only once, if you change anything
        # you have to delete your cache.
        probchip_cfgstr = ibs.cfg.featweight_cfg.get_cfgstr(use_feat=False, use_chip=False)
    else:
        probchip_cfgstr = config2_.get('probchip_cfgstr')
        assert probchip_cfgstr is not None
        #raise NotImplementedError('config2_ is not None')

    suffix = probchip_cfgstr
    if species is not None:
        # HACK, we sortof know the species here already from the
        # config string, but this helps in case we mess the config up
        suffix += '_' + species
    #probchip_cfgstr = ibs.cfg.detect_cfg.get_cfgstr()   # algo settings cfgstr
    fname_noext, ext = splitext(cfname_fmt)
    probchip_fname_fmt = ''.join(['prob', fname_noext, suffix, ext])
    return probchip_fname_fmt


def get_annot_probchip_fpath_list(ibs, aid_list, config2_=None, species=None):
    """ Build probability chip file paths based on the current IBEIS configuration

    Args:
        ibs (IBEISController):
        aid_list (list):
        suffix (None):

    Returns:
        probchip_fpath_list

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.preproc.preproc_probchip import *  # NOQA
        >>> from os.path import basename
        >>> ibs, aid_list = preproc_chip.testdata_ibeis()
        >>> config2_ = None
        >>> probchip_fpath_list = get_annot_probchip_fpath_list(ibs, aid_list)
        >>> result = ut.relpath_unix(probchip_fpath_list[1], ibs.get_dbdir())
        >>> print(result)
        _ibsdb/_ibeis_cache/prob_chips/probchip_avuuid=5a1a53ba-fd44-b113-7f8c-fcf248d7047f_CHIP(sz450)_FEATWEIGHT(OFF).png

        _ibsdb/_ibeis_cache/prob_chips/probchip_avuuid=5a1a53ba-fd44-b113-7f8c-fcf248d7047f_CHIP(sz450)_FEATWEIGHT(ON,uselabel,rf).png

    probchip_aid=5_bbox=(0,0,1072,804)_theta=0.0tau_gid=5_CHIP(sz450)_FEATWEIGHT(ON,uselabel,rf)_CHIP().png
    """
    ibs.probchipdir = ibs.get_probchip_dir()
    cachedir = ibs.get_probchip_dir()
    ut.ensuredir(cachedir)
    probchip_fname_fmt = get_probchip_fname_fmt(ibs, config2_=config2_, species=species)
    #probchip_fpath_list = preproc_chip.format_aid_bbox_theta_gid_fnames(
    #    ibs, aid_list, probchip_fname_fmt, cachedir)
    annot_visual_uuid_list  = ibs.get_annot_visual_uuids(aid_list)
    probchip_fpath_list = [ut.unixjoin(cachedir, probchip_fname_fmt.format(avuuid=avuuid)) for avuuid in annot_visual_uuid_list]
    return probchip_fpath_list


def compute_and_write_probchip(ibs, aid_list, config2_=None, lazy=True):
    """ Computes probability chips using pyrf

    CommandLine:
        python -m ibeis.model.preproc.preproc_probchip --test-compute_and_write_probchip:0 --show
        python -m ibeis.model.preproc.preproc_probchip --test-compute_and_write_probchip:1
        python -m ibeis.model.preproc.preproc_probchip --test-compute_and_write_probchip:2 --show --cnn

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.preproc.preproc_probchip import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('PZ_MTEST')
        >>> config2_ = None
        >>> lazy = True
        >>> aid_list = ibs.get_valid_aids(species=ibeis.const.Species.ZEB_PLAIN)[0:4]
        >>> probchip_fpath_list_ = compute_and_write_probchip(ibs, aid_list, config2_, lazy=lazy)
        >>> result = ut.list_str(probchip_fpath_list_)
        >>> print(result)
        >>> ut.quit_if_noshow()
        >>> import plottool as pt
        >>> iteract_obj = pt.interact_multi_image.MultiImageInteraction(probchip_fpath_list_, nPerPage=4)
        >>> ut.show_if_requested()

    Example:
        >>> # SLOW_DOCTEST
        >>> from ibeis.model.preproc.preproc_probchip import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> config2_ = None
        >>> lazy = False
        >>> aid_list = ibs.get_valid_aids(species=ibeis.const.Species.ZEB_PLAIN)
        >>> probchip_fpath_list_ = compute_and_write_probchip(ibs, aid_list, config2_, lazy=lazy)
        >>> result = ut.list_str(probchip_fpath_list_)
        >>> print(result)

    Example2:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.model.preproc.preproc_probchip import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> config2_ = ibs.new_query_params({'featweight_detector': 'cnn'})
        >>> lazy = True
        >>> aid_list = ibs.get_valid_aids()
        >>> probchip_fpath_list_ = compute_and_write_probchip(ibs, aid_list, config2_, lazy=lazy)
        >>> result = ut.list_str(probchip_fpath_list_)
        >>> print(result)
        >>> ut.quit_if_noshow()
        >>> import plottool as pt
        >>> iteract_obj = pt.interact_multi_image.MultiImageInteraction(probchip_fpath_list_, nPerPage=4)
        >>> ut.show_if_requested()

    Dev::
        #ibs.delete_annot_chips(aid_list)
        #probchip_fpath_list = get_annot_probchip_fpath_list(ibs, aid_list)
    """
    # Get probchip dest information (output path)
    # TODO; properly ungroup output
    grouped_aids, unique_species, groupxs = group_aids_by_featweight_species(ibs, aid_list, config2_)
    nSpecies = len(unique_species)
    nTasks = len(aid_list)
    print('[preproc_probchip.compute_and_write_probchip] Preparing to compute %d probchips of %d species' % (nTasks, nSpecies))
    cachedir = ibs.get_probchip_dir()
    ut.ensuredir(cachedir)

    grouped_probchip_fpath_list = []
    if ut.VERBOSE:
        print('[preproc_probchip] +--------------------')
    for aids, species in zip(grouped_aids, unique_species):
        if ut.VERBOSE:
            print('[preproc_probchip] Computing probchips for species=%r' % species)
            print('[preproc_probchip] |--------------------')
        if len(aids) == 0:
            continue
        probchip_fpaths = get_annot_probchip_fpath_list(ibs, aids, config2_=config2_, species=species)

        if lazy:
            # Filter out probchips that are already on disk
            # pyrf used to do this, now we need to do it
            # caching should be implicit due to using the visual_annot_uuid in
            # the filename
            isdirty_list = ut.not_list(map(exists, probchip_fpaths))
            dirty_aids = ut.filter_items(aids, isdirty_list)
            dirty_probchip_fpath_list = ut.filter_items(probchip_fpaths, isdirty_list)
            print('[preproc_probchip.compute_and_write_probchip] Lazy compute of to compute %d/%d of species=%s' %
                  (len(dirty_aids), len(aids), species))
        else:
            # No filtering
            dirty_aids  = aids
            dirty_probchip_fpath_list = probchip_fpaths

        if len(dirty_aids) > 0:
            write_dirty_aids(ibs, dirty_probchip_fpath_list, dirty_aids, config2_, species)

        grouped_probchip_fpath_list.append(probchip_fpaths)
    if ut.VERBOSE:
        print('[preproc_probchip] Done computing probability images')
        print('[preproc_probchip] L_______________________')

    probchip_fpath_list = vt.invert_apply_grouping2(grouped_probchip_fpath_list, groupxs, dtype=object)
    return probchip_fpath_list


def write_dirty_aids(ibs, dirty_probchip_fpath_list, dirty_aids, config2_, species):
    if config2_ is None:
        featweight_detector = ibs.cfg.featweight_cfg.featweight_detector
    else:
        featweight_detector = config2_.get('featweight_detector')

    if featweight_detector == 'rf':
        (extramargin_fpath_list,
         probchip_extramargin_fpath_list,
         halfoffset_cs_list,
         ) = compute_extramargin_detectchip(ibs, dirty_aids, config2_=config2_, species=species, FACTOR=4)
        #dirty_cfpath_list  = ibs.get_annot_chip_fpath(dirty_aids, ensure=True, config2_=config2_)

        config = {
            'scale_list': [1.0],
            'output_gpath_list': probchip_extramargin_fpath_list,
            'mode': 1,
        }
        probchip_generator = randomforest.detect_gpath_list_with_species(ibs, extramargin_fpath_list, species, **config)
        # Evalutate genrator until completion
        ut.evaluate_generator(probchip_generator)
        extramargin_mask_gen = (vt.imread(fpath, grayscale=True) for fpath in probchip_extramargin_fpath_list)

        # Crop the extra margin off of the new probchips
        _iter = zip(dirty_probchip_fpath_list,
                    extramargin_mask_gen,
                    halfoffset_cs_list)
        for (probchip_fpath, extramargin_probchip, halfmargin) in _iter:
            half_w, half_h = halfmargin
            probchip = extramargin_probchip[half_h:-half_h, half_w:-half_w]
            vt.imwrite(probchip_fpath, probchip)
    elif featweight_detector == 'cnn':
        # dont use extrmargin here (for now)
        chip_fpath_list = ibs.get_annot_chip_fpath(dirty_aids, config2_=config2_)
        mask_gen = ibs.generate_species_background_mask(chip_fpath_list, species)
        for probchip_fpath, probchip in zip(dirty_probchip_fpath_list, mask_gen):
            probchip = postprocess_mask(probchip)
            vt.imwrite(probchip_fpath, probchip)
    else:
        raise NotImplementedError('bad featweight_detector=%r' % (featweight_detector,))


def postprocess_mask(mask):
    r"""
    Args:
        mask (ndarray):

    Returns:
        ndarray: mask2

    CommandLine:
        python -m ibeis.model.preproc.preproc_probchip --exec-postprocess_mask --cnn --show

    Example:
        >>> # DISABLE_DOCTEST
        >>> import ibeis_cnn
        >>> import ibeis
        >>> import vtool as vt
        >>> import plottool as pt
        >>> from ibeis.model.preproc.preproc_probchip import *  # NOQA
        >>> ibs = ibeis.opendb(defaultdb='testdb1')
        >>> chip_fpath = ibs.get_annot_chip_fpath([10])[0]
        >>> chip = vt.imread(chip_fpath)
        >>> mask_list = list(ibs.generate_species_background_mask([chip_fpath]))
        >>> mask = mask_list[0]
        >>> mask2 = postprocess_mask(mask)
        >>> ut.quit_if_noshow()
        >>> fnum = 1
        >>> pt.imshow(chip, pnum=(1, 3, 1), fnum=fnum)
        >>> pt.imshow(mask, pnum=(1, 3, 2), fnum=fnum, title='before')
        >>> pt.imshow(mask2, pnum=(1, 3, 3), fnum=fnum, title='after')
        >>> ut.show_if_requested()
    """
    import cv2
    thresh = 20
    kernel_size = 20
    mask2 = mask.copy()
    # light threshold
    mask2[mask2 < thresh] = 0
    # open and close
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    mask2 = cv2.morphologyEx(mask2, cv2.MORPH_OPEN, kernel)
    mask2 = cv2.morphologyEx(mask2, cv2.MORPH_CLOSE, kernel)
    return mask2


def gen_detectchip(tup):
    r"""
    Parallel worker. Crops chip out of an image, applies filters, etc
    """
    cfpath, gfpath, bbox, theta, new_size, filter_list = tup
    chipBGR = ctool.compute_chip(gfpath, bbox, theta, new_size, filter_list)
    gtool.imwrite(cfpath, chipBGR)
    return cfpath


def compute_extramargin_detectchip(ibs, aid_list, config2_=None, species=None, FACTOR=4):
    #from vtool import chip as ctool
    #from vtool import image as gtool
    arg_list, newsize_list, halfoffset_cs_list = get_extramargin_detectchip_info(ibs, aid_list, config2_=config2_, species=species, FACTOR=FACTOR)
    # Again, it seems we cannot use warpAffine in parallel loops
    extramargin_fpath_list = list(ut.generate(gen_detectchip, arg_list, ordered=True, force_serial=True))
    probchip_extramargin_fpath_list   = [fpath.replace('detectchip', 'probchip') for fpath in extramargin_fpath_list]
    return extramargin_fpath_list, probchip_extramargin_fpath_list, halfoffset_cs_list
    #probchip_extramargin_fpath_list = []
    #chipBGR = vt.imread(fpath)
    #print(chipBGR.shape)
    #assert chipBGR.shape[1] == 160
    #for cfpath, gfpath, bbox, theta, new_size, filter_list in arg_list:
    #    chipBGR = ctool.compute_chip(gfpath, bbox, theta, new_size, filter_list)
    #    gtool.imwrite(cfpath, chipBGR)
    #    probchip_extramargin_fpath_list.append(cfpath)


def get_extramargin_detectchip_info(ibs, aid_list, config2_=None, species=None, FACTOR=4):
    r"""
    Computes a detection chip with a bit of spatial context so the detection algorithm doesn't clip boundaries

    CommandLine:
        python -m ibeis.model.preproc.preproc_probchip --test-get_extramargin_detectchip_info --show
        python -m ibeis.model.preproc.preproc_probchip --test-get_extramargin_detectchip_info --show --qaid 27
        python -m ibeis.model.preproc.preproc_probchip --test-get_extramargin_detectchip_info --show --qaid 2

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.model.preproc.preproc_probchip import *  # NOQA
        >>> import ibeis
        >>> from ibeis.init import main_helpers
        >>> ibs = ibeis.opendb('PZ_MTEST')
        >>> aid_list = main_helpers.get_test_qaids(ibs)
        >>> arg_list, newsize_list, halfoffset_cs_list = get_extramargin_detectchip_info(ibs, aid_list)
        >>> ut.quit_if_noshow()
        >>> testshow_extramargin_info(ibs, aid_list, arg_list, newsize_list, halfoffset_cs_list)
    """
    from vtool import chip as ctool
    target_width = 128 * FACTOR
    gfpath_list = ibs.get_annot_image_paths(aid_list)
    bbox_list   = ibs.get_annot_bboxes(aid_list)
    theta_list  = ibs.get_annot_thetas(aid_list)
    bbox_size_list = ut.get_list_column(bbox_list, [2, 3])
    newsize_list = list(map(lambda size: ctool.get_scaled_size_with_width(target_width, *size), bbox_size_list))
    invalid_aids = [aid for aid, (w, h) in zip(aid_list, bbox_size_list) if w == 0 or h == 0]
    if len(invalid_aids) > 0:
        msg = ("REMOVE INVALID (BAD WIDTH AND/OR HEIGHT) AIDS TO COMPUTE AND WRITE CHIPS")
        msg += ("INVALID AIDS: %r" % (invalid_aids, ))
        print(msg)
        raise Exception(msg)
    # There are two spaces we are working in here
    # probchipspace _pcs (the space of the margined chip computed for probchip) and
    # imagespace _gs (the space using in bbox specification)

    # Compute the offset we would like in chip space for margin expansion
    halfoffset_cs_list = [
        # TODO: Find correct offsets
        (16 * FACTOR, 16 * FACTOR)  # (w / 16, h / 16)
        for (w, h) in newsize_list
    ]

    # Compute expanded newsize list to include the extra margin offset
    expanded_newsize_list = [
        (w_pcs + (2 * xo_pcs), h_pcs + (2 * yo_pcs))
        for (w_pcs, h_pcs), (xo_pcs, yo_pcs) in zip(newsize_list, halfoffset_cs_list)
    ]

    # Get the conversion from chip to image space
    to_imgspace_scale_factors = [
        (w_gs / w_pcs, h_gs / h_pcs)
        for ((w_pcs, h_pcs), (w_gs, h_gs)) in zip(newsize_list, bbox_size_list)
    ]

    # Convert the chip offsets to image space
    halfoffset_gs_list = [
        ((sx * xo), (sy * yo))
        for (sx, sy), (xo, yo) in zip(to_imgspace_scale_factors, halfoffset_cs_list)
    ]

    # Find the size of the expanded margin bbox in image space
    expanded_bbox_gs_list = [
        (x_gs - xo_gs, y_gs - yo_gs, w_gs + (2 * xo_gs), h_gs + (2 * yo_gs))
        for (x_gs, y_gs, w_gs, h_gs), (xo_gs, yo_gs) in zip(bbox_list, halfoffset_gs_list)
    ]

    # TODO: make this work
    probchip_fpath_list = get_annot_probchip_fpath_list(ibs, aid_list, config2_=config2_, species=species)
    #probchip_extramargin_fpath_list = [ut.augpath(fpath, '_extramargin') for fpath in probchip_fpath_list]
    extramargin_fpath_list = [ut.augpath(fpath, '_extramargin').replace('probchip', 'detectchip')
                              for fpath in probchip_fpath_list]
    # # filter by species and add a suffix for the probchip_input
    # # also compute a probchip fpath with an expanded suffix for the detector
    #probchip_fpath_list = get_annot_probchip_fpath_list(ibs, aids, config2_=None, species=species)
    # Then crop the output and write that as the real probchip

    filtlist_iter = ([] for _ in range(len(aid_list)))
    arg_iter = zip(extramargin_fpath_list, gfpath_list,
                   expanded_bbox_gs_list, theta_list, expanded_newsize_list,
                   filtlist_iter)
    arg_list = list(arg_iter)
    return arg_list, newsize_list, halfoffset_cs_list


def testshow_extramargin_info(ibs, aid_list, arg_list, newsize_list, halfoffset_cs_list):
    #cfpath, gfpath, bbox, theta, new_size, filter_list = tup
    # TEMP TESTING
    from vtool import chip as ctool
    import plottool as pt
    import vtool as vt
    from ibeis.viz import viz_chip

    index = 0
    cfpath, gfpath, bbox, theta, new_size, filter_list = arg_list[index]
    chipBGR = ctool.compute_chip(gfpath, bbox, theta, new_size, filter_list)
    bbox_cs_list = [
        (xo_pcs, yo_pcs, w_pcs, h_pcs)
        for (w_pcs, h_pcs), (xo_pcs, yo_pcs) in zip(newsize_list, halfoffset_cs_list)
    ]
    bbox_pcs = bbox_cs_list[index]
    aid = aid_list[0]
    print('new_size = %r' % (new_size,))
    print('newsize_list[index] = %r' % (newsize_list[index],))

    fnum = 1
    viz_chip.show_chip(ibs, aid, pnum=(1, 3, 1), fnum=fnum, annote=False, in_image=True , title_suffix='\noriginal image')
    viz_chip.show_chip(ibs, aid, pnum=(1, 3, 2), fnum=fnum, annote=False, title_suffix='\noriginal chip')
    bboxed_chip = vt.draw_verts(chipBGR, vt.scaled_verts_from_bbox(bbox_pcs, theta, 1, 1))
    pt.imshow(bboxed_chip, pnum=(1, 3, 3), fnum=fnum, title='scaled chip with expanded margin.\n(orig margin drawn in orange)')

    pt.show_if_requested()
    #pt.imshow(chipBGR)


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.model.preproc.preproc_probchip
        python -m ibeis.model.preproc.preproc_probchip --allexamples
        python -m ibeis.model.preproc.preproc_probchip --allexamples --serial --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()
    import utool as ut  # NOQA
    ut.doctest_funcs()
