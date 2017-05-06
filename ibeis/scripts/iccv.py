import numpy as np
import utool as ut
print, rrr, profile = ut.inject2(__name__)


def debug_expanded_aids(ibs, expanded_aids_list, verbose=1):
    import warnings
    warnings.simplefilter('ignore', RuntimeWarning)
    # print('len(expanded_aids_list) = %r' % (len(expanded_aids_list),))
    cfgargs = dict(per_vp=False, per_multiple=False, combo_dists=False,
                   per_name=True, per_enc=True, use_hist=False,
                   combo_enc_info=False)

    for qaids, daids in expanded_aids_list:
        stats = ibs.get_annotconfig_stats(qaids, daids, **cfgargs)
        hashids = (stats['qaid_stats']['qhashid'],
                   stats['daid_stats']['dhashid'])
        print('hashids = %r' % (hashids,))
        if verbose > 1:
            print(ut.repr2(stats, strvals=True, strkeys=True, nl=2))


def encounter_stuff(ibs, aids):
    from ibeis.init import main_helpers
    main_helpers.monkeypatch_encounters(ibs, aids, days=50)
    annots = ibs.annots(aids)

    from ibeis.init.filter_annots import encounter_crossval
    expanded_aids = encounter_crossval(ibs, annots.aids, qenc_per_name=1,
                                       denc_per_name=2)
    import warnings
    warnings.simplefilter('ignore', RuntimeWarning)
    # with warnings.catch_warnings():
    for qaids, daids in expanded_aids:
        stats = ibs.get_annotconfig_stats(qaids, daids, use_hist=False,
                                          combo_enc_info=False)
        hashids = (stats['qaid_stats']['qhashid'],
                   stats['daid_stats']['dhashid'])
        print('hashids = %r' % (hashids,))
        # print(ut.repr2(stats, strvals=True, strkeys=True, nl=2))


