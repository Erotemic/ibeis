
# @six.add_metaclass(ut.ReloadingMetaclass)
class ScoreNormalizer(ut.Cachable):
    r"""
    Args:
        normalizer       (?):
        cfgstr           (None):
        score_domain     (None):
        p_tp_given_score (None):
        tp_support       (None):
        tn_support       (None):
        tp_labels        (None):
        tn_labels        (None):
        clip_score        (None):

    CommandLine:
        python -m ibeis.algo.hots.score_normalization --test-ScoreNormalizer

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.hots.score_normalization import *  # NOQA
        >>> cfgstr = None
        >>> score_domain = None
        >>> p_tp_given_score = None
        >>> tp_support = None
        >>> tn_support = None
        >>> tp_labels = None
        >>> tn_labels = None
        >>> normalizer = ScoreNormalizer(cfgstr, score_domain, p_tp_given_score,
        ...                              tp_support, tn_support, tp_labels,
        ...                              tn_labels)
    """
    prefix2 = '_normalizer_'

    def __init__(normalizer, cfgstr=None, score_domain=None,
                 p_tp_given_score=None, tp_support=None, tn_support=None,
                 tp_labels=None, tn_labels=None, clip_score=None,
                 timestamp=None, prefix=''):
        super(ScoreNormalizer, normalizer).__init__()
        normalizer.cfgstr = cfgstr
        normalizer.prefix1 = prefix
        normalizer.score_domain = score_domain
        normalizer.p_tp_given_score = p_tp_given_score
        normalizer.tp_support = tp_support
        normalizer.tn_support = tn_support
        normalizer.tp_labels = tp_labels
        normalizer.tn_labels = tn_labels
        normalizer.timestamp = timestamp
        normalizer.clip_score = clip_score
        #normalizer.set_values(score_domain, p_tp_given_score, tp_support,
        #                      tn_support, tp_labels, tn_labels)

    def get_prefix(normalizer):
        return normalizer.prefix1 + ScoreNormalizer.prefix2

    def get_cfgstr(normalizer):
        assert normalizer.cfgstr is not None
        return normalizer.cfgstr

    #def load(normalizer, *args, **kwargs):
    #    # Inherited method
    #    super(ScoreNormalizer, normalizer).load(*args, **kwargs)

    #def save(normalizer, *args, **kwargs):
    #    # Inherited method
    #    super(ScoreNormalizer, normalizer).save(*args, **kwargs)

    def normalize_score_(normalizer, score):
        """ for internal use only """
        if normalizer.score_domain is None:
            raise AssertionError('user normalize score list')
            return .5
        if score < normalizer.score_domain[0]:
            # clip scores at 0
            prob = 0.0
        elif score > normalizer.score_domain[-1]:
            # interpolate between max probability and one
            prob = (normalizer.p_tp_given_score[-1] + 1.0) / 2.0
        else:
            # use normalizer to get scores
            indexes = np.where(normalizer.score_domain <= score)[0]
            index = indexes[-1]
            prob = normalizer.p_tp_given_score[index]
        #if prob >= 1:
        #    ut.embed()
        return prob

    def __call__(normalizer, score_list):
        return normalizer.normalize_score_list(score_list)

    def normalize_score_list(normalizer, score_list):
        if normalizer.get_num_training_pairs() < 2:
            #prob_list = normalizer.empty_normalize_score_list_46(score_list)
            prob_list = normalizer.empty_normalize_score_list_None(score_list)
        else:
            prob_list = [normalizer.normalize_score_(score) for score in score_list]
        return prob_list

    def empty_normalize_score_list_None(normalizer, score_list):
        return [None] * len(score_list)

    def empty_normalize_score_list_46(normalizer, score_list):
        """
        # HACK
        # return scores from .4 to .6 if we have no idea
        """
        score_arr = np.array(score_list)
        if len(score_arr) < 2 or score_arr.max() == score_arr.min():
            return np.full(score_arr.shape, .5)
        else:
            prob_list = (ut.norm_zero_one(score_arr) * .2) + .4
        return prob_list

    def normalizer_score_list2(normalizer, score_list):
        """
        linear combination of probability and original score based on num
        support cases
        """
        num_train_pairs = normalizer.get_num_training_pairs()
        score_list = np.array(score_list)
        prob_list = normalizer.normalize_score_list(score_list)
        NUM_SUPPORT_THRESH = 200
        alpha = min(1.0, num_train_pairs / float(NUM_SUPPORT_THRESH))
        prob_list2 = (alpha * score_list) + ((1 - alpha) * prob_list)
        return prob_list2

    def get_num_training_pairs(normalizer):
        if normalizer.score_domain is None:
            num_train_pairs = 0
        else:
            num_train_pairs = len(normalizer.tp_support)
        return num_train_pairs

    def get_infostr(normalizer):
        if normalizer.score_domain is None:
            return 'empty normalizer'
        infostr_list = [
            ut.get_stats_str(normalizer.tp_support, lbl='tp_support', exclude_keys=['nMin', 'nMax']),
            ut.get_stats_str(normalizer.tn_support, lbl='tn_support', exclude_keys=['nMin', 'nMax']),
            ut.get_stats_str(normalizer.p_tp_given_score, lbl='p_tp_given_score', exclude_keys=['nMin', 'nMax']),
            ut.get_stats_str(normalizer.score_domain, keys=['max', 'min', 'shape'], lbl='score_domain'),
            'clip_score = %.2f' % normalizer.clip_score,
            'cfgstr = %r' % normalizer.cfgstr,
            'timestamp = %r' % normalizer.timestamp,
        ]
        infostr = '\n'.join(infostr_list)
        return infostr

    def add_support(normalizer, tp_scores, tn_scores, tp_labels, tn_labels):
        """

        CommandLine:
            python -m ibeis.algo.hots.score_normalization --test-add_support --show

        Example:
            >>> # DISABLE_DOCTEST
            >>> from ibeis.algo.hots.score_normalization import *  # NOQA
            >>> # build test data
            >>> normalizer = ScoreNormalizer('testnorm')
            >>> tp_scores = [100, 100, 70, 60, 60, 60, 100]
            >>> tn_scores = [10, 10, 20, 30, 30, 30, 10]
            >>> tp_labels = list(map(ut.deterministic_uuid, [110, 110, 111, 112, 112, 112, 110]))
            >>> tn_labels = list(map(ut.deterministic_uuid, [10, 10, 11, 12, 12, 12, 10]))
            >>> # call test function
            >>> normalizer.add_support(tp_scores, tn_scores, tp_labels, tn_labels)
            >>> # verify results
            >>> normalizer.retrain()
            >>> if ut.show_was_requested():
            >>>      normalizer.visualize()
            >>> # build test data
            >>> tp_scores = np.random.randint(100, size=100)
            >>> tn_scores = np.random.randint(50, size=100)
            >>> tp_labels = list(map(ut.deterministic_uuid, np.arange(1000, 1100)))
            >>> tn_labels = list(map(ut.deterministic_uuid, np.arange(2000, 2100)))
            >>> normalizer.add_support(tp_scores, tn_scores, tp_labels, tn_labels)
            >>> normalizer.retrain()
            >>> if ut.show_was_requested():
            >>>     import plottool as pt
            >>>     normalizer.visualize()
            >>>     pt.show_if_requested()
        """
        # Initialize support if empty
        if normalizer.tp_support is None:
            normalizer.tp_support = np.array([])
            normalizer.tn_support = np.array([])
            normalizer.tp_labels = np.array([])
            normalizer.tn_label = np.array([])

        # Ensure that incoming data is unique w.r.t. data that already exists
        def filter_seen_data(seen_labels, input_labels, input_data):
            """
            seen_labels, input_labels, input_data = normalizer.tp_labels, tp_labels, tp_scores
            """
            unique_labels, unique_indiceis = np.unique(input_labels,  return_index=True)
            unique_data = np.array(input_data).take(unique_indiceis, axis=0)
            isold_flags = np.in1d(unique_labels, seen_labels)
            isnew_flags = np.logical_not(isold_flags, out=isold_flags)
            filtered_labels = unique_labels.compress(isnew_flags)
            filtered_data = unique_data.compress(isnew_flags)
            return filtered_labels, filtered_data
        filtered_tp_labels, filtered_tp_scores = filter_seen_data(normalizer.tp_labels, tp_labels, tp_scores)
        filtered_tn_labels, filtered_tn_scores = filter_seen_data(normalizer.tn_labels, tn_labels, tn_scores)

        # Ensure input in list format
        assert ut.allsame(map(
            len, (tp_scores, tn_scores, tp_labels, tn_labels))), ('unequal lengths')

        if len(filtered_tp_scores) == 0:
            return

        normalizer.tp_support = np.append(normalizer.tp_support, filtered_tp_scores)
        normalizer.tn_support = np.append(normalizer.tn_support, filtered_tn_scores)
        normalizer.tp_labels  = np.append(normalizer.tp_labels, filtered_tp_labels)
        normalizer.tn_label   = np.append(normalizer.tn_labels, filtered_tn_labels)

    def retrain(normalizer):
        tp_support = np.array(normalizer.tp_support)
        tn_support = np.array(normalizer.tn_support)
        learnkw = dict()
        learntup = learn_score_normalization(tp_support, tn_support,
                                             return_all=False, **learnkw)
        (score_domain, p_tp_given_score, clip_score) = learntup
        # DONT Make a new custom cfg
        #cfgstr = ut.hashstr((tp_support, tn_support))
        #normalizer.cfgstr = cfgstr
        normalizer.score_domain = score_domain
        normalizer.p_tp_given_score = p_tp_given_score
        normalizer.clip_score = clip_score

    def visualize(normalizer, update=True, verbose=True, fnum=None):
        """
        CommandLine:
            python -m ibeis.algo.hots.score_normalization --test-visualize --index 0
            --cmd

        Example:
            >>> # DISABLE_DOCTEST
            >>> import plottool as pt
            >>> from ibeis.algo.hots.score_normalization import *  # NOQA
            >>> #import ibeis
            >>> index = ut.get_argval('--index', type_=int, default=0)
            >>> normalizer = load_precomputed_normalizer(index, with_global=False)
            >>> normalizer.visualize()
            >>> six.exec_(pt.present(), globals(), locals())

        """
        import plottool as pt
        if verbose:
            print(normalizer.get_infostr())
        if normalizer.score_domain is None:
            return
        if fnum is None:
            fnum = pt.next_fnum()
        pt.figure(fnum=fnum, pnum=(2, 1, 1), doclf=True, docla=True)
        normalizer.visualize_probs(fnum=fnum, pnum=(2, 1, 1), update=False)
        normalizer.visualize_support(fnum=fnum, pnum=(2, 1, 2), update=False)
        if update:
            pt.update()

    def visualize_support(normalizer, update=True, fnum=None, pnum=(1, 1, 1)):
        plot_support(normalizer.tn_support, normalizer.tp_support, fnum=fnum, pnum=pnum)
        if update:
            import plottool as pt
            pt.update()

    def visualize_probs(normalizer, update=True, fnum=None, pnum=(1, 1, 1)):
        plot_postbayes_pdf(normalizer.score_domain, 1 - normalizer.p_tp_given_score,
                           normalizer.p_tp_given_score,
                           cfgstr=normalizer.get_cfgstr(), fnum=fnum, pnum=pnum)
        if update:
            import plottool as pt
            pt.update()


