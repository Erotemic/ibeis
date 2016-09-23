# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals
from six.moves import zip, map
import dtool
import utool as ut
import vtool as vt
import pyflann
from ibeis.algo.smk import pickle_flann
import numpy as np
import warnings
#from ibeis import core_annots
from ibeis.control.controller_inject import register_preprocs
(print, rrr, profile) = ut.inject2(__name__)


derived_attribute = register_preprocs['annot']


class VocabConfig(dtool.Config):
    _param_info_list = [
        ut.ParamInfo('algorithm', 'minibatch', 'alg'),
        ut.ParamInfo('random_seed', 42, 'seed'),
        ut.ParamInfo('num_words', 1000, 'n'),
        #ut.ParamInfo('num_words', 64000),
        ut.ParamInfo('version', 1),
        #ut.ParamInfo('n_jobs', -1, hide=True),
    ]


class InvertedIndexConfig(dtool.Config):
    _param_info_list = [
        ut.ParamInfo('nAssign', 2),
        #ut.ParamInfo('int_rvec', False, hideif=False),
        ut.ParamInfo('int_rvec', True, hideif=False),
        ut.ParamInfo('inva_version', 2)
        #massign_alpha=1.2,
        #massign_sigma=80.0,
        #massign_equal_weights=False
    ]