# @profile
def end_to_end():
    r"""
    CommandLine:
        python -m ibeis.scripts.iccv end_to_end --show

    Example:
        >>> from ibeis.scripts.iccv import *  # NOQA
        >>> result = end_to_end()
        >>> print(result)
    """
    import ibeis
    from ibeis.init import main_helpers
    # ibs = ibeis.opendb('PZ_MTEST')
    # ibs = ibeis.opendb('PZ_PB_RF_TRAIN')
    ibs = ibeis.opendb('GZ_Master1')
    # Specialized database params
    enc_kw = dict(minutes=30)
    filt_kw = dict(require_timestamp=True, require_gps=True, is_known=True)
    if ibs.dbname == 'PZ_MTEST':
        enc_kw = dict(days=50)
        filt_kw = dict(require_timestamp=True, is_known=True)
    expt_aids = ibs.filter_annots_general(**filt_kw)
    main_helpers.monkeypatch_encounters(ibs, aids=expt_aids, **enc_kw)

    annots = ibs.annots(expt_aids)
    names = list(annots.group_items(annots.nids).values())
    ut.shuffle(names, rng=321)
    train_aids = ut.flatten(names[0::2])
    test_aids = ut.flatten(names[1::2])

    print_cfg = dict(per_multiple=False)
    ibs.print_annot_stats(test_aids, prefix='TRAIN_', **print_cfg)
    ibs.print_annot_stats(test_aids, prefix='TEST_', **print_cfg)
    import utool
    utool.embed()

    train_cfgstr = ibs.get_annot_hashid_visual_uuid(train_aids)

    # -----------
    # TRAINING

    # aids = train_aids
    phi_cacher = ut.Cacher('term_phis', cfgstr=train_cfgstr)
    phis = phi_cacher.tryload()
    if phis is None:
        phis = learn_termination(ibs, aids=train_aids)
        phi_cacher.save(phis)
    # show_phis(phis)

    from ibeis.scripts.script_vsone import OneVsOneProblem
    clf_key = 'RF'
    data_key = 'learn(sum,glob)'
    task_keys = ['match_state', 'photobomb_state']
    pblm = OneVsOneProblem.from_aids(ibs, aids=train_aids, verbose=1)
    pblm.load_features()
    pblm.load_samples()
    pblm.build_feature_subsets()

    # Figure out what the thresholds should be
    thresh_cacher = ut.Cacher('clf_thresh', cfgstr=train_cfgstr)
    fpr_thresholds = thresh_cacher.tryload()
    if fpr_thresholds is None:
        feat_cfgstr = ut.hashstr_arr27(
            pblm.samples.X_dict['learn(all)'].columns.values, 'matchfeat')
        cfg_prefix = (pblm.samples.make_sample_hashid() +
                      pblm.qreq_.get_cfgstr() + feat_cfgstr)
        pblm.learn_evaluation_classifiers(['match_state'], ['RF'], [data_key],
                                          cfg_prefix)
        task_key = 'match_state'
        clf_key = 'RF'
        res = pblm.task_combo_res[task_key][clf_key][data_key]
        fpr_thresholds = {
            fpr: res.get_pos_threshes('fpr', value=fpr)
            for fpr in [0, .01, .1]
        }
        thresh_cacher.save(fpr_thresholds)

    clf_cacher = ut.Cacher('deploy_clf_', cfgstr=train_cfgstr)
    pblm.deploy_task_clfs = clf_cacher.tryload()
    if pblm.deploy_task_clfs is None:
        pblm.learn_deploy_classifiers(task_keys, data_key=data_key,
                                      clf_key=clf_key)
        clf_cacher.save(pblm.deploy_task_clfs)
    # pblm.samples.print_info()
    # task_keys = list(pblm.samples.subtasks.keys())
    # match_clf = pblm.deploy_task_clfs['match_state']
    # pb_clf = pblm.deploy_task_clfs['photobomb_state']

    # Inspect feature importances if you want
    # pblm.report_classifier_importance2(match_clf, data_key=data_key)
    # pblm.report_classifier_importance2(pb_clf, data_key=data_key)

    # ------------
    # TESTING
    import plottool as pt  # NOQA
    # test_aids = ut.flatten(names[1::2])
    # test_aids = ut.flatten(names[1::2][0:4])
    # test_aids = ut.flatten(names[1::2][::2])
    # oracle_accuracy = 1.0
    # oracle_accuracy = .6
    # match_state_thresh = 1.0
    # oracle_accuracy = .9
    oracle_accuracy = 1.0
    complete_thresh = .95
    ranking_loops = 2
    graph_loops = np.inf
    expt_dials = [
        {
            'name': 'Ranking',
            'method': 'ranking',
            'k_redun': np.inf,
            'cand_kw': dict(pblm=None),
            'priority_metric': 'normscore',
            'oracle_accuracy': oracle_accuracy,
            'complete_thresh': 1.0,
            'match_state_thresh': None,
            'max_loops': ranking_loops,
        },
        {
            'name': 'Ranking+Classifier',
            'method': 'ranking',
            'k_redun': np.inf,
            'cand_kw': dict(pblm=pblm),
            'priority_metric': 'priority',
            'oracle_accuracy': oracle_accuracy,
            'complete_thresh': 1.0,
            'match_state_thresh': fpr_thresholds[0],
            'max_loops': ranking_loops,
        },
        {
            'name': 'Graph,K=2,fpr=.01',
            'method': 'graph',
            'k_redun': 2,
            'cand_kw': dict(pblm=pblm),
            'priority_metric': 'priority',
            'oracle_accuracy': oracle_accuracy,
            'complete_thresh': complete_thresh,
            'match_state_thresh': fpr_thresholds[.01],
            'max_loops': graph_loops,
        },
        {
            'name': 'Graph,K=2,fpr=.1',
            'method': 'graph',
            'k_redun': 2,
            'cand_kw': dict(pblm=pblm),
            'priority_metric': 'priority',
            'oracle_accuracy': oracle_accuracy,
            'complete_thresh': complete_thresh,
            'match_state_thresh': fpr_thresholds[.1],
            'max_loops': graph_loops,
        },
    ]

    colors = pt.distinct_colors(len(expt_dials))

    dials = expt_dials[1]
    import pandas as pd

    # verbose = 0
    verbose = 1
    expt_metrics = {}
    for idx in range(3, 4):
        dials = expt_dials[idx]
        infr = ibeis.AnnotInference(ibs=ibs, aids=test_aids, autoinit=True,
                                    verbose=verbose)
        infr.init_test_mode()
        infr.init_termination_criteria(phis)
        run_expt(infr, dials=dials)
        metrics_df = pd.DataFrame.from_dict(infr.metrics_list)
        # infr.non_complete_pcc_pairs().__next__()
        expt_metrics[idx] = (dials, metrics_df)

    pt.qtensure()
    error_denom = len(infr.aids)
    if error_denom == 0:
        error_denom = 1

    # lwb = 3.5

    pt.figure(fnum=1, pnum=(1, 2, 1))
    for count, (dials, metrics_df) in expt_metrics.items():
        pt.plot(metrics_df['n_manual'].values,
                metrics_df['n_merge_remain'].values, '-',
                # lw=lwb - (count),
                color=colors[count],
                label=dials['name'])
    pt.set_xlabel('# manual reviews')
    pt.set_ylabel('# merges remaining')
    pt.legend()

    pt.figure(fnum=1, pnum=(1, 2, 2))
    for count, (dials, metrics_df) in expt_metrics.items():
        pt.plot(metrics_df['n_manual'].values,
                metrics_df['n_errors'].values,
                '-',
                # lw=lwb - count,
                color=colors[count],
                label=dials['name'])

        pt.plot(metrics_df['n_manual'].values,
                metrics_df['n_fn'].values,
                '--',
                # lw=lwb - count,
                color=colors[count],
                label=dials['name'] + 'n_fn')

        pt.plot(metrics_df['n_manual'].values,
                metrics_df['n_fp'].values,
                ':',
                # lw=lwb - count,
                color=colors[count],
                label=dials['name'] + 'n_fp')
        pt.gca().set_ylim(0, error_denom)

    pt.set_ylabel('# of errors')
    pt.set_xlabel('# manual reviews')
    pt.legend()

    # infr.show(fnum=3, groupby='name_label')
    ut.show_if_requested()