# DEVELOPER FUNCTIONS


def find_score_maxclip(tp_support, tn_support, clip_factor=ut.PHI + 1):
    """
    returns score to clip true positives past.

    Args:
        tp_support (ndarray):
        tn_support (ndarray):

    Returns:
        float: clip_score

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.score_normalization import *  # NOQA
        >>> tp_support = np.array([100, 200, 50000])
        >>> tn_support = np.array([10, 30, 110])
        >>> clip_score = find_score_maxclip(tp_support, tn_support)
        >>> result = str(clip_score)
        >>> print(result)
        287.983738762
    """
    max_true_positive_score = tp_support.max()
    max_true_negative_score = tn_support.max()
    if clip_factor is None:
        clip_score = max_true_positive_score
    else:
        overshoot_factor = max_true_positive_score / max_true_negative_score
        if overshoot_factor > clip_factor:
            clip_score = max_true_negative_score * clip_factor
        else:
            clip_score = max_true_positive_score
    return clip_score


# DEBUGGING FUNCTIONS


def test_score_normalization():
    """

    CommandLine:
        python ibeis/algo/hots/score_normalization.py --test-test_score_normalization

        python dev.py -t custom --cfg codename:vsone_unnorm --db PZ_MTEST --allgt --vf --va
        python dev.py -t custom --cfg codename:vsone_unnorm --db PZ_MTEST --allgt --vf --va --index 0:8:3 --dindex 0:10 --verbose

    Example:
        >>> # DISABLE_DOCTEST
        >>> #from ibeis.algo.hots import score_normalization
        >>> #score_normalization.rrr()
        >>> from ibeis.algo.hots.score_normalization import *   # NOQA
        >>> locals_ = test_score_normalization()
        >>> execstr = ut.execstr_dict(locals_)
        >>> #print(execstr)
        >>> exec(execstr)
        >>> import plottool as pt
        >>> exec(pt.present())

    """
    import ibeis
    import plottool as pt  # NOQA

    # Load IBEIS database
    dbname = 'PZ_MTEST'
    #dbname = 'GZ_ALL'

    ibs = ibeis.opendb(dbname)
    qaid_list = daid_list = ibs.get_valid_aids()

    # Get unnormalized query results
    #cfgdict = dict(codename='nsum_unnorm')
    cfgdict = dict(codename='vsone_unnorm')
    cm_list = ibs.query_chips(qaid_list, daid_list, cfgdict, return_cm=True)

    # Get a training sample
    datatup = get_ibeis_score_training_data(ibs, cm_list)
    (tp_support, tn_support, tp_support_labels, tn_support_labels) = datatup

    # Print raw score statistics
    ut.print_stats(tp_support, lbl='tp_support')
    ut.print_stats(tn_support, lbl='tn_support')

    normkw_list = ut.util_dict.all_dict_combinations(
        {
            'monotonize': [True],  # [True, False],
            #'adjust': [1, 4, 8],
            'adjust': [4, 8],
            #'adjust': [8],
        }
    )

    if len(normkw_list) > 32:
        raise AssertionError('Too many plots to test!')

    fnum = pt.next_fnum()
    true_color = pt.TRUE_BLUE  # pt.TRUE_GREEN
    false_color = pt.FALSE_RED
    unknown_color = pt.UNKNOWN_PURP
    pt.plots.plot_sorted_scores(
        (tn_support, tp_support),
        ('true negative scores', 'true positive scores'),
        score_colors=(false_color, true_color),
        #logscale=True,
        logscale=False,
        figtitle='sorted nscores',
        fnum=fnum)

    for normkw in normkw_list:
        # Learn the appropriate normalization
        #normkw = {}  # dict(gridsize=1024, adjust=8, clip_factor=ut.PHI + 1, return_all=True)
        (score_domain, p_tp_given_score, p_tn_given_score, p_score_given_tp, p_score_given_tn,
         p_score, clip_score) = learn_score_normalization(tp_support, tn_support, return_all=True, **normkw)

        assert clip_score > tn_support.max()

        inspect_pdfs(tn_support, tp_support, score_domain,
                     p_tp_given_score, p_tn_given_score, p_score_given_tp, p_score_given_tn, p_score)

        pt.set_figtitle('ScoreNorm ' + ibs.get_dbname() + ' ' + ut.dict_str(normkw))
    locals_ = locals()
    return locals_