@ut.reloadable_class
class VisualVocab(ut.NiceRepr):
    """
    Class that maintains a list of visual words (cluster centers)
    Also maintains a nearest neighbor index structure for finding words.
    This class is build using the depcache
    """

    def __init__(vocab, words=None):
        vocab.wx_to_word = words
        vocab.wordflann = None
        vocab.flann_params = vt.get_flann_params(random_seed=42)
        # TODO: grab the depcache rowid and maybe config?
        # make a dtool.Computable

    def __nice__(vocab):
        return 'nW=%r' % (ut.safelen(vocab.wx_to_word))

    def __len__(vocab):
        return len(vocab.wx_to_word)

    @property
    def shape(vocab):
        return vocab.wx_to_word.shape

    def __getstate__(vocab):
        """
        http://www.linuxscrew.com/2010/03/24/fastest-way-to-create-ramdisk-in-ubuntulinux/
        sudo mkdir /tmp/ramdisk; chmod 777 /tmp/ramdisk
        sudo mount -t tmpfs -o size=256M tmpfs /tmp/ramdisk/
        http://zeblog.co/?p=1588
        """
        state = vocab.__dict__.copy()
        if 'wx2_word' in state:
            state['wx_to_word'] = state.pop('wx2_word')
        state['wordindex_bytes'] = vocab.wordflann.dumps()
        del state['wordflann']
        return state

    def __setstate__(vocab, state):
        wordindex_bytes = state.pop('wordindex_bytes')
        vocab.__dict__.update(state)
        #flannclass = pyflann.FLANN
        flannclass = pickle_flann.PickleFLANN
        vocab.wordflann = flannclass()
        try:
            vocab.wordflann.loads(wordindex_bytes, vocab.wx_to_word)
        except Exception:
            print('Fixing vocab problem')
            vocab.build()

    def build(vocab, verbose=True):
        num_vecs = len(vocab.wx_to_word)
        if vocab.wordflann is None:
            #flannclass = pyflann.FLANN
            flannclass = pickle_flann.PickleFLANN
            vocab.wordflann = flannclass()
        if verbose:
            print(' ...build kdtree with %d points (may take a sec).' % num_vecs)
            tt = ut.tic(msg='Building vocab index')
        if num_vecs == 0:
            print('WARNING: CANNOT BUILD FLANN INDEX OVER 0 POINTS.')
            print('THIS MAY BE A SIGN OF A DEEPER ISSUE')
        else:
            vocab.wordflann.build_index(vocab.wx_to_word, **vocab.flann_params)
        if verbose:
            ut.toc(tt)

    def nn_index(vocab, idx_to_vec, nAssign):
        """
            >>> idx_to_vec = depc.d.get_feat_vecs(aid_list)[0]
            >>> vocab = vocab
            >>> nAssign = 1
        """
        # Assign each vector to the nearest visual words
        assert nAssign > 0, 'cannot assign to 0 neighbors'
        try:
            idx_to_vec = idx_to_vec.astype(vocab.wordflann._FLANN__curindex_data.dtype)
            _idx_to_wx, _idx_to_wdist = vocab.wordflann.nn_index(idx_to_vec, nAssign)
        except pyflann.FLANNException as ex:
            ut.printex(ex, 'probably misread the cached flann_fpath=%r' % (
                getattr(vocab.wordflann, 'flann_fpath', None),))
            raise
        else:
            _idx_to_wx = vt.atleast_nd(_idx_to_wx, 2)
            _idx_to_wdist = vt.atleast_nd(_idx_to_wdist, 2)
            return _idx_to_wx, _idx_to_wdist

    def assign_to_words(vocab, idx_to_vec, nAssign, massign_alpha=1.2,
                        massign_sigma=80.0, massign_equal_weights=False, verbose=None):
        """
        Assigns descriptor-vectors to nearest word.

        Args:
            wordflann (FLANN): nearest neighbor index over words
            words (ndarray): vocabulary words
            idx_to_vec (ndarray): descriptors to assign
            nAssign (int): number of words to assign each descriptor to
            massign_alpha (float): multiple-assignment ratio threshold
            massign_sigma (float): multiple-assignment gaussian variance
            massign_equal_weights (bool): assign equal weight to all multiassigned words

        Returns:
            tuple: inverted index, multi-assigned weights, and forward index
            formated as::

                * wx_to_idxs - word index   -> vector indexes
                * wx_to_maws - word index   -> multi-assignment weights
                * idf2_wxs - vector index -> assigned word indexes

        Example:
            >>> # SLOW_DOCTEST
            >>> idx_to_vec = depc.d.get_feat_vecs(aid_list)[0][0::300]
            >>> idx_to_vec = np.vstack((idx_to_vec, vocab.wx_to_word[0]))
            >>> nAssign = 2
            >>> massign_equal_weights = False
            >>> massign_alpha = 1.2
            >>> massign_sigma = 80.0
            >>> nAssign = 2
            >>> idx_to_wxs, idx_to_maws = vocab.assign_to_words(idx_to_vec, nAssign)
            >>> print('idx_to_maws = %s' % (ut.repr2(idx_to_wxs, precision=2),))
            >>> print('idx_to_wxs = %s' % (ut.repr2(idx_to_maws, precision=2),))
        """
        if verbose is None:
            verbose = ut.VERBOSE
        if verbose:
            print('[vocab.assign] +--- Start Assign vecs to words.')
            print('[vocab.assign] * nAssign=%r' % nAssign)
            print('[vocab.assign] assign_to_words_. len(idx_to_vec) = %r' % len(idx_to_vec))
        _idx_to_wx, _idx_to_wdist = vocab.nn_index(idx_to_vec, nAssign)
        if nAssign > 1:
            idx_to_wxs, idx_to_maws = weight_multi_assigns(
                _idx_to_wx, _idx_to_wdist, massign_alpha, massign_sigma,
                massign_equal_weights)
        else:
            idx_to_wxs = _idx_to_wx.tolist()
            idx_to_maws = [[1.0]] * len(idx_to_wxs)
        return idx_to_wxs, idx_to_maws

    def invert_assignment(vocab, idx_to_wxs, idx_to_maws, verbose=False):
        """
        Inverts assignment of vectors to words into words to vectors.

        Example:
            >>> idx_to_idx = np.arange(len(idx_to_wxs))
            >>> other_idx_to_prop = (idx_to_idx,)
            >>> wx_to_idxs, wx_to_maws = vocab.invert_assignment(idx_to_wxs, idx_to_maws)
        """
        # Invert mapping -- Group by word indexes
        idx_to_nAssign = [len(wxs) for wxs in idx_to_wxs]
        jagged_idxs = [[idx] * num for idx, num in enumerate(idx_to_nAssign)]
        wx_keys, groupxs = vt.jagged_group(idx_to_wxs)
        idxs_list = vt.apply_jagged_grouping(jagged_idxs, groupxs)
        wx_to_idxs = dict(zip(wx_keys, idxs_list))
        maws_list = vt.apply_jagged_grouping(idx_to_maws, groupxs)
        wx_to_maws = dict(zip(wx_keys, maws_list))
        if verbose:
            print('[vocab] L___ End Assign vecs to words.')
        return (wx_to_idxs, wx_to_maws)

    def render_vocab_word(vocab, inva, wx, fnum=None):
        """
        Creates a visualization of a visual word. This includes the average patch,
        the SIFT-like representation of the centroid, and some of the patches that
        were assigned to it.

        CommandLine:
            python -m ibeis.algo.smk.vocab_indexer render_vocab_word --show

        Example:
            >>> from ibeis.algo.smk.vocab_indexer import *  # NOQA
            >>> ibs, aid_list, inva = testdata_inva('PZ_MTEST', num_words=10000)
            >>> vocab = inva.vocab
            >>> sortx = ut.argsort(list(inva.wx_to_num.values()))[::-1]
            >>> wx_list = ut.take(list(inva.wx_to_num.keys()), sortx)
            >>> wx = wx_list[0]
            >>> ut.quit_if_noshow()
            >>> import plottool as pt
            >>> ut.qt4ensure()
            >>> fnum = 2
            >>> fnum = pt.ensure_fnum(fnum)
            >>> # Interactive visualization of many words
            >>> for wx in ut.InteractiveIter(wx_list):
            >>>     word_img = vocab.render_vocab_word(inva, wx, fnum)
            >>>     pt.imshow(word_img, fnum=fnum, title='Word %r/%r' % (wx, len(inva.vocab)))
            >>>     pt.update()
            >>> ut.show_if_requested()
        """
        import plottool as pt
        # Create the contributing patch image
        word_patches = inva.get_patches(wx)
        stacked_patches = vt.stack_square_images(word_patches)

        # Create the average word image
        word = inva.vocab.wx_to_word[wx]
        average_patch = np.mean(word_patches, axis=0)
        #vecs = inva.get_vecs(wx)
        #assert np.allclose(word, vecs.mean(axis=0))
        with_sift = True
        if with_sift:
            patch_img = pt.render_sift_on_patch(average_patch, word)
        else:
            patch_img = average_patch

        # Stack them together
        solidbar = np.zeros((patch_img.shape[0],
                             int(patch_img.shape[1] * .1), 3), dtype=patch_img.dtype)
        border_color = (100, 10, 10)  # bgr, darkblue
        if ut.is_float(solidbar):
            solidbar[:, :, :] = (np.array(border_color) / 255)[None, None]
        else:
            solidbar[:, :, :] = np.array(border_color)[None, None]
        patch_img2 = vt.inverted_sift_patch(word)
        patch_img = vt.rectify_to_uint8(patch_img)
        patch_img2 = vt.rectify_to_uint8(patch_img2)
        solidbar = vt.rectify_to_uint8(solidbar)
        stacked_patches = vt.rectify_to_uint8(stacked_patches)
        patch_img2, patch_img = vt.make_channels_comparable(patch_img2, patch_img)
        img_list = [patch_img, solidbar, patch_img2, solidbar, stacked_patches]
        word_img = vt.stack_image_list(img_list, vert=False, modifysize=True)
        return word_img

    def render_vocab(vocab):
        """
        Renders the average patch of each word.
        This is a quick visualization of the entire vocabulary.

        CommandLine:
            python -m ibeis.algo.smk.vocab_indexer render_vocab --show

        Example:
            >>> from ibeis.algo.smk.vocab_indexer import *  # NOQA
            >>> vocab = testdata_vocab('PZ_MTEST', num_words=10000)
            >>> all_words = vocab.render_vocab()
            >>> ut.quit_if_noshow()
            >>> import plottool as pt
            >>> pt.qt4ensure()
            >>> pt.imshow(all_words)
            >>> ut.show_if_requested()
        """
        import plottool as pt
        wx_list = list(range(len(vocab)))
        wx_list = ut.strided_sample(wx_list, 64)

        word_patch_list = []
        for wx in ut.ProgIter(wx_list, bs=True, lbl='building patches'):
            word = vocab.wx_to_word[wx]
            word_patch = vt.inverted_sift_patch(word, 64)
            word_patch = pt.render_sift_on_patch(word_patch, word)
            word_patch_list.append(word_patch)

        all_words = vt.stack_square_images(word_patch_list)
        return all_words