@profile
def run_expt(infr, dials):
    import pandas as pd
    import itertools as it

    ut.cprint('RUNING TEST', 'yellow')
    print('dials = %s' % (ut.repr4(dials),))
    k_redun = dials['k_redun']
    oracle_accuracy = dials['oracle_accuracy']
    cand_kw = dials['cand_kw']
    priority_metric = dials['priority_metric']
    infr.method = dials['method']
    infr.PRIORITY_METRIC = priority_metric
    autoreview_enabled = infr.PRIORITY_METRIC == 'priority'
    infr.queue_params['pos_redundancy'] = k_redun
    infr.queue_params['neg_redundancy'] = k_redun
    infr.queue_params['complete_thresh'] = dials['complete_thresh']
    infr.task_thresh = {
        'photobomb_state': pd.Series({
            'pb': .5,
            'notpb': .9,
        }),
        'match_state': pd.Series(dials['match_state_thresh'])
    }

    # aid_to_gt_nid = ut.dzip(infr.aids, infr.orig_name_labels)
    seed = sum(map(ord, dials['name']))

    rng = ut.ensure_rng(seed, impl='python')
    infr.reset(state='empty')
    infr.remove_feedback(apply=True)

    infr.init_refresh_criteria()

    for count in it.count(0):
        if count >= dials['max_loops']:
            # Just do a maximum of some number of runs for now
            ut.cprint('Early stop', 'blue')
            break
        ut.cprint('Outer loop iter %d ' % (count,), 'blue')
        infr.refresh_candidate_edges(**cand_kw)

        if not len(infr.queue):
            ut.cprint('Queue is empty. Terminate.', 'blue')
            break

        ut.cprint('Start inner loop', 'blue')
        while True:
            if len(infr.queue) == 0:
                ut.cprint('No more edges, need refresh', 'blue')
                break
            edge, priority = infr.pop()
            if priority <= 1:
                if infr.refresh.check():
                    ut.cprint('Refresh criteria flags refresh', 'blue')
                    break
            else:
                ut.cprint('IN RECOVERY MODE priority=%r' % (priority,), 'red')

            flag = False
            if autoreview_enabled:
                flag, review = infr.try_auto_review(edge, priority)
            if not flag:
                if infr.method == 'graph':
                    flag, review = infr.try_implicit_review(edge, priority)
                if not flag:
                    error, review = infr.oracle_review(edge, oracle_accuracy,
                                                       rng)
            infr.add_feedback(edge=edge, apply=True, rectify=False, **review)

    if infr.method == 'graph':
        # Enforce that a user checks any PCC that was auto-reviewed
        # but was unable to achieve k-positive-consistency
        for pcc in infr.non_pos_redundant_pccs():
            subgraph = infr.graph.subgraph(pcc)
            for u, v, data in subgraph.edges(data=True):
                edge = infr.e_(u, v)
                if data.get('user_id', '').startswith('auto'):
                    error, review = infr.oracle_review(edge, oracle_accuracy, rng)
                    infr.add_feedback(edge=edge, apply=True, rectify=False,
                                      **review)
        # Check for inconsistency recovery
        while len(infr.queue):
            edge, priority = infr.pop()
            if priority <= 1:
                break
            error, review = infr.oracle_review(edge, oracle_accuracy, rng)
            infr.add_feedback(edge=edge, apply=True, rectify=False, **review)

    if infr.method == 'graph':
        assert len(list(infr.inconsistent_components())) == 0

    true_groups = list(map(set, infr.nid_to_gt_cc.values()))
    pred_groups = list(infr.positive_connected_compoments())
    from ibeis.algo.hots import sim_graph_iden
    comparisons = sim_graph_iden.compare_groups(true_groups, pred_groups)
    pred_merges = comparisons['pred_merges']
    print(pred_merges)
    # print(ut.repr4(comparisons, nl=4))

    # import utool
    # utool.embed()