def inspect_pdfs(tn_support, tp_support, score_domain, p_tp_given_score,
                 p_tn_given_score, p_score_given_tp, p_score_given_tn, p_score,
                 with_scores=False):
    import plottool as pt  # NOQA

    fnum = pt.next_fnum()
    nRows = 2 + with_scores
    pnum_ = pt.get_pnum_func(nRows=nRows, nCols=1)
    #pnum_ = pt.get_pnum_func(nRows=3, nCols=1)
    #def next_pnum():
    #    return pnum_(

    def generate_pnum():
        for px in range(nRows):
            yield pnum_(px)

    _pnumiter = generate_pnum().next

    pt.figure(fnum=fnum, pnum=pnum_(0))

    if with_scores:
        plot_support(tn_support, tp_support, fnum=fnum, pnum=_pnumiter())

    plot_prebayes_pdf(score_domain, p_score_given_tn, p_score_given_tp, p_score,
                      cfgstr='', fnum=fnum, pnum=_pnumiter())

    plot_postbayes_pdf(score_domain, p_tn_given_score, p_tp_given_score,
                       cfgstr='', fnum=fnum, pnum=_pnumiter())


def plot_support(tn_support, tp_support, fnum=None, pnum=(1, 1, 1)):
    r"""
    Args:
        tn_support (ndarray):
        tp_support (ndarray):
        fnum (int):  figure number
        pnum (tuple):  plot number

    CommandLine:
        python -m ibeis.algo.hots.score_normalization --test-plot_support

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.hots.score_normalization import *  # NOQA
        >>> tn_support = '?'
        >>> tp_support = '?'
        >>> fnum = None
        >>> pnum = (1, 1, 1)
        >>> result = plot_support(tn_support, tp_support, fnum, pnum)
        >>> print(result)
    """
    import plottool as pt  # NOQA
    if fnum is None:
        fnum = pt.next_fnum()
    true_color = pt.TRUE_BLUE  # pt.TRUE_GREEN
    false_color = pt.FALSE_RED
    pt.plots.plot_sorted_scores(
        (tn_support, tp_support),
        ('trueneg scores', 'truepos scores'),
        score_colors=(false_color, true_color),
        #logscale=True,
        logscale=False,
        figtitle='sorted nscores',
        fnum=fnum,
        pnum=pnum)