def cast_residual_integer(rvecs):
    # same trunctation hack as in SIFT. values will typically not reach the
    # maximum, so we can multiply by a higher number for better fidelity.
    return np.clip(np.round(rvecs * 255.0), -127, 127).astype(np.int8)
    #return np.clip(np.round(rvecs * 255.0), -127, 127).astype(np.int8)


def uncast_residual_integer(rvecs):
    return rvecs.astype(np.float) / 255.0


def compute_rvec(vecs, word):
    """
    Compute residual vectors phi(x_c)

    Subtract each vector from its quantized word to get the resiudal, then
    normalize residuals to unit length.
    """
    rvecs = np.subtract(word.astype(np.float), vecs.astype(np.float))
    # If a vec is a word then the residual is 0 and it cant be L2 noramlized.
    is_zero = np.all(rvecs == 0, axis=1)
    vt.normalize_rows(rvecs, out=rvecs)
    # reset these values back to zero
    if np.any(is_zero):
        rvecs[is_zero, :] = 0
    # Determine if any errors occurred
    # FIXME: zero will drive the score of a match to 0 even though if they
    # are both 0, then it is an exact match and should be scored as a 1.
    error_flags = is_zero
    return rvecs, error_flags


def aggregate_rvecs(rvecs, maws, error_flags):
    r"""
    Compute aggregated residual vectors Phi(X_c)
    """
    # Propogate errors from previous step
    flags_agg = np.any(error_flags, axis=0, keepdims=True)
    if rvecs.shape[0] == 0:
        rvecs_agg = np.empty((0, rvecs.shape[1]), dtype=np.float)
    if rvecs.shape[0] == 1:
        rvecs_agg = rvecs
    else:
        # Prealloc sum output (do not assign the result of sum)
        rvecs_agg = np.empty((1, rvecs.shape[1]), dtype=np.float)
        out = rvecs_agg[0]
        # Take weighted average of multi-assigned vectors
        weighted_sum = (maws[:, None] * rvecs).sum(axis=0, out=out)
        total_weight = maws.sum()
        is_zero = np.all(rvecs_agg == 0, axis=1)
        rvecs_agg = np.divide(weighted_sum, total_weight, out=rvecs_agg)
        vt.normalize_rows(rvecs_agg, out=rvecs_agg)
        if np.any(is_zero):
            # Add in errors from this step
            rvecs_agg[is_zero, :] = 0
            flags_agg[is_zero] = True
    return rvecs_agg, flags_agg


def weight_multi_assigns(_idx_to_wx, _idx_to_wdist, massign_alpha=1.2,
                         massign_sigma=80.0, massign_equal_weights=False):
    r"""
    Multi Assignment Weight Filtering from Improving Bag of Features

    Args:
        massign_equal_weights (): Turns off soft weighting. Gives all assigned
            vectors weight 1

    Returns:
        tuple : (idx_to_wxs, idx_to_maws)

    References:
        (Improving Bag of Features)
        http://lear.inrialpes.fr/pubs/2010/JDS10a/jegou_improvingbof_preprint.pdf
        (Lost in Quantization)
        http://www.robots.ox.ac.uk/~vgg/publications/papers/philbin08.ps.gz
        (A Context Dissimilarity Measure for Accurate and Efficient Image Search)
        https://lear.inrialpes.fr/pubs/2007/JHS07/jegou_cdm.pdf

    Example:
        >>> massign_alpha = 1.2
        >>> massign_sigma = 80.0
        >>> massign_equal_weights = False

    Math:
        exp(-dist / (2 * sigma ** 2))

    Notes:
        sigma values from \cite{philbin_lost08}
        (70 ** 2) ~= 5000, (80 ** 2) ~= 6250, (86 ** 2) ~= 7500,
    """
    #if not ut.QUIET:
    #    print('[vocab] compute_multiassign_weights_')
    if _idx_to_wx.shape[1] <= 1:
        idx_to_wxs = _idx_to_wx.tolist()
        idx_to_maws = [[1.0]] * len(idx_to_wxs)
    else:
        # Valid word assignments are beyond fraction of distance to the nearest word
        massign_thresh = _idx_to_wdist.T[0:1].T.copy()
        # HACK: If the nearest word has distance 0 then this threshold is too hard
        # so we should use the distance to the second nearest word.
        EXACT_MATCH_HACK = True
        if EXACT_MATCH_HACK:
            flag_too_close = (massign_thresh == 0)
            massign_thresh[flag_too_close] = _idx_to_wdist.T[1:2].T[flag_too_close]
        # Compute the threshold fraction
        eps = .001
        np.add(eps, massign_thresh, out=massign_thresh)
        np.multiply(massign_alpha, massign_thresh, out=massign_thresh)
        # Mark assignments as invalid if they are too far away from the nearest
        # assignment
        invalid = np.greater_equal(_idx_to_wdist, massign_thresh)
        if ut.VERBOSE:
            nInvalid = (invalid.size - invalid.sum(), invalid.size)
            print('[maw] + massign_alpha = %r' % (massign_alpha,))
            print('[maw] + massign_sigma = %r' % (massign_sigma,))
            print('[maw] + massign_equal_weights = %r' % (massign_equal_weights,))
            print('[maw] * Marked %d/%d assignments as invalid' % nInvalid)

        if massign_equal_weights:
            # Performance hack from jegou paper: just give everyone equal weight
            masked_wxs = np.ma.masked_array(_idx_to_wx, mask=invalid)
            idx_to_wxs  = list(map(ut.filter_Nones, masked_wxs.tolist()))
            idx_to_maws = [np.ones(len(wxs), dtype=np.float)
                           for wxs in idx_to_wxs]
        else:
            # More natural weighting scheme
            # Weighting as in Lost in Quantization
            gauss_numer = np.negative(_idx_to_wdist.astype(np.float64))
            gauss_denom = 2 * (massign_sigma ** 2)
            gauss_exp   = np.divide(gauss_numer, gauss_denom)
            unnorm_maw = np.exp(gauss_exp)
            # Mask invalid multiassignment weights
            masked_unorm_maw = np.ma.masked_array(unnorm_maw, mask=invalid)
            # Normalize multiassignment weights from 0 to 1
            masked_norm = masked_unorm_maw.sum(axis=1)[:, np.newaxis]
            masked_maw = np.divide(masked_unorm_maw, masked_norm)
            masked_wxs = np.ma.masked_array(_idx_to_wx, mask=invalid)
            # Remove masked weights and word indexes
            idx_to_wxs  = list(map(ut.filter_Nones, masked_wxs.tolist()))
            idx_to_maws = list(map(ut.filter_Nones, masked_maw.tolist()))
            #with ut.EmbedOnException():
    return idx_to_wxs, idx_to_maws