def show_phis(phis):
    import plottool as pt
    pt.qtensure()
    ranks = 20
    ydatas = [phi.cumsum()[0:ranks] for phi in phis.values()]
    pt.multi_plot(
        xdata=np.arange(1, ranks + 1),
        ydata_list=ydatas,
        num_xticks=ranks,
        label_list=['annots per query: %d' % d for d in phis.keys()],
        title='Learned Termination CDF',
    )


def learn_termination(ibs, aids):
    """
    Example:
    """
    ut.cprint('Learning termination phi', 'white')
    from ibeis.init.filter_annots import encounter_crossval
    from ibeis.expt import test_result
    pipe_cfg = {
        # 'resize_dim': 'area',
        # 'dim_size': 450,
    }

    n_splits = 3
    crossval_splits = []
    avail_confusors = []
    import random
    rng = random.Random(0)
    for n_query_per_name in range(1, 5):
        reshaped_splits, nid_to_confusors = encounter_crossval(
            ibs, aids, qenc_per_name=n_query_per_name, denc_per_name=1,
            rng=rng, n_splits=n_splits, early=True)

        avail_confusors.append(nid_to_confusors)

        expanded_aids = []
        for qpart, dpart in reshaped_splits:
            # For each encounter choose just 1 annotation
            qaids = [rng.choice(enc) for enc in ut.flatten(qpart)]
            daids = [rng.choice(enc) for enc in ut.flatten(dpart)]
            assert len(set(qaids).intersection(daids)) == 0
            expanded_aids.append((sorted(qaids), sorted(daids)))

        crossval_splits.append((n_query_per_name, expanded_aids))

    n_daid_spread = [len(expanded_aids[0][1])
                     for _, expanded_aids in crossval_splits]

    # Check to see if we can pad confusors to make the database size equal
    max_size = max(n_daid_spread)
    afford = (min(map(len, avail_confusors)) - (max(n_daid_spread) -
                                                min(n_daid_spread)))
    max_size += afford

    crossval_splits2 = []
    _iter =  zip(crossval_splits, avail_confusors)
    for (n_query_per_name, expanded_aids), nid_to_confusors in _iter:
        crossval_splits2.append((n_query_per_name, []))
        for qaids, daids in expanded_aids:
            n_extra = max(max_size - len(daids), 0)
            if n_extra <= len(nid_to_confusors):
                extra2 = ut.take_column(nid_to_confusors.values(), 0)[:n_extra]
                extra = ut.flatten(extra2)
            else:
                extra2 = ut.flatten(nid_to_confusors.values())
                rng.shuffle(extra2)
                extra = extra2[:n_extra]
            crossval_splits2[-1][1].append((qaids, sorted(daids + extra)))

    for n_query_per_name, expanded_aids in crossval_splits2:
        debug_expanded_aids(ibs, expanded_aids, verbose=1)

    phis = {}
    for n_query_per_name, expanded_aids in crossval_splits2:
        accumulators = []
        for qaids, daids in expanded_aids:
            num_datab_pccs = len(np.unique(ibs.annots(daids).nids))
            # num_query_pccs = len(np.unique(ibs.annots(qaids).nids))
            qreq_ = ibs.new_query_request(qaids, daids, verbose=False,
                                          cfgdict=pipe_cfg)
            cm_list = qreq_.execute()
            testres = test_result.TestResult.from_cms(cm_list, qreq_)
            freqs, bins = testres.get_rank_histograms(
                key='qnx2_gt_name_rank', bins=np.arange(num_datab_pccs))
            freq = freqs[0]
            accumulators.append(freq)
        size = max(map(len, accumulators))
        accum = np.zeros(size)
        for freq in accumulators:
            accum[0:len(freq)] += freq

        # unsmoothed
        phi1 = accum / accum.sum()
        # kernel = cv2.getGaussianKernel(ksize=3, sigma=.9).T[0]
        # phi2 = np.convolve(phi1, kernel)
        # Smooth out everything after the sv rank to be uniform
        svrank = qreq_.qparams.nNameShortlistSVER
        phi = phi1.copy()
        phi[svrank:] = (phi[svrank:].sum()) / (len(phi) - svrank)
        # phi = accum
        phis[n_query_per_name] = phi
    return phis