def plot_prebayes_pdf(score_domain, p_score_given_tn, p_score_given_tp, p_score,
                      cfgstr='', fnum=None, pnum=(1, 1, 1)):
    import plottool as pt  # NOQA
    if fnum is None:
        fnum = pt.next_fnum()
    true_color = pt.TRUE_BLUE  # pt.TRUE_GREEN
    false_color = pt.FALSE_RED
    unknown_color = pt.UNKNOWN_PURP

    pt.plots.plot_probabilities(
        (p_score_given_tn,  p_score_given_tp, p_score),
        ('p(score | tn)', 'p(score | tp)', 'p(score)'),
        prob_colors=(false_color, true_color, unknown_color),
        figtitle='pre_bayes pdf score',
        xdata=score_domain,
        fnum=fnum,
        pnum=pnum)


def plot_postbayes_pdf(score_domain, p_tn_given_score, p_tp_given_score,
                       cfgstr='', fnum=None, pnum=(1, 1, 1)):
    import plottool as pt  # NOQA
    if fnum is None:
        fnum = pt.next_fnum()
    true_color = pt.TRUE_BLUE  # pt.TRUE_GREEN
    false_color = pt.FALSE_RED

    pt.plots.plot_probabilities(
        (p_tn_given_score, p_tp_given_score),
        ('p(tn | score)', 'p(tp | score)'),
        prob_colors=(false_color, true_color,),
        figtitle='post_bayes pdf score ' + cfgstr,
        xdata=score_domain, fnum=fnum, pnum=pnum)