@derived_attribute(
    tablename='vocab', parents=['feat*'],
    colnames=['words'], coltypes=[VisualVocab],
    configclass=VocabConfig, chunksize=1, fname='visual_vocab',
    taggable=True, vectorized=False,
)
def compute_vocab(depc, fid_list, config):
    r"""
    Depcache method for computing a new visual vocab

    CommandLine:
        python -m ibeis.core_annots --exec-compute_neighbor_index --show
        python -m ibeis show_depc_annot_table_input --show --tablename=neighbor_index

        python -m ibeis.algo.smk.vocab_indexer --exec-compute_vocab:0
        python -m ibeis.algo.smk.vocab_indexer --exec-compute_vocab:1

        # FIXME make util_tests register
        python -m ibeis.algo.smk.vocab_indexer compute_vocab:0

    Ignore:
        # Lev Example
        import ibeis
        ibs = ibeis.opendb('Oxford')
        depc = ibs.depc
        table = depc['vocab']
        table.print_table()
        table.print_internal_info()

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.smk.vocab_indexer import *  # NOQA
        >>> # Test depcache access
        >>> import ibeis
        >>> ibs, aid_list = ibeis.testdata_aids('testdb1')
        >>> depc = ibs.depc_annot
        >>> input_tuple = [aid_list]
        >>> rowid_kw = {}
        >>> tablename = 'vocab'
        >>> vocabid_list = depc.get_rowids(tablename, input_tuple, **rowid_kw)
        >>> vocab = depc.get(tablename, input_tuple, 'words')[0]
        >>> assert vocab.wordflann is not None
        >>> assert vocab.wordflann._FLANN__curindex_data is not None
        >>> assert vocab.wordflann._FLANN__curindex_data is vocab.wx_to_word

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.smk.vocab_indexer import *  # NOQA
        >>> import ibeis
        >>> ibs, aid_list = ibeis.testdata_aids('testdb1')
        >>> depc = ibs.depc_annot
        >>> fid_list = depc.get_rowids('feat', aid_list)
        >>> config = VocabConfig()
        >>> vocab, train_vecs = ut.exec_func_src(compute_vocab, keys=['vocab', 'train_vecs'])
        >>> idx_to_vec = depc.d.get_feat_vecs(aid_list)[0]
        >>> self = vocab
        >>> ut.quit_if_noshow()
        >>> data = train_vecs
        >>> centroids = vocab.wx_to_word
        >>> import plottool as pt
        >>> vt.plot_centroids(data, centroids, num_pca_dims=2)
        >>> ut.show_if_requested()
        >>> #config = ibs.depc_annot['vocab'].configclass()

    """
    print('[IBEIS] COMPUTE_VOCAB:')
    vecs_list = depc.get_native('feat', fid_list, 'vecs')
    train_vecs = np.vstack(vecs_list)
    num_words = config['num_words']
    max_iters = 100
    print('[smk_index] Train Vocab(nWords=%d) using %d annots and %d descriptors' %
          (num_words, len(fid_list), len(train_vecs)))
    flann_params = vt.get_flann_params(random_seed=42)
    kwds = dict(
        max_iters=max_iters,
        flann_params=flann_params
    )

    if config['algorithm'] == 'kdtree':
        words = vt.akmeans(train_vecs, num_words, **kwds)
    elif config['algorithm'] == 'minibatch':
        print('Using minibatch kmeans')
        import sklearn.cluster
        rng = np.random.RandomState(config['random_seed'])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clusterer = sklearn.cluster.MiniBatchKMeans(
                num_words, random_state=rng, verbose=5)
            clusterer.fit(train_vecs)
        words = clusterer.cluster_centers_
    if False:
        flann_params['checks'] = 64
        flann_params['trees'] = 4
        num_words = 128
        centroids = vt.initialize_centroids(num_words, train_vecs, 'akmeans++')
        words, hist = vt.akmeans_iterations(
            train_vecs, centroids, max_iters=1000, monitor=True,
            flann_params=flann_params)

    vocab = VisualVocab(words)
    vocab.build()
    return (vocab,)