def learn_phi():
    # from ibeis.init import main_helpers
    # dbname = 'GZ_Master1'
    # a = 'timectrl'
    # t = 'baseline'
    # ibs, testres = main_helpers.testdata_expts(dbname, a=a, t=t)
    import ibeis
    # from ibeis.init.filter_annots import annot_crossval
    from ibeis.init.filter_annots import encounter_crossval
    from ibeis.init import main_helpers
    from ibeis.expt import test_result
    import plottool as pt
    pt.qtensure()

    ibs = ibeis.opendb('GZ_Master1')
    # ibs = ibeis.opendb('PZ_MTEST')
    # ibs = ibeis.opendb('PZ_PB_RF_TRAIN')

    aids = ibs.filter_annots_general(require_timestamp=True, require_gps=True,
                                     is_known=True)
    # aids = ibs.filter_annots_general(is_known=True, require_timestamp=True)

    # annots = ibs.annots(aids=aids, asarray=True)
    # Take only annots with time and gps data
    # annots = annots.compress(~np.isnan(annots.image_unixtimes_asfloat))
    # annots = annots.compress(~np.isnan(np.array(annots.gps)).any(axis=1))

    main_helpers.monkeypatch_encounters(ibs, aids, minutes=30)

    # pt.draw_time_distribution(annots.image_unixtimes_asfloat, bw=1209600.0)

    pipe_cfg = {
        'resize_dim': 'area',
        'dim_size': 450,
    }
    # qreq_ = ibs.new_query_request(qaids, daids, verbose=False, query_cfg=pipe_cfg)
    # cm_list = qreq_.execute()
    # annots = ibs.annots(aids=aids)
    # nid_to_aids = ut.group_items(annots.aids, annots.nids)

    # TO FIX WE SHOULD GROUP ENCOUNTERS

    n_splits = 3
    # n_splits = 5
    crossval_splits = []
    avail_confusors = []
    import random
    rng = random.Random(0)
    for n_query_per_name in range(1, 5):
        reshaped_splits, nid_to_confusors = encounter_crossval(
            ibs, aids, qenc_per_name=n_query_per_name, denc_per_name=1,
            rng=rng, n_splits=n_splits, early=True)

        avail_confusors.append(nid_to_confusors)

        expanded_aids = []
        for qpart, dpart in reshaped_splits:
            # For each encounter choose just 1 annotation
            qaids = [rng.choice(enc) for enc in ut.flatten(qpart)]
            daids = [rng.choice(enc) for enc in ut.flatten(dpart)]
            assert len(set(qaids).intersection(daids)) == 0
            expanded_aids.append((sorted(qaids), sorted(daids)))

        # expanded_aids = annot_crossval(ibs, annots.aids,
        #                                n_qaids_per_name=n_query_per_name,
        #                                n_daids_per_name=1, n_splits=n_splits,
        #                                rng=rng, debug=False)
        crossval_splits.append((n_query_per_name, expanded_aids))

    n_daid_spread = [len(expanded_aids[0][1]) for _, expanded_aids in crossval_splits]
    # Check to see if we can pad confusors to make the database size equal

    max_size = max(n_daid_spread)

    afford = (min(map(len, avail_confusors)) - (max(n_daid_spread) -
                                                min(n_daid_spread)))
    max_size += afford

    crossval_splits2 = []

    for (n_query_per_name, expanded_aids), nid_to_confusors in zip(crossval_splits, avail_confusors):
        crossval_splits2.append((n_query_per_name, []))
        for qaids, daids in expanded_aids:
            n_extra = max(max_size - len(daids), 0)
            if n_extra <= len(nid_to_confusors):
                extra2 = ut.take_column(nid_to_confusors.values(), 0)[:n_extra]
                extra = ut.flatten(extra2)
            else:
                extra2 = ut.flatten(nid_to_confusors.values())
                rng.shuffle(extra2)
                extra = extra2[:n_extra]
            crossval_splits2[-1][1].append((qaids, sorted(daids + extra)))

    for n_query_per_name, expanded_aids in crossval_splits2:
        debug_expanded_aids(ibs, expanded_aids, verbose=1)

    phis = {}
    for n_query_per_name, expanded_aids in crossval_splits2:
        accumulators = []
        # with warnings.catch_warnings():
        for qaids, daids in expanded_aids:
            num_datab_pccs = len(np.unique(ibs.annots(daids).nids))
            # num_query_pccs = len(np.unique(ibs.annots(qaids).nids))
            qreq_ = ibs.new_query_request(qaids, daids, verbose=False,
                                          cfgdict=pipe_cfg)

            cm_list = qreq_.execute()
            testres = test_result.TestResult.from_cms(cm_list, qreq_)
            # nranks = testres.get_infoprop_list(key='qnx2_gt_name_rank')[0]
            # aranks = testres.get_infoprop_list(key='qx2_gt_annot_rank')[0]
            # freqs, bins = testres.get_rank_histograms(
            #     key='qnx2_gt_name_rank', bins=np.arange(num_datab_pccs))
            freqs, bins = testres.get_rank_histograms(
                key='qnx2_gt_name_rank', bins=np.arange(num_datab_pccs))
            freq = freqs[0]
            accumulators.append(freq)
        size = max(map(len, accumulators))
        accum = np.zeros(size)
        for freq in accumulators:
            accum[0:len(freq)] += freq

        # unsmoothed
        phi1 = accum / accum.sum()
        # kernel = cv2.getGaussianKernel(ksize=3, sigma=.9).T[0]
        # phi2 = np.convolve(phi1, kernel)
        # Smooth out everything after the sv rank to be uniform
        svrank = qreq_.qparams.nNameShortlistSVER
        phi = phi1.copy()
        phi[svrank:] = (phi[svrank:].sum()) / (len(phi) - svrank)
        # phi = accum
        phis[n_query_per_name] = phi

    # ydatas = [phi.cumsum() for phi in phis.values()]
    # label_list = list(map(str, phis.keys()))
    # pt.multi_plot(xdata=np.arange(len(phi)), ydata_list=ydatas, label_list=label_list)
    # pt.figure()
    ranks = 20
    # ydatas = [phi[0:ranks] for phi in phis.values()]
    ydatas = [phi.cumsum()[0:ranks] for phi in phis.values()]
    pt.multi_plot(
        xdata=np.arange(1, ranks + 1),
        ydata_list=ydatas,
        num_xticks=ranks,
        # kind='bar',
        label_list=['annots per query: %d' % d for d in phis.keys()],
        title='Learned Termination CDF',
    )

    #cmc = phi3.cumsum()
    # accum[20:].sum()
    # import cv2
    # accum

    # from sklearn.neighbors.kde import KernelDensity
    # kde = KernelDensity(kernel='gaussian', bandwidth=3)
    # X = ut.flatten([[rank] * (1 + int(freq)) for rank, freq in enumerate(accum)])
    # kde.fit(np.array(X)[:, None])
    # basis = np.linspace(0, len(accum), 1000)
    # density = np.exp(kde.score_samples(basis[:, None]))
    # pt.plot(basis, density)

    # bins, edges = testres.get_rank_percentage_cumhist()
    # import plottool as pt
    # pt.qtensure()
    # pt.multi_plot(edges, [bins[0]])

    # testres.get_infoprop_list('qx2_gt_name_rank')
    # [cm.extend_results(qreq_).get_name_ranks([cm.qnid])[0] for cm in cm_list]

    # if False:
    #     accumulator = np.zeros(num_datab_pccs)
    #     for cm in cm_list:
    #         cm = cm.extend_results(qreq_)
    #         rank = cm.get_name_ranks([cm.qnid])[0]
    #         # rank = min(cm.get_annot_ranks(cm.get_groundtruth_daids()))
    #         accumulator[rank] += 1

if __name__ == '__main__':
    r"""
    CommandLine:
        python -m ibeis.scripts.iccv
        python -m ibeis.scripts.iccv --allexamples
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