def test():
    r"""
    >>> from ibeis.algo.hots.score_normalization import *  # NOQA
    """
    #from ibeis.algo.hots import query_request
    import ibeis
    ibs = ibeis.opendb(db='PZ_MTEST')
    qaid_list = [1, 2, 3, 4, 5]
    daid_list = [1, 2, 3, 4, 5]
    cfgdict = {'codename': 'nsum'}
    cm_list, qreq_ = ibs.query_chips(qaid_list, daid_list, use_cache=False, return_cm=True, cfgdict=cfgdict, return_request=True)
    qreq_.load_score_normalizer(qreq_.ibs)
    normalizer = qreq_.normalizer

    for cm in cm_list:
        aid_list = list(six.iterkeys(cm.aid2_score))
        score_list = list(six.itervalues(cm.aid2_score))
        #normalizer  = normalizer
        prob_list = normalizer.normalize_score_list(score_list)
        cm.qaid2_score = dict(zip(aid_list, prob_list))
    for cm in cm_list:
        print(list(six.itervalues(cm.qaid2_score)))

        #aid2_score = {aid: normalizer.no(score) for aid, score in }
        pass


# DOCTEST MAIN


# NORMALIZER STORAGE AND CACHINE CLASS
USE_NORMALIZER_CACHE = not ut.get_argflag(('--no-normalizer-cache', '--no-normcache'))
# IBEIS FUNCTIONS
MAX_NORMALIZER_CACHE_SIZE = 8
# NORMALIZER_CACHE = ut.get_lru_cache(MAX_NORMALIZER_CACHE_SIZE)
#NORMALIZER_CACHE = {}


def parse_available_normalizers(*args, **kwargs):
    import parse
    normalizers_fpaths = list_available_score_normalizers(*args, **kwargs)
    parsestr = '{cachedir}/{prefix1}' + vt.ScoreNormalizer.prefix2 + '{cfgstr}' + vt.ScoreNormalizer.ext
    result_list = [parse.parse(parsestr, path) for path in normalizers_fpaths]
    cfgstr_list = [result['cfgstr'] for result in result_list]
    prefix1_list = [result['prefix1'] for result in result_list]
    cachedir_list = [result['cachedir'] for result in result_list]
    return cfgstr_list, cachedir_list, prefix1_list