@derived_attribute(
    tablename='inverted_agg_assign', parents=['feat', 'vocab'],
    colnames=['wx_list', 'fxs_list', 'maws_list',
              #'rvecs_list', 'flags_list',
              'agg_rvecs', 'agg_flags'],
    coltypes=[list, list, list,
              #list, list,
              np.ndarray, np.ndarray],
    configclass=InvertedIndexConfig,
    fname='smk/smk_agg_rvecs',
    chunksize=256,
)
def compute_residual_assignments(depc, fid_list, vocab_id_list, config):
    r"""
    CommandLine:
        python -m ibeis.control.IBEISControl show_depc_annot_table_input \
                --show --tablename=residuals

    Ignore:
        ibs.depc['vocab'].print_table()

    Ignore:
        data = ibs.depc.get('inverted_agg_assign', ([1, 2473], qreq_.daids), config=qreq_.config)
        wxs1 = data[0][0]
        wxs2 = data[1][0]

        # Lev Example
        import ibeis
        ibs = ibeis.opendb('Oxford')
        depc = ibs.depc
        table = depc['inverted_agg_assign']
        table.print_table()
        table.print_internal_info()

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.smk.vocab_indexer import *  # NOQA
        >>> # Test depcache access
        >>> import ibeis
        >>> ibs, aid_list = ibeis.testdata_aids('testdb1')
        >>> depc = ibs.depc_annot
        >>> config = {'num_words': 1000, 'nAssign': 1}
        >>> #input_tuple = (aid_list, [aid_list] * len(aid_list))
        >>> daids = aid_list
        >>> input_tuple = (daids, [daids])
        >>> rowid_kw = {}
        >>> tablename = 'inverted_agg_assign'
        >>> target_tablename = tablename
        >>> input_ids = depc.get_parent_rowids(tablename, input_tuple, config)
        >>> fid_list = ut.take_column(input_ids, 0)
        >>> vocab_id_list = ut.take_column(input_ids, 1)
        >>> data = depc.get(tablename, input_tuple, config)
        >>> tup = dat[1]

    Example:
        >>> from ibeis.algo.smk.vocab_indexer import *  # NOQA
        >>> import ibeis
        >>> qreq_ = ibeis.testdata_qreq_(defaultdb='Oxford', a='oxford')
        >>> config = {'num_words': 64000, 'nAssign': 1, 'int_rvec': True}
        >>> depc = qreq_.ibs.depc
        >>> daids = qreq_.daids
        >>> input_tuple = (daids, [daids])
        >>> rowid_kw = {}
        >>> tablename = 'inverted_agg_assign'
        >>> target_tablename = tablename
        >>> input_ids = depc.get_parent_rowids(tablename, input_tuple, config)
        >>> fid_list = ut.take_column(input_ids, 0)
        >>> vocab_id_list = ut.take_column(input_ids, 1)
    """
    #print('[IBEIS] ASSIGN RESIDUALS:')
    assert ut.allsame(vocab_id_list)
    vocabid = vocab_id_list[0]

    # NEED HACK TO NOT LOAD INDEXER EVERY TIME
    this_table = depc['inverted_agg_assign']
    vocab_table = depc['vocab']
    if this_table._hack_chunk_cache is not None and vocabid in this_table._hack_chunk_cache:
        vocab = this_table._hack_chunk_cache[vocabid]
    else:
        vocab = vocab_table.get_row_data([vocabid], 'words')[0]
        if this_table._hack_chunk_cache is not None:
            this_table._hack_chunk_cache[vocabid] = vocab

    print('Grab Vecs')
    vecs_list = depc.get_native('feat', fid_list, 'vecs')
    nAssign = config['nAssign']
    int_rvec = config['int_rvec']

    from concurrent import futures
    print('Building residual args')
    worker = parprep_agg_phi_worker
    args_gen = parprep_agg_phi_args(vocab, vecs_list, nAssign, int_rvec)
    args_gen = [args for args in ut.ProgIter(args_gen, nTotal=len(vecs_list), lbl='building args')]
    nprocs = ut.num_unused_cpus(thresh=10) - 1
    print('Creatinmg process pools')
    executor = futures.ProcessPoolExecutor(nprocs)
    try:
        fs_chunk = [executor.submit(worker, args) for args in args_gen]
        for fs in fs_chunk:
            yield fs.result()
    except Exception:
        raise
    finally:
        executor.shutdown(wait=True)


def parprep_agg_phi_args(vocab, vecs_list, nAssign, int_rvec):
    for fx_to_vecs in vecs_list:
        fx_to_wxs, fx_to_maws = vocab.assign_to_words(fx_to_vecs, nAssign)
        wx_to_fxs, wx_to_maws = vocab.invert_assignment(fx_to_wxs, fx_to_maws)
        wx_list = sorted(wx_to_fxs.keys())

        word_list = ut.take(vocab.wx_to_word, wx_list)
        fxs_list = ut.take(wx_to_fxs, wx_list)
        maws_list = ut.take(wx_to_maws, wx_list)
        argtup = wx_list, word_list, fxs_list, maws_list, fx_to_vecs, int_rvec
        yield argtup


def parprep_agg_phi_worker(argtup):
    wx_list, word_list, fxs_list, maws_list, fx_to_vecs, int_rvec = argtup
    if int_rvec:
        agg_rvecs = np.empty((len(wx_list), fx_to_vecs.shape[1]), dtype=np.int8)
    else:
        agg_rvecs = np.empty((len(wx_list), fx_to_vecs.shape[1]), dtype=np.float)
    agg_flags = np.empty((len(wx_list), 1), dtype=np.bool)

    #for idx, wx in enumerate(wx_list):
    for idx in range(len(wx_list)):
        word = word_list[idx]
        fxs = fxs_list[idx]
        maws = maws_list[idx]
        vecs = fx_to_vecs.take(fxs, axis=0)

        _rvecs, _flags = compute_rvec(vecs, word)
        _agg_rvecs, _agg_flags = aggregate_rvecs(_rvecs, maws, _flags)
        # Cast to integers for storage
        if int_rvec:
            _agg_rvecs = cast_residual_integer(_agg_rvecs)
        agg_rvecs[idx] = _agg_rvecs[0]
        agg_flags[idx] = _agg_flags[0]

    tup = (wx_list, fxs_list, maws_list, agg_rvecs, agg_flags)
    return tup