def load_precomputed_normalizer(index, *args, **kwargs):
    """
    python -m ibeis.algo.hots.score_normalization --test-load_precomputed_normalizer

    Example:
        >>> from ibeis.algo.hots.score_normalization import *  # NOQA
        >>> encoder = load_precomputed_normalizer(None)
        >>> encoder.visualize()
        >>> import plottool as pt
    """
    cfgstr_list, cachedir_list, prefix1_list = parse_available_normalizers(*args, **kwargs)
    if index is None or index == 'None':
        print('Avaliable indexes:')
        print(ut.indentjoin(map(str, enumerate(cfgstr_list))))
        index = int(input('what index?'))
    cfgstr = cfgstr_list[index]
    cachedir = cachedir_list[index]
    #prefix1 = prefix1_list[index]
    encoder = vt.ScoreNormalizer(cfgstr=cfgstr)
    encoder.load(cachedir)
    return encoder


def testload_myscorenorm():
    r"""
    CommandLine:
        python -m ibeis.algo.hots.score_normalization --test-testload_myscorenorm

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.hots.score_normalization import *  # NOQA
        >>> testload_myscorenorm()
        >>> import plottool as pt
    """
    encoder = vt.ScoreNormalizer(cfgstr='gzbase')
    encoder.load(utool.truepath('~/Dropbox/IBEIS'))
    encoder.visualize()


def list_available_score_normalizers(with_global=True, with_local=True):
    r"""
    CommandLine:
        python -m ibeis.algo.hots.score_normalization --test-list_available_score_normalizers

    Ignore::
        cp /media/raid/work/_INCTEST_arr((666)7xcu21@fcschv2@m)_GZ_ALL/_ibsdb/_ibeis_cache/scorenorm/zebra_grevys/zebra_grevys_normalizer_bi+i4y&3dl8!xb!+.cPkl
        mkdir ~/Dropbox/IBEIS
        cp '/media/raid/work/_INCTEST_arr((666)7xcu21@fcschv2@m)_GZ_ALL/_ibsdb/_ibeis_cache/scorenorm/zebra_grevys/zebra_grevys_normalizer_bi+i4y&3dl8!xb!+.cPkl' ~/Dropbox/IBEIS/normalizer.cPkl
        mv ~/Dropbox/IBEIS/normalizer.cPkl ~/Dropbox/IBEIS/_normalizer_gzbase.cPkl

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.hots.score_normalization import *  # NOQA
        >>> local_normalizers_fpaths = list_available_score_normalizers(with_global=False)
        >>> global_normalizers_fpaths = list_available_score_normalizers(with_local=False)
        >>> # quote them
        >>> # local_normalizers_fpaths = ['"%s"' % fpath for fpath in local_normalizers_fpaths]
        >>> # global_normalizers_fpaths = ['"%s"' % fpath for fpath in global_normalizers_fpaths]
        >>> print('Available LOCAL normalizers: ' + ut.indentjoin(local_normalizers_fpaths, '\n  '))
        >>> print('Available GLOBAL normalizers: ' + ut.indentjoin(global_normalizers_fpaths, '\n  '))
        >>> print(list(map(ut.get_file_nBytes_str, local_normalizers_fpaths)))
        >>> print(list(map(ut.get_file_nBytes_str, global_normalizers_fpaths)))

    """
    from ibeis.init import sysres
    #from os.path import join
    pattern = '*' + ScoreNormalizer.prefix2 + '*' + ScoreNormalizer.ext
    ibeis_resdir = sysres.get_ibeis_resource_dir()
    workdir = sysres.get_workdir()

    normalizer_fpaths = []
    if with_global:
        global_normalizers = ut.glob(ibeis_resdir, pattern, recursive=True)
        normalizer_fpaths += global_normalizers
    if with_local:
        ibsdbdir_list = sysres.get_ibsdb_list(workdir)
        searchdirs = [join(ibsdbdir, ibs.const.REL_PATHS.cache)
                      for ibsdbdir in ibsdbdir_list]
        local_normalizers_list = [ut.glob(path, pattern, recursive=True) for path in  searchdirs]
        local_normalizers = ut.flatten(local_normalizers_list)
        normalizer_fpaths.extend(local_normalizers)
    # Just search localdb cachedirs (otherwise it will take forever)
    return normalizer_fpaths


def delete_all_learned_normalizers():
    r"""
    DELETES ALL CACHED NORMALIZERS IN ALL DATABASES

    CommandLine:
        python -m ibeis.algo.hots.score_normalization --test-delete_all_learned_normalizers
        #-y

    Example:
        >>> # DOCTEST_DISABLE
        >>> from ibeis.algo.hots import score_normalization
        >>> score_normalization.delete_all_learned_normalizers()
    """
    from ibeis.algo.hots import score_normalization
    import utool as ut
    print('DELETE_ALL_LEARNED_NORMALIZERS')
    normalizer_fpath_list = score_normalization.list_available_score_normalizers()
    print('The following normalizers will be deleted: ' + ut.indentjoin(normalizer_fpath_list, '\n  '))
    if ut.are_you_sure('Deleting all learned normalizers'):
        ut.remove_fpaths(normalizer_fpath_list, verbose=True)


# TRAINING FUNCTIONS


def train_baseline_for_all_dbs():
    r"""
    Runs unnormalized queries to compute normalized queries

    CommandLine:
        python -m ibeis.algo.hots.score_normalization --test-train_baseline_for_all_dbs

    Example:
        >>> from ibeis.algo.hots.score_normalization import *  # NOQA
        >>> train_baseline_for_all_dbs()
    """
    import ibeis
    #from ibeis.algo.hots import score_normalization
    dbname = 'GZ_ALL'
    dbname = 'PZ_MTEST'
    dbname_list = [
        'PZ_MTEST',
        #'GZ_ALL',
    ]
    learnkw = dict()

    for dbname in dbname_list:
        ibs = ibeis.opendb(dbname)
        train_baseline_ibeis_normalizer(ibs, use_cache=False, **learnkw)


def train_baseline_ibeis_normalizer(ibs, use_cache=True, **learnkw):
    r"""
    Runs unnormalized queries to compute normalized queries

    Args:
        ibs (IBEISController):

    Returns:
        ScoreNormalizer: encoder

    CommandLine:
        python -m ibeis.algo.hots.score_normalization --test-train_baseline_ibeis_normalizer --cmd
        python -m ibeis.algo.hots.score_normalization --test-train_baseline_ibeis_normalizer --noshow

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.hots.score_normalization import *  # NOQA
        >>> from ibeis.all_imports import *  # NOQA
        >>> import plottool as pt
        >>> import ibeis
        >>> from ibeis.algo.hots import score_normalization
        >>> #score_normalization.rrr()
        >>> dbname = 'GZ_ALL'
        >>> dbname = 'PZ_MTEST'
        >>> ibs = ibeis.opendb(dbname)
        >>> learnkw = dict()
        >>> encoder = score_normalization.train_baseline_ibeis_normalizer(ibs, use_cache=False, **learnkw)
        >>> encoder.visualize()
        >>> result = str(encoder)
        >>> print(result)
        >>> exec(pt.present())
    """
    from ibeis.algo.hots import query_request
    # TRAIN BASELINE
    tag = '<TRAINING> '
    print(utool.msgblock(tag, 'Begning Training'))
    with utool.Timer(tag):
        #with utool.Indenter('TRAIN >>> '):
        qaid_list = ibs.get_valid_aids()
        daid_list = ibs.get_valid_aids()
        #cfgdict = dict(codename='nsum_unnorm')
        codename = 'vsone_unnorm'
        cfgdict = dict(codename=codename)
        qreq_ = query_request.new_ibeis_query_request(ibs, qaid_list, daid_list, cfgdict)
        use_qcache = True
        cm_list = ibs.query_chips(qaid_list, daid_list, qreq_=qreq_, use_cache=use_qcache, return_cm=True)
        encoder = cached_annotscore_normer(cm_list, qreq_,
                                                   use_cache=use_cache,
                                                   **learnkw)
        # Save as baseline for this species
        species_text = '_'.join(qreq_.get_unique_species())  # HACK
        baseline_cfgstr = 'baseline_' + species_text
        cachedir = ibs.get_global_species_scorenorm_cachedir(species_text)
        encoder.save(cachedir, cfgstr=baseline_cfgstr)
    print('\n' + utool.msgblock(tag, 'Finished Training'))
    return encoder


def try_download_baseline_ibeis_normalizer(ibs, qreq_):
    """
    tries to download a baseline normalizer for some species.
    creates an empty normalizer if it cannot
    """
    baseline_url_dict = {
        # TODO: Populate
    }
    species_text = '_'.join(qreq_.get_unique_species())  # HACK
    query_cfgstr = qreq_.qparams.query_cfgstr
    cachedir = qreq_.ibs.get_global_species_scorenorm_cachedir(species_text)
    key = species_text + query_cfgstr
    baseline_url = baseline_url_dict.get(key, None)
    if baseline_url is not None:
        try:
            cachedir = qreq_.ibs.get_global_species_scorenorm_cachedir(species_text)
            baseline_cachedir = join(cachedir, 'baseline')
            ut.ensuredir(baseline_cachedir)
            encoder = vt.ScoreNormalizer(cfgstr=query_cfgstr, prefix=species_text)
            encoder.load(baseline_cachedir)
        except Exception:
            encoder = None
    else:
        encoder = None
    if encoder is None:
        if False and ut.is_developer(['hyrule']):
            # train new encoder. only do this on hyrule
            print('Baseline does not exist and cannot be downlaoded. Training baseline')
            encoder = train_baseline_ibeis_normalizer(qreq_.ibs)
        else:
            # return empty score encoder
            encoder = vt.ScoreNormalizer(cfgstr=query_cfgstr, prefix=species_text)
            print('returning empty encoder')
            #raise NotImplementedError('return the nodata noramlizer with 1/2 default')
    return encoder