@ut.reloadable_class
class InvertedAnnots2(object):
    """
    >>> from ibeis.algo.smk.vocab_indexer import *  # NOQA
    >>> import ibeis
    >>> qreq_ = ibeis.testdata_qreq_(defaultdb='Oxford', a='oxford', p='default:proot=smk,nAssign=1,num_words=64000')
    >>> config = qreq_.qparams
    >>> ibs = qreq_.ibs
    >>> depc = qreq_.ibs.depc
    >>> aids = qreq_.daids
    >>> aids = qreq_.qaids
    >>> input_tuple = (aids, [qreq_.daids])
    >>> inva = ut.DynStruct()

    >>> inva = InvertedAnnots2(aids, qreq_)
    """

    def __init__(inva, aids, qreq_):
        print('Loading up inverted assigments')
        tablename = 'inverted_agg_assign'
        depc = qreq_.ibs.depc
        input_tuple = (aids, [qreq_.daids])
        table = depc[tablename]
        tbl_rowids = depc.get_rowids(tablename, input_tuple, config=qreq_.config)
        print('Reading data')
        #if ut.is_developer():
        #    cacher = ut.Cacher(
        #        fname=qreq_.ibs.get_dbname(),
        #        cfgstr=ut.hashstr_arr27(tbl_rowids, 'group'),
        #        cache_dir=ut.truepath('~/Desktop')
        #    )
        #    groups = cacher.tryload()
        #    if groups is None:
        #        print('Developer cache miss')
        #        groups = table.get_row_data(tbl_rowids, colnames)
        #        cacher.save(groups)
        #else:
        if True:
            with ut.Timer('Formating inverted assigments2'):
                inva.aids = aids
                table.default_to_unpack = True
                # 431.61 vs 143.87 MB here
                inva.wx_lists = [np.array(wx_list_, dtype=np.int32)
                                 for wx_list_ in table.get_row_data(tbl_rowids, ('wx_list',), showprog='load wxs')]
                # Is this better to use?
                inva.fxs_lists = [[np.array(fxs, dtype=np.uint16) for fxs in fxs_list]
                                  for fxs_list in table.get_row_data(tbl_rowids, ('fxs_list',), showprog='load fxs')]
                # [ut.lmap(np.array, fx_list) for fx_list in x.fxs_lists]
                inva.maws_lists = [[np.array(m, dtype=np.float32) for m in maws]
                                   for maws in table.get_row_data(tbl_rowids, ('maws_list',), showprog='load maws')]
                inva.agg_rvecs = table.get_row_data(tbl_rowids, ('agg_rvecs',), showprog='load agg_rvecs')
                inva.agg_flags = table.get_row_data(tbl_rowids, ('agg_flags',), showprog='load agg_flags')
                # less memory hogs
                inva.aid_to_idx = ut.make_index_lookup(inva.aids)
                inva.int_rvec = qreq_.qparams.int_rvec
                inva.gamma_list = None
                # Inverted list
                inva.wx_to_idf = None
                inva.wx_to_aids = None
        else:
            with ut.Timer('Formating inverted assigments1'):
                colnames = ('wx_list', 'fxs_list', 'maws_list', 'agg_rvecs', 'agg_flags')
                groups = table.get_row_data(tbl_rowids, colnames, showprog=True)
                inva.aids = aids
                # 431.61 vs 143.87 MB here
                inva.wx_lists = ut.itake_column(groups, 0)
                inva.wx_lists = [np.array(wx_list, dtype=np.int32) for wx_list in inva.wx_lists]
                # Is this better to use?
                # As nested lists: 471.35 MB
                # As nested ndarrays: 157.12 MB
                inva.fxs_lists = ut.itake_column(groups, 1)
                inva.fxs_lists = [[np.array(fxs, dtype=np.uint16) for fxs in fxs_list] for fxs_list in inva.fxs_lists]
                # [ut.lmap(np.array, fx_list) for fx_list in x.fxs_lists]
                inva.maws_lists = ut.itake_column(groups, 2)
                inva.maws_lists = [[np.array(m, dtype=np.float32)
                                    for m in maws] for maws in inva.maws_lists]
                inva.agg_rvecs = ut.take_column(groups, 3)
                inva.agg_flags = ut.take_column(groups, 4)
                # less memory hogs
                inva.aid_to_idx = ut.make_index_lookup(inva.aids)
                inva.int_rvec = qreq_.qparams.int_rvec
                inva.gamma_list = None
                # Inverted list
                inva.wx_to_idf = None
                inva.wx_to_aids = None

    def _assert_self(inva, qreq_):
        ibs = qreq_.ibs
        assert len(inva.aids) == len(inva.wx_lists)
        assert len(inva.aids) == len(inva.fxs_lists)
        assert len(inva.aids) == len(inva.maws_lists)
        assert len(inva.aids) == len(inva.agg_rvecs)
        assert len(inva.aids) == len(inva.agg_flags)
        nfeat_list1 = ibs.get_annot_num_feats(inva.aids, config2_=qreq_.qparams)
        nfeat_list2 = [sum(ut.lmap(len, fx_list)) for fx_list in inva.fxs_lists]
        nfeat_list3 = [sum(ut.lmap(len, maws)) for maws in inva.maws_lists]
        ut.assert_lists_eq(nfeat_list1, nfeat_list2)
        ut.assert_lists_eq(nfeat_list1, nfeat_list3)

    def __getstate__(inva):
        state = inva.__dict__
        return state

    def __setstate__(inva, state):
        inva.__dict__.update(**state)

    def get_size_info(inva):
        import sys
        def get_homog_list_nbytes_scalar(list_scalar):
            if list_scalar is None:
                return 0
            if len(list_scalar) == 0:
                return 0
            else:
                val = list_scalar[0]
                item_nbytes = ut.get_object_nbytes(val)
                return item_nbytes * len(list_scalar)

        def get_homog_list_nbytes_nested(list_nested):
            if list_nested is None:
                return 0
            if len(list_nested) == 0:
                return 0
            else:
                val = list_nested[0]
                if isinstance(val, np.ndarray):
                    nbytes = sum(sys.getsizeof(v) for v in list_nested)
                    #item_nbytes = sum(v.nbytes for v in list_nested)
                else:
                    nest_nbytes = sys.getsizeof(val) * len(list_nested)
                    totals = sum(ut.lmap(len, list_nested))
                    item_nbytes = sys.getsizeof(val[0]) * totals
                    nbytes = nest_nbytes + item_nbytes
                return nbytes

        def get_homog_dict_nbytes_nested(dict_nested):
            if dict_nested is None:
                return 0
            wxkeybytes = get_homog_list_nbytes_scalar(list(dict_nested.keys()))
            wxvalbytes = get_homog_list_nbytes_nested(list(dict_nested.values()))
            wxbytes = wxkeybytes + wxvalbytes + sys.getsizeof(dict_nested)
            return wxbytes

        def get_homog_dict_nbytes_scalar(dict_scalar):
            if dict_scalar is None:
                return 0
            wxkeybytes = get_homog_list_nbytes_scalar(list(dict_scalar.keys()))
            wxvalbytes = get_homog_list_nbytes_scalar(list(dict_scalar.values()))
            wxbytes = wxkeybytes + wxvalbytes + sys.getsizeof(dict_scalar)
            return wxbytes

        sizes = {
            'aids'       : get_homog_list_nbytes_scalar(inva.aids),
            'wx_lists'   : get_homog_list_nbytes_nested(inva.wx_lists),
            'fxs_lists'  : get_homog_list_nbytes_nested(inva.fxs_lists),
            'maws_lists' : get_homog_list_nbytes_nested(inva.maws_lists),
            'agg_rvecs'  : get_homog_list_nbytes_nested(inva.agg_rvecs),
            'agg_flags'  : get_homog_list_nbytes_nested(inva.agg_flags),
            'aid_to_idx' : get_homog_dict_nbytes_scalar(inva.aid_to_idx),
            'gamma_list' : get_homog_list_nbytes_scalar(inva.gamma_list),
            'wx_to_aids' : get_homog_dict_nbytes_nested(inva.wx_to_aids),
            'wx_to_idf'  : get_homog_dict_nbytes_scalar(inva.wx_to_idf),
        }
        return sizes

    def print_size_info(inva):
        sizes = inva.get_size_info()
        sizes = ut.sort_dict(sizes, value_key=ut.identity)
        total_nbytes =  sum(sizes.values())
        print(ut.align(ut.repr3(ut.map_dict_vals(ut.byte_str2, sizes), strvals=True), ':'))
        print('total_nbytes = %r' % (ut.byte_str2(total_nbytes),))

    def get_nbytes(inva):
        sizes = inva.get_size_info()
        total_nbytes =  sum(sizes.values())
        return total_nbytes

    @profile
    def compute_gammas(inva, wx_to_idf, alpha, thresh):
        from ibeis.algo.smk import smk_pipeline
        _prog = ut.ProgPartial(nTotal=len(inva.wx_lists), bs=True, lbl='gamma', adjust=True)
        _iter = zip(inva.wx_lists, inva.agg_rvecs, inva.agg_flags)
        gamma_list = []
        for wx_list, phiX_list, flagsX_list in _prog(_iter):
            if inva.int_rvec:
                phiX_list = uncast_residual_integer(phiX_list)
            gammaX = smk_pipeline.gamma(wx_list, phiX_list, flagsX_list,
                                        wx_to_idf, alpha, thresh)
            gamma_list.append(gammaX)
        return gamma_list

    @profile
    def compute_idf(inva):
        with ut.Timer('Computing idf'):
            num_docs_total = len(inva.aids)
            # idf denominator (the num of docs containing a word for each word)
            # The max(maws) to denote the probab that this word indexes an annot
            #wx_to_ndocs = ut.DefaultValueDict(0)
            #wx_to_ndocs = ut.ddict(lambda: 0)

            wx_list = sorted(inva.wx_to_aids.keys())
            wx_to_ndocs = {wx: 0.0 for wx in wx_list}

            if True:
                # Unweighted documents
                wx_to_ndocs = {wx: len(set(aids))
                               for wx, aids in inva.wx_to_aids.items()}
            else:
                # Weighted documents
                for wx, maws in zip(ut.iflatten(inva.wx_lists), ut.iflatten(inva.maws_lists)):
                    # Determine how many documents use each word
                    wx_to_ndocs[wx] += min(1.0, sum(maws))

            #wx_list = sorted(wx_to_ndocs.keys())
            ndocs_arr = np.array(ut.take(wx_to_ndocs, wx_list), dtype=np.float)
            # Typically for IDF, 1 is added to the denom to prevent divide by 0
            # We add epsilon to numer and denom to ensure recep is a probability
            out = ndocs_arr
            out = np.add(ndocs_arr, 1, out=out)
            out = np.divide(num_docs_total + 1, ndocs_arr, out=out)
            idf_list = np.log(ndocs_arr, out=out)

            wx_to_idf = dict(zip(wx_list, idf_list))
            wx_to_idf = ut.DefaultValueDict(0, wx_to_idf)
            return wx_to_idf

    @profile
    @ut.memoize
    def get_annot(inva, aid):
        idx = inva.aid_to_idx[aid]
        X = SingleAnnot2(inva, idx)
        return X

    def compute_inverted_list(inva):
        with ut.Timer('Building inverted list'):
            wx_to_aids = ut.ddict(list)
            for aid, wxs in zip(inva.aids, inva.wx_lists):
                for wx in wxs:
                    wx_to_aids[wx].append(aid)
            return wx_to_aids


@ut.reloadable_class
class SingleAnnot2(object):
    def __init__(X, inva, idx):
        X.aid = inva.aids[idx]
        X.wx_list = inva.wx_lists[idx]
        X.fxs_list = inva.fxs_lists[idx]
        X.maws_list = inva.maws_lists[idx]
        X.agg_rvecs = inva.agg_rvecs[idx]
        X.agg_flags = inva.agg_flags[idx]
        X.gamma = inva.gamma_list[idx]
        X.wx_to_idx = ut.make_index_lookup(X.wx_list)
        X.int_rvec = inva.int_rvec

        X.wx_set = set(X.wx_list)

    @property
    def words(X):
        return X.wx_set

    @profile
    def fxs(X, c):
        idx = X.wx_to_idx[c]
        fxs = X.fxs_list[idx]
        return fxs

    @profile
    def maws(X, c):
        idx = X.wx_to_idx[c]
        maws = X.maws_list[idx]
        return maws

    @profile
    def Phi_flags(X, c):
        idx = X.wx_to_idx[c]
        PhiX = X.agg_rvecs[idx]
        if X.int_rvec:
            PhiX = uncast_residual_integer(PhiX)
        flags = X.agg_flags[idx]
        return PhiX, flags


def new_load_vocab(ibs, aids, config):
    # Hack in depcache info to the loaded vocab class
    # (maybe this becomes part of the depcache)
    #rowid = ibs.depc.get_rowids('vocab', [aids], config=config)[0]
    rowid = 1
    table = ibs.depc['vocab']
    vocab = table.get_row_data([rowid], 'words')[0]
    vocab.rowid = rowid
    vocab.config_history = table.get_config_history([vocab.rowid])[0]
    vocab.config = table.get_row_configs([vocab.rowid])[0]
    return vocab