@profile
def request_annoscore_normer(qreq_, verbose=True):
    r"""
    FIXME: do what is in the docstr

    Any loaded normalizer must be configured on the query_cfg of the query
    request. This ensures that all of the support data fed to the normalizer is
    consistent.

    First try to lod the normalizer from the in-memory cache.
    If that fails try to load a custom normalizer from the local directory
    If that fails try to load a custom normalizer from the global directory
    If that fails try to (download and) load the baseline normalizer from the global directory
    If that fails return empty score normalizer.
    As queries are run the normalizer should be udpated and saved under the
    custom normalizer in the local directory.

    Tries to load the best possible normalizer for this query request.
    If none are found then a it tries to load a downloaded baseline. If
    none exists then it starts to compute a custom baseline.

    The basline probability for an empty normalizer should be 1/2.
    The probability of a baseline normalizer should be regularized to
    stay close to 1/2 when there is little support.

    Returns:
        ScoreNormalizer: cached or prebuilt score normalizer

    Example:
        >>> from ibeis.algo.hots.score_normalization import *  # NOQA
        >>> from ibeis.algo.hots import query_request
        >>> import ibeis
        >>> ibs = ibeis.opendb(db='PZ_MTEST')
        >>> qaid_list = [1]
        >>> daid_list = [1, 2, 3, 4, 5]
        >>> cfgdict = dict(codename='vsone_unnorm')
        >>> #cfgdict = dict(codename='vsone_unnorm')
        >>> qreq_ = query_request.new_ibeis_query_request(ibs, qaid_list, daid_list, cfgdict=cfgdict)
        >>> normalizer = request_annoscore_normer(qreq_)
        >>> normalizer.add_support([100], [10], [1], [2])
    """
    # global NORMALIZER_CACHE
    # if not USE_NORMALIZER_CACHE:
    normalizer = try_download_baseline_ibeis_normalizer(qreq_.ibs, qreq_)
    return normalizer


def cached_annotscore_normer(qreq_, use_cache=True, **learnkw):
    r"""
    Builds a normalizer trained on query results for a database

    Returns:
        vtool.ScoreNormalizer: cached or freshly trained score normalizer

    CommandLine:
        python -m ibeis.algo.hots.score_normalization --test-cached_annotscore_normer

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.score_normalization import *   # NOQA
        >>> import ibeis
        >>> qreq_ = ibeis.testdata_qreq_(defaultdb='PZ_MTEST')
        >>> encoder = cached_annotscore_normer(qreq_)
        >>> result = encoder.get_fname()
        >>> result += '\n' + encoder.get_cfgstr()
        >>> print(result)
    """
    # Collect training data
    #cfgstr = ibs.get_dbname() + ibs.get_annot_hashid_semantic_uuid(qaid_list)
    ibs = qreq_.ibs
    species_text = '_'.join(qreq_.get_unique_species())  # HACK
    #data_hashid = qreq_.get_data_hashid()
    #query_hashid = qreq_.get_query_hashid()
    query_cfgstr = qreq_.get_pipe_cfgstr()
    prefix = species_text
    cfgstr = query_cfgstr
    #ibs.get_dbname() + data_hashid + query_hashid + species_text + query_cfgstr
    cachedir = ibs.get_local_species_scorenorm_cachedir(species_text)
    try:
        if use_cache is False:
            raise Exception('forced normalizer cache miss')
        normalizer = vt.ScoreNormalizer()
        normalizer.load(cachedir, cfgstr=cfgstr)
        print('returning cached normalizer')
    except Exception as ex:
        print('cannot load noramlizer so computing on instead')
        ut.printex(ex, iswarning=True)
        #qaid_list = qreq_.qaids
        normalizer = learn_ibeis_score_normalizer(qreq_, cfgstr,
                                                  prefix, **learnkw)
        normalizer.save(cachedir)
    return normalizer


# LEARNING FUNCTIONS