def testdata_vocab(defaultdb='testdb1', **kwargs):
    """
    >>> from ibeis.algo.smk.vocab_indexer import *  # NOQA
    >>> defaultdb='testdb1'
    >>> kwargs = {'num_words': 1000}
    """
    import ibeis
    ibs, aid_list = ibeis.testdata_aids(defaultdb=defaultdb)
    vocab = new_load_vocab(ibs, aid_list, kwargs)
    return vocab
    #fstack = ForwardIndex(ibs, aid_list)
    #inva = InvertedIndex(fstack, vocab, config={'nAssign': 3})
    #fstack.build()
    #inva.build()
    #return ibs, aid_list, inva


def render_vocab(vocab, inva=None, use_data=False):
    """
    Renders the average patch of each word.
    This is a quick visualization of the entire vocabulary.

    CommandLine:
        python -m ibeis.algo.smk.vocab_indexer render_vocab --show
        python -m ibeis.algo.smk.vocab_indexer render_vocab --show --use-data
        python -m ibeis.algo.smk.vocab_indexer render_vocab --show --debug-depc

    Example:
        >>> from ibeis.algo.smk.vocab_indexer import *  # NOQA
        >>> ibs, aid_list, voab = testdata_vocab('PZ_MTEST', num_words=10000)
        >>> use_data = ut.get_argflag('--use-data')
        >>> vocab = inva.vocab
        >>> all_words = vocab.render_vocab(inva, use_data=use_data)
        >>> ut.quit_if_noshow()
        >>> import plottool as pt
        >>> pt.qt4ensure()
        >>> pt.imshow(all_words)
        >>> ut.show_if_requested()
    """
    # Get words with the most assignments
    sortx = ut.argsort(list(inva.wx_to_num.values()))[::-1]
    wx_list = ut.take(list(inva.wx_to_num.keys()), sortx)

    wx_list = ut.strided_sample(wx_list, 64)

    word_patch_list = []
    for wx in ut.ProgIter(wx_list, bs=True, lbl='building patches'):
        word = inva.vocab.wx_to_word[wx]
        if use_data:
            word_patch = inva.get_word_patch(wx)
        else:
            word_patch = vt.inverted_sift_patch(word, 64)
        import plottool as pt
        word_patch = pt.render_sift_on_patch(word_patch, word)
        word_patch_list.append(word_patch)

    #for wx, p in zip(wx_list, word_patch_list):
    #    inva._word_patches[wx] = p
    all_words = vt.stack_square_images(word_patch_list)
    return all_words


def get_patches(inva, wx, verbose=True):
    """
    Loads the patches assigned to a particular word in this stack
    """
    ax_list = inva.wx_to_axs(wx)
    fx_list = inva.wx_to_fxs(wx)
    config = inva.fstack.config
    ibs = inva.fstack.ibs

    # Group annotations with more than one assignment to this word, so we
    # only have to load a chip at most once
    unique_axs, groupxs = vt.group_indices(ax_list)
    fxs_groups = vt.apply_grouping(fx_list, groupxs)

    unique_aids = ut.take(inva.fstack.ax_to_aid, unique_axs)

    all_kpts_list = ibs.depc.d.get_feat_kpts(unique_aids, config=config)
    sub_kpts_list = vt.ziptake(all_kpts_list, fxs_groups, axis=0)

    chip_list = ibs.depc_annot.d.get_chips_img(unique_aids)
    # convert to approprate colorspace
    #if colorspace is not None:
    #    chip_list = vt.convert_image_list_colorspace(chip_list, colorspace)
    # ut.print_object_size(chip_list, 'chip_list')
    patch_size = 64
    _prog = ut.ProgPartial(enabled=verbose, lbl='warping patches', bs=True)
    grouped_patches_list = [
        vt.get_warped_patches(chip, kpts, patch_size=patch_size)[0]
        #vt.get_warped_patches(chip, kpts, patch_size=patch_size, use_cpp=True)[0]
        for chip, kpts in _prog(zip(chip_list, sub_kpts_list),
                                nTotal=len(unique_aids))
    ]
    # Make it correspond with original fx_list and ax_list
    word_patches = vt.invert_apply_grouping(grouped_patches_list, groupxs)
    return word_patches


def get_word_patch(inva, wx):
    if wx not in inva._word_patches:
        assigned_patches = inva.get_patches(wx, verbose=False)
        #print('assigned_patches = %r' % (len(assigned_patches),))
        average_patch = np.mean(assigned_patches, axis=0)
        average_patch = average_patch.astype(np.float)
        inva._word_patches[wx] = average_patch
    return inva._word_patches[wx]


if __name__ == '__main__':
    r"""
    CommandLine:
        export PYTHONPATH=$PYTHONPATH:/home/joncrall/code/ibeis/ibeis/algo/smk
        python ~/code/ibeis/ibeis/algo/smk/vocab_indexer.py
        python ~/code/ibeis/ibeis/algo/smk/vocab_indexer.py --allexamples
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()