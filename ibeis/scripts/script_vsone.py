# -*- coding: utf-8 -*-
"""
TODO:

* Get end-to-end system test working with simulated reviewer

* Autoselect features:
    * Learn RF
    * prune bottom N features
    * loop until only X features remain
"""
from __future__ import absolute_import, division, print_function, unicode_literals  # NOQA
import utool as ut
import numpy as np
import vtool as vt
import dtool as dt
import copy
from six.moves import zip
import pandas as pd
import sklearn
import sklearn.metrics
import sklearn.model_selection
import sklearn.multiclass
import sklearn.ensemble
from ibeis.scripts import clf_helpers
print, rrr, profile = ut.inject2(__name__)


class PairSampleConfig(dt.Config):
    _param_info_list = [
        ut.ParamInfo('top_gt', 4),
        ut.ParamInfo('mid_gt', 2),
        ut.ParamInfo('bot_gt', 2),
        ut.ParamInfo('rand_gt', 2),
        ut.ParamInfo('top_gf', 3),
        ut.ParamInfo('mid_gf', 2),
        ut.ParamInfo('bot_gf', 1),
        ut.ParamInfo('rand_gf', 2),
    ]


class PairFeatureConfig(dt.Config):
    _param_info_list = [
        ut.ParamInfo('indices', slice(0, 26, 5)),
        ut.ParamInfo('summary_ops', {'sum', 'std', 'mean', 'len', 'med'}),
        ut.ParamInfo('local_keys', None),
        # ut.ParamInfo('local_keys', [...]),
        ut.ParamInfo('sorters', [
            'ratio', 'norm_dist', 'match_dist'
            # 'lnbnn', 'lnbnn_norm_dist',
        ]),

        # ut.ParamInfo('sum', True),
        # ut.ParamInfo('std', True),
        # ut.ParamInfo('mean', True),
        # ut.ParamInfo('len', True),
        # ut.ParamInfo('med', True),
    ]


class VsOneAssignConfig(dt.Config):
    _param_info_list = vt.matching.VSONE_ASSIGN_CONFIG


@ut.reloadable_class
class OneVsOneProblem(clf_helpers.ClfProblem):
    """
    Keeps information about the one-vs-one pairwise classification problem

    CommandLine:
        python -m ibeis.scripts.script_vsone evaluate_classifiers
        python -m ibeis.scripts.script_vsone evaluate_classifiers --db PZ_PB_RF_TRAIN --show
        python -m ibeis.scripts.script_vsone evaluate_classifiers --db PZ_MTEST --show
        python -m ibeis.scripts.script_vsone evaluate_classifiers --db PZ_Master1 --show
        python -m ibeis.scripts.script_vsone evaluate_classifiers --db GZ_Master1 --show

    Example:
        >>> from ibeis.scripts.script_vsone import *  # NOQA
        >>> pblm = OneVsOneProblem()
        >>> pblm.load_features()
        >>> pblm.load_samples()
    """
    appname = 'vsone_rf_train'

    def __init__(pblm):
        import ibeis
        # ut.aug_sysargv('--db PZ_Master1')
        qreq_ = ibeis.testdata_qreq_(
            defaultdb='PZ_PB_RF_TRAIN',
            a=':mingt=3,species=primary',
            # t='default:K=4,Knorm=1,score_method=csum,prescore_method=csum',
            # t='default:K=4,Knorm=1,score_method=csum,prescore_method=csum,QRH=True',
            t='default:K=3,Knorm=1,score_method=csum,prescore_method=csum,QRH=True',
        )
        hyper_params = dt.Config.from_dict(dict(
            subsample=None,
            pair_sample=PairSampleConfig(),
            vsone_assign=VsOneAssignConfig(),
            pairwise_feats=PairFeatureConfig(), ),
            tablename='HyperParams'
        )
        if qreq_.qparams.featweight_enabled:
            hyper_params.vsone_assign['weight'] = 'fgweights'
            hyper_params.pairwise_feats['sorters'] += [
                'weighted_ratio',
                # 'weighted_lnbnn',
            ]
        else:
            hyper_params.vsone_assign['weight'] = None
        assert qreq_.qparams.can_match_samename is True
        assert qreq_.qparams.prescore_method == 'csum'
        pblm.hyper_params = hyper_params
        pblm.qreq_ = qreq_
        pblm.ibs = qreq_.ibs

    def load_features(pblm):
        qreq_ = pblm.qreq_
        dbname = qreq_.ibs.get_dbname()
        vsmany_hashid = qreq_.get_cfgstr(hash_pipe=True, with_input=True)
        hyper_params = pblm.hyper_params
        features_hashid = ut.hashstr27(vsmany_hashid + hyper_params.get_cfgstr())
        cfgstr = '_'.join(['devcache', str(dbname), features_hashid])
        cacher = ut.Cacher('pairwise_data_v11', cfgstr=cfgstr,
                           appname=pblm.appname, enabled=1)
        data = cacher.tryload()
        if not data:
            data = build_features(qreq_, hyper_params)
            cacher.save(data)
        aid_pairs, simple_scores, X_all, match = data
        assert X_all.index.tolist() == aid_pairs, 'index disagrees'
        pblm.raw_aid_pairs = aid_pairs
        pblm.raw_X_dict = {'learn(all)': X_all}
        pblm.raw_simple_scores = simple_scores

    def load_samples(pblm):
        pblm.samples = AnnotPairSamples(
            ibs=pblm.ibs,
            simple_scores=copy.deepcopy(pblm.raw_simple_scores),
            X_dict=copy.deepcopy(pblm.raw_X_dict),
        )

    def evaluate_classifiers(pblm):
        """
        Example:
            >>> from ibeis.scripts.script_vsone import *  # NOQA
            >>> pblm = OneVsOneProblem()
            >>> pblm.evaluate_classifiers()
        """
        pblm.set_pandas_options()

        ut.cprint('\n--- LOADING DATA ---', 'blue')
        pblm.load_features()
        pblm.load_samples()

        # pblm.samples.print_info()
        ut.cprint('\n--- CURATING DATA ---', 'blue')
        pblm.reduce_dataset_size()
        pblm.samples.print_info()
        print('---------------')

        ut.cprint('\n--- FEATURE INFO ---', 'blue')
        pblm.build_feature_subsets()

        if 1:
            for data_key in pblm.samples.X_dict.keys():
                print('\nINFO(samples.X_dict[%s])' % (data_key,))
                print(ut.indent(AnnotPairFeatInfo(pblm.samples.X_dict[data_key]).get_infostr()))

        task_keys = list(pblm.samples.subtasks.keys())
        # task_keys = ut.setdiff(task_keys, ['photobomb_state'])

        data_keys = list(pblm.samples.X_dict.keys())
        # clf_keys = ['RF', 'RF-OVR', 'SVC']
        clf_keys = ['RF']

        # Remove any tasks that cant be done
        for task_key in task_keys[:]:
            labels = pblm.samples.subtasks[task_key]
            if len(labels.make_histogram()) < 2:
                print('No data to train task_key = %r' % (task_key,))
                task_keys.remove(task_key)

        sample_hashid = pblm.samples.make_sample_hashid()
        feat_cfgstr = ut.hashstr_arr27(
            pblm.samples.X_dict['learn(all)'].columns.values, 'matchfeat')

        ut.cprint('\n--- EVALUTE SIMPLE SCORES ---', 'blue')
        pblm.evaluate_simple_scores(task_keys)

        ut.cprint('\n--- LEARN CROSS-VALIDATED RANDOM FORESTS ---', 'blue')
        cfg_prefix = sample_hashid + pblm.qreq_.get_cfgstr() + feat_cfgstr
        pblm.learn_evaluation_classifiers(task_keys, clf_keys, data_keys,
                                          cfg_prefix)

        selected_data_keys = ut.ddict(list)
        ut.cprint('\n--- EVALUATE LEARNED CLASSIFIERS ---', 'blue')
        from utool.experimental.pandas_highlight import to_string_monkey
        # For each task / classifier type
        for task_key in task_keys:
            ut.cprint('--- TASK = %s' % (ut.repr2(task_key),), 'turquoise')
            pblm.report_simple_scores(task_key)
            for clf_key in clf_keys:
                # Combine results over datasets
                print('clf_key = %s' % (ut.repr2(clf_key),))
                data_combo_res = pblm.task_combo_res[task_key][clf_key]
                df_auc_ovr = pd.DataFrame(dict([
                    (datakey, list(data_combo_res[datakey].roc_scores_ovr()))
                    for datakey in data_keys
                ]),
                    index=pblm.samples.subtasks[task_key].one_vs_rest_task_names()
                )
                ut.cprint('[%s] ROC-AUC(OVR) Scores' % (clf_key,), 'yellow')
                print(to_string_monkey(df_auc_ovr, highlight_cols='all'))

                if clf_key.endswith('-OVR') and pblm.samples.subtasks[task_key].n_classes > 2:
                    # Report un-normalized ovr measures if they available
                    ut.cprint('[%s] ROC-AUC(OVR_hat) Scores' % (clf_key,), 'yellow')
                    df_auc_ovr_hat = pd.DataFrame(dict([
                        (datakey, list(data_combo_res[datakey].roc_scores_ovr_hat()))
                        for datakey in data_keys
                    ]),
                        index=pblm.samples.subtasks[task_key].one_vs_rest_task_names()
                    )
                    print(to_string_monkey(df_auc_ovr_hat, highlight_cols='all'))

                roc_scores = dict([(datakey, [data_combo_res[datakey].roc_score()])
                                   for datakey in data_keys])
                df_auc = pd.DataFrame(roc_scores)
                ut.cprint('[%s] ROC-AUC(MacroAve) Scores' % (clf_key,), 'yellow')
                print(to_string_monkey(df_auc, highlight_cols='all'))

                # best_data_key = 'learn(sum,glob,3)'
                best_data_key = df_auc.columns[df_auc.values.argmax(axis=1)[0]]
                selected_data_keys[task_key].append(best_data_key)
                combo_res = data_combo_res[best_data_key]
                ut.cprint('[%s] BEST DataKey = %r' % (clf_key, best_data_key,),
                          'darkgreen')
                with ut.Indenter('[%s] ' % (best_data_key,)):
                    combo_res.extended_clf_report()
                res = combo_res
                if 1:
                    pos_threshes = res.report_thresholds()  # NOQA
                if 0:
                    importance_datakeys = set([
                        # 'learn(all)'
                    ] + [best_data_key])

                    for data_key in importance_datakeys:
                        pblm.report_classifier_importance(task_key, clf_key,
                                                          data_key)

        if 1:
            pblm.end_to_end(task_keys)

        # ut.cprint('\n--- FEATURE INFO ---', 'blue')
        # for best_data_key in selected_data_keys:
        #     print('data_key=(%s)' % (best_data_key,))
        #     print(ut.indent(AnnotPairFeatInfo(
        #           pblm.samples.X_dict[best_data_key]).get_infostr()))

        # TODO: view failure / success cases
        # Need to show and potentially fix misclassified examples
        if False:
            pblm.samples.aid_pairs
            combo_res.target_bin_df
            res = combo_res
            samples = pblm.samples
            meta = res.make_meta(samples).copy()
            import ibeis
            aid_pairs = ut.lzip(meta['aid1'], meta['aid2'])
            attrs = meta.drop(['aid1', 'aid2'], 1).to_dict(orient='list')
            ibs = pblm.qreq_.ibs
            infr = ibeis.AnnotInference.from_pairs(aid_pairs, attrs, ibs=ibs,
                                                   verbose=3)
            infr.reset_feedback('staging')
            infr.reset_labels_to_ibeis()
            infr.apply_feedback_edges()
            infr.relabel_using_reviews()
            # x = [c for c in infr.consistent_compoments()]
            # cc = x[ut.argmax(ut.lmap(len, x))]
            # keep = list(cc.nodes())
            # infr.remove_aids(ut.setdiff(infr.aids, keep))
            infr.start_qt_interface()
            return

    @profile
    def end_to_end(pblm, task_keys):
        r"""
        NOTE:
            the classifiers are always applied to unseen pairs.  However, novel
            pairs may contain previously seen annotations.

        TODO:
            use photobomb and match_state classifier together the way they
            would be used in the end-to-end system.  IE. Don't automatch
            anything that has a high photobomb probability
        """
        # hack to load specific datas (paramatarize me)
        clf_key = 'RF'
        data_key = 'learn(sum,glob)'
        task_keys = ['match_state', 'photobomb_state']
        # Create a new AnnotInference instance to go end-to-end
        import ibeis
        aids = pblm.qreq_.ibs.get_valid_aids()
        infr = ibeis.AnnotInference(ibs=pblm.qreq_.ibs, aids=aids,
                                    autoinit=True)
        # Use one-vs-many to establish candidate edges to classify
        infr.exec_matching()
        infr.apply_match_edges()

        want_edges = list(infr.graph.edges())
        task_probs = pblm.get_independant_evaluation_probs(
            task_keys, clf_key, data_key, infr, want_edges)

        primary_task = 'match_state'
        index = task_probs[primary_task].index
        primary_task_truth = infr.match_state_df(index)

        # with ut.Timer('t3'):
        #     index = task_probs[primary_task].index
        #     want_samples = AnnotPairSamples(
        #         ibs=infr.ibs, index=task_probs[primary_task].index)

        # Get the operating points
        # (FIXME this is influenced by re-using the training set)

        # TODO: pick out all threshold values first (remove thresholds less
        # than .5)

        """
        PROBLEM:
            if we pick a fpr/thresh for match_state=match, then
            what do we do for the other thresholds for that task?

            For photobombs we can just fix that at max of MCC.

            We could use fix the target FPR for each subtask. That
            seems reasonable.

        TODO:
            * Get predictions using user review in addition to the number of
            reviews. Then comparare the ROC curves

                * y_pred_auto @ threshold
                * y_pred_user @ threshold
                * n_user_reveiws @ threshold (approximate this)

            * Find the number of matches that can't be made because the
            candidate edges just don't exist.
        """

        # target_fprs = [1E-4, 1E-2, .1, .3, .49]
        primary_res = pblm.task_combo_res[primary_task][clf_key][data_key]
        labels = primary_res.target_bin_df['match'].values
        probs = primary_res.probs_df['match'].values
        cfms = vt.ConfusionMetrics.from_scores_and_labels(probs, labels)

        # thresh_list0 = np.linspace(0, 1.0, 20)
        thresh_list0 = np.linspace(.51, 1.0, 10)
        # gets the closest fpr (no interpolation)
        fpr_list0 = cfms.get_metric_at_threshold('fpr', thresh_list0)
        # interpolates back to appropriate threshold
        thresh_list = [cfms.get_thresh_at_metric('fpr', fpr)
                       for fpr in fpr_list0]
        fpr_list = cfms.get_metric_at_threshold('fpr', thresh_list)
        assert fpr_list0 == fpr_list, ('should map back correctly')

        thresh_list, unique_idx = np.unique(thresh_list, return_index=True)
        fpr_list = ut.take(fpr_list, unique_idx)

        # primary_threshes = [
        #     primary_res.get_pos_threshes('fpr', target_fpr)['match']
        #     for target_fpr in target_fprs
        # ]
        auto_results_list = []

        task_thresh = {}
        task_key = 'photobomb_state'
        res = pblm.task_combo_res[task_key][clf_key][data_key]
        thresh_df = res.get_pos_threshes('mcc', 'max')
        task_thresh[task_key] = thresh_df

        for target_fpr in fpr_list:
            print('===================================')
            thresh_df = primary_res.get_pos_threshes('fpr', target_fpr)
            task_thresh[primary_task] = thresh_df
            print('target_fpr = %r' % (target_fpr,))
            print('thresh_df = %r' % (thresh_df,))

            # print('Using thresolds %s' % (ut.repr3(task_thresh, precision=4)))
            primary_auto_flags = pblm.auto_decisions_at_threshold(
                primary_task, task_probs, task_thresh, task_keys, clf_key,
                data_key)
            auto_results = pblm.test_auto_decisions(
                infr, primary_task, primary_auto_flags, task_keys, task_probs,
                primary_task_truth)
            auto_results['fpr'] = target_fpr
            auto_results_list.append(auto_results)

        import plottool as pt
        pt.qt4ensure()

        xdata = thresh_list
        xlabel = 'thresh'
        fnum = pt.ensure_fnum(1)
        fig = pt.figure(fnum=fnum, doclf=True)

        ut.fix_embed_globals()
        def make_subplot(label_list, pnum_):
            ydata_list = [ut.take_column(auto_results_list, ylbl) for ylbl in
                          label_list]
            pt.multi_plot(xdata, ydata_list, label_list=label_list, xlabel=xlabel,
                          use_legend=True, fnum=fnum, pnum=pnum_())

        pnum_ = pt.make_pnum_nextgen(nRows=3, nCols=2)
        make_subplot(['n_inconsistent'], pnum_)
        make_subplot(['n_clusters'], pnum_)
        make_subplot(['n_mistakes'], pnum_)
        make_subplot(['n_flagged'], pnum_)
        make_subplot(['fpr'], pnum_)

        fig.canvas.manager.window.raise_()
        ut.show_if_requested()

    @profile
    def test_auto_decisions(pblm, infr, primary_task, primary_auto_flags,
                            task_keys, task_probs, primary_task_truth):
        auto_results = {}
        is_auto = primary_auto_flags.any(axis=1)
        # pblm.extra_report(task_probs, is_auto, want_samples)

        # Apply probabilities to edges in infr
        for task_key in task_keys:
            infr._set_vsone_probs(task_key, task_probs[task_key])
        # Cleanup (maybe not necessary for script)
        infr.remove_feedback()
        infr._del_feedback_edges()
        # Add automatic feedback
        auto_decisions = primary_auto_flags[is_auto].idxmax(axis=1)
        auto_decisions.name = primary_task
        decision_df = pd.DataFrame(auto_decisions.sort_values())
        infr.add_feedback_df(decision_df, user_id='clf(RF-eval)')
        # Apply feedback edges is the bottleneck of the function
        infr.apply_feedback_edges(safe=False)
        n_clusters, n_inconsistent = infr.relabel_using_reviews(
            rectify_names=False)
        auto_results['n_clusters'] = n_clusters
        auto_results['n_inconsistent'] = n_inconsistent

        y_bin_match = primary_task_truth
        auto_truth = y_bin_match.loc[auto_decisions.index].idxmax(axis=1)
        is_mistake = auto_decisions != auto_truth
        auto_results['n_mistakes'] = len(is_mistake)

        queue_params = {
            'pos_diameter': None,
            'neg_diameter': None,
            # 'pos_diameter': 1,
            # 'neg_diameter': 2,
        }
        def oracle_decision(aid1, aid2, primary_task_truth):
            state = primary_task_truth.loc[(aid1, aid2)].idxmax()
            tags = []
            return state, tags
        rng = np.random.RandomState(0)
        _iter = infr.generate_reviews(randomness=0, rng=rng, **queue_params)
        _iter2 = enumerate(_iter)
        prog = ut.ProgIter(_iter2, bs=False, adjust=False)
        for count, (aid1, aid2) in prog:
            print('remaining_reviews = %r' % (infr.remaining_reviews()),)
            # Make the next review decision
            state, tags = oracle_decision(aid1, aid2, primary_task_truth)
            infr.add_feedback(aid1, aid2, state, tags, apply=True)
        auto_results['n_reviews'] = count

        # Assume the user will correct any inconsistent compoments
        import ibeis
        import networkx as nx
        e_ = ibeis.algo.hots.graph_iden.e_
        merge_fixes = []
        split_fixes = []
        for cc in infr.inconsistent_compoments():
            edges = ut.lstarmap(e_, list(cc.edges()))
            edge_states = np.array([
                cc.edge[u][v].get('reviewed_state', 'unreviewed')
                for u, v in edges
            ])
            node_to_nid = nx.get_node_attributes(cc, 'orig_name_label')
            same_flags = (
                np.diff(ut.unflat_take(node_to_nid, edges), axis=1) == 0).T[0]
            split_edges = ut.compress(edges, (edge_states == 'match') &
                                      (~same_flags))
            merge_edges = ut.compress(edges, (edge_states == 'nomatch') &
                                      (same_flags))
            merge_fixes += merge_edges
            split_fixes += split_edges
        # print('----')
        # print('merge_fixes = %r' % (len(merge_fixes),))
        # print('split_fixes = %r' % (len(split_fixes),))
        flagged_edges = merge_fixes + split_fixes

        auto_results['n_flagged'] = len(flagged_edges)

        # fixed_state = y_bin_match.loc[flagged_edges]

        # pd.isnull(auto_decisions.loc[flagged_edges]).sum()
        # mistake_uv = is_mistake[is_mistake].index
        # total_mistakes = is_mistake.sum()
        # print('User is able to discover %d/%d misclassifications' % (
        #     len(flagged_edges), total_mistakes))
        # remaining_mistake_uv = mistake_uv.difference(flagged_edges)
        # print('Initial mistakes')
        # clf_helpers.classification_report2(
        #     y_true=y_bin_match.loc[mistake_uv].idxmax(axis=1),
        #     y_pred=auto_decisions.loc[mistake_uv]
        # )

        # print('Remaining mistakes')
        # clf_helpers.classification_report2(
        #     y_true=y_bin_match.loc[remaining_mistake_uv].idxmax(axis=1),
        #     y_pred=auto_decisions.loc[remaining_mistake_uv]
        # )

        # report number of names with (gt) split problems
        # report number of merge problems (incorrect negative review)
        # report number of remaining merges
        # number of decisions that were part of the training data

        # * accept-threshold -vs- #mistakes
        # * accept-threshold -vs- #discoverable mistakes
        # * accept-threshold -vs- #undiscoverable mistakes
        # * accept-threshold -vs- #user reviews

        # FIX MISTAKES
        # with ut.Timer('apply-auto-feedback'):
        #     fixed_decisions = fixed_state.idxmax(axis=1)
        #     for (u, v), state in fixed_decisions.iteritems():
        #         infr.add_feedback(u, v, state, apply=False)
        # infr.apply_feedback_edges()
        # n_clusters, n_inconsistent = infr.relabel_using_reviews()
        # infr.apply_review_inference()
        # print('n_clusters = %r' % (n_clusters,))
        # print('n_orig_nids = %r' % (len(ut.unique(infr.orig_name_labels))))
        # print('n_aids = %r' % (len(ut.unique(infr.aids))))
        # print('n_inconsistent = %r' % (n_inconsistent,))

        # TODO: simulated user script and report results
        return auto_results

    def extra_report(pblm, task_probs, is_auto, want_samples):
        task_key = 'photobomb_state'
        probs = task_probs[task_key]
        labels = want_samples[task_key]
        y_true = labels.encoded_df.loc[probs.index.tolist()]
        y_pred = probs.idxmax(axis=1).apply(labels.lookup_class_idx)
        target_names = probs.columns
        print('----------------------')
        print('Want Photobomb Report')
        clf_helpers.classification_report2(
            y_true, y_pred, target_names=target_names)

        # Make labels for entire set
        task_key = 'match_state'
        primary_probs = task_probs[task_key]
        primary_labels = want_samples[task_key]
        y_true_enc = primary_labels.encoded_df
        y_true = y_true_enc.loc[primary_probs.index.tolist()]
        y_pred = primary_probs.idxmax(axis=1).apply(
            primary_labels.lookup_class_idx)
        target_names = primary_probs.columns
        print('----------------------')
        print('Want Match Report')
        clf_helpers.classification_report2(
            y_true, y_pred, target_names=target_names)
        print('----------------------')
        print('Autoclassification Report')
        auto_edges = is_auto[is_auto].index
        clf_helpers.classification_report2(
            y_true.loc[auto_edges], y_pred.loc[auto_edges],
            target_names=target_names)
        print('----------------------')

    def auto_decisions_at_threshold(pblm, primary_task, task_probs,
                                    task_thresh, task_keys, clf_key,
                                    data_key):
        # task_thresh = {}
        # for task_key in task_keys:
        #     metric, value = operating_points[task_key]
        #     res = pblm.task_combo_res[task_key][clf_key][data_key]
        #     task_thresh[task_key] = res.get_pos_threshes(metric, value)
        # print('Using thresolds %s' % (ut.repr3(task_thresh, precision=4)))

        # Find edges that pass positive thresh and have max liklihood
        task_pos_flags = {}
        for task_key in task_keys:
            thresh = pd.Series(task_thresh[task_key])
            probs = task_probs[task_key]
            ismax_flags = probs.values.argsort(axis=1) == (probs.shape[1] - 1)
            pos_flags_df = probs > thresh
            pos_flags_df = pos_flags_df & ismax_flags
            if __debug__:
                assert all(f < 2 for f in pos_flags_df.sum(axis=1).unique()), (
                    'unsupported multilabel decision')
            task_pos_flags[task_key] = pos_flags_df

        # Define the primary task and which tasks confound it
        # Restrict auto-decisions based on if the main task is likely to be
        # confounded. (basically restrict based on photobombs)
        task_confounders = {
            'match_state': [('photobomb_state', ['pb'])],
        }
        primary_pos_flags = task_pos_flags[primary_task]

        # Determine classes that are very unlikely or likely to be confounded
        # Either: be safe, don't decide on anything that *is* confounding, OR
        # be even safer, don't decide on anything that *could* be confounding
        task_confounder_flags = pd.DataFrame()
        primary_confounders = task_confounders[primary_task]
        for task_key, confounding_classes in primary_confounders:
            pos_flags = task_pos_flags[task_key]
            nonconfounding_classes = pos_flags.columns.difference(
                confounding_classes)
            likely = pos_flags[confounding_classes].any(axis=1)
            unlikely = pos_flags[nonconfounding_classes].any(axis=1)
            flags = likely if True else likely | ~unlikely
            task_confounder_flags[task_key] = flags

        # A sample is confounded in general if is confounded by any task
        is_confounded = task_confounder_flags.any(axis=1)
        # Automatic decisions are applied to positive and unconfounded samples
        primary_auto_flags = primary_pos_flags.__and__(~is_confounded, axis=0)

        # print('Autodecision info after pos threshold')
        # print('Number positive-decisions\n%s' % primary_pos_flags.sum(axis=0))
        # # print('Percent positive-decisions\n%s' % (
        # #     100 * primary_pos_flags.sum(axis=0) / len(primary_pos_flags)))
        # # print('Total %s, Percent %.2f%%' % (primary_pos_flags.sum(axis=0).sum(),
        # #       100 * primary_pos_flags.sum(axis=0).sum() /
        # #       len(primary_pos_flags)))
        # print('Revoked autodecisions based on confounders:\n%s'  %
        #         primary_pos_flags.__and__(is_confounded, axis=0).sum())
        # print('Making #auto-decisions %s' % ut.map_dict_vals(
        #     sum, primary_auto_flags))
        return primary_auto_flags

    @profile
    def get_independant_evaluation_probs(pblm, task_keys, clf_key, data_key,
                                         infr, want_edges):
        """
        Note: Ideally we should use a completely independant dataset to test.
        However, due to lack of labeled photobombs and notcomparable cases we
        can cheat a little. A subset of want_edges were previously used in
        training, but there is one classifier that never saw it. We use this
        classifier to predict on that case. For completely unseen data we use
        the average probability of all classifiers.

        NOTE: Using the cross-validated training data to select thresholds
        breaks these test independence assumptions. You really should use a
        completely disjoint test set.
        """
        # Choose a classifier for each task
        res_dict = dict([
            (task_key, pblm.task_combo_res[task_key][clf_key][data_key])
            for task_key in task_keys
        ])
        assert ut.allsame([res.probs_df.index for res in res_dict.values()]), (
            'inconsistent combined result indices')

        # Normalize and align combined result sample edges
        res0 = next(iter(res_dict.values()))
        train_uv = np.array(res0.probs_df.index.tolist())
        assert np.all(train_uv.T[0] < train_uv.T[1]), (
            'edges must be in lower triangular form')
        assert len(vt.unique_row_indexes(train_uv)) == len(train_uv), (
            'edges must be unique')
        assert (sorted(ut.lmap(tuple, train_uv.tolist())) ==
                sorted(ut.lmap(tuple, pblm.samples.aid_pairs.tolist())))
        want_uv = np.array(want_edges)

        # Determine which edges need/have probabilities
        want_uv_, train_uv_ = vt.structure_rows(want_uv, train_uv)
        unordered_have_uv_ = np.intersect1d(want_uv_, train_uv_)
        need_uv_ = np.setdiff1d(want_uv_, unordered_have_uv_)
        flags = vt.flag_intersection(train_uv_, unordered_have_uv_)
        # Re-order have_edges to agree with test_idx
        have_uv_ = train_uv_[flags]
        need_uv, have_uv = vt.unstructure_rows(need_uv_, have_uv_)

        # Convert to tuples for pandas lookup. bleh...
        have_edges = ut.lmap(tuple, have_uv.tolist())
        need_edges = ut.lmap(tuple, need_uv.tolist())
        want_edges = ut.lmap(tuple, want_uv.tolist())
        assert set(have_edges) & set(need_edges) == set([])
        assert set(have_edges) | set(need_edges) == set(want_edges)

        # Parse the data_key to build the appropriate feature
        featinfo = AnnotPairFeatInfo(pblm.samples.X_dict[data_key])
        # Find the kwargs to make the desired feature subset
        pairfeat_cfg, global_keys = featinfo.make_pairfeat_cfg()
        need_lnbnn = any('lnbnn' in key for key in pairfeat_cfg['local_keys'])
        # print(featinfo.get_infostr())

        # Construct the matches
        # TODO: ensure the params are ALL the same including qreq_ params
        config = pblm.hyper_params.vsone_assign
        cfgstr = 'temp'
        cacher2 = ut.Cacher('full_eval_probs', cfgstr, appname=pblm.appname,
                            verbose=2)
        data2 = cacher2.tryload()
        if not data2:
            # TODO: cache this
            cfgstr = 'temp'
            cacher = ut.Cacher('full_eval_feats', cfgstr, appname=pblm.appname,
                               verbose=2)
            data = cacher.tryload()
            if not data:
                print('Building need features')
                matches, X_need = infr._make_pairwise_features(
                    need_edges, config=config, pairfeat_cfg=pairfeat_cfg,
                    need_lnbnn=need_lnbnn)
                data = matches, X_need
                cacher.save(data)
            matches, X_need = data
            assert np.all(featinfo.X.columns == X_need.columns), (
                'inconsistent feature dimensions')

            # Make an ensemble of the evaluation classifiers
            # (todo: use a classifier that hasn't seen any of this data)
            task_need_probs = {}
            for task_key in task_keys:
                print('Predicting %s probabilities' % (task_key,))
                clf_list = pblm.task_clfs[task_key][clf_key][data_key]
                labels = pblm.samples.subtasks[task_key]
                eclf = clf_helpers.voting_ensemble(clf_list, voting='soft')
                eclf_probs = clf_helpers.predict_proba_df(eclf, X_need,
                                                          labels.class_names)
                task_need_probs[task_key] = eclf_probs

            # Combine probabilities --- get probabilites for each sample
            # edges = have_edges + need_edges
            task_probs = {}
            for task_key in task_keys:
                eclf_probs = task_need_probs[task_key]
                have_probs = res_dict[task_key].probs_df.loc[have_edges]
                task_probs[task_key] = pd.concat([have_probs, eclf_probs])
                assert have_probs.index.intersection(eclf_probs.index).size == 0
            data2 = task_probs
            cacher2.save(data2)
        task_probs = data2
        return task_probs

    def reduce_dataset_size(pblm):
        """
        Reduce the size of the dataset for development speed

        Example:
            >>> from ibeis.scripts.script_vsone import *  # NOQA
            >>> pblm = OneVsOneProblem()
            >>> pblm.load_features()
            >>> pblm.load_samples()
            >>> pblm.reduce_dataset_size()
        """
        from six import next
        labels = next(iter(pblm.samples.subtasks.values()))
        ut.assert_eq(len(labels), len(pblm.samples), verbose=False)

        if 0:
            # Remove singletons
            unique_aids = np.unique(pblm.samples.aid_pairs)
            nids = pblm.ibs.get_annot_nids(unique_aids)
            singleton_nids = set([nid for nid, v in ut.dict_hist(nids).items() if v == 1])
            nid_flags = [nid in singleton_nids for nid in nids]
            singleton_aids = set(ut.compress(unique_aids, nid_flags))
            mask = [not (a1 in singleton_aids or a2 in singleton_aids)
                     for a1, a2 in pblm.samples.aid_pairs]
            print('Removing %d pairs based on singleton' % (len(mask) - sum(mask)))
            pblm.samples = samples2 = pblm.samples.compress(mask)
            # samples2.print_info()
            # print('---------------')
            labels = next(iter(samples2.subtasks.values()))
            ut.assert_eq(len(labels), len(samples2), verbose=False)
            pblm.samples = samples2

        if 0:
            # Remove anything 1vM didn't get
            mask = (pblm.samples.simple_scores['score_lnbnn_1vM'] > 0).values
            print('Removing %d pairs based on LNBNN failure' % (len(mask) - sum(mask)))
            pblm.samples = samples3 = pblm.samples.compress(mask)
            # samples3.print_info()
            # print('---------------')
            labels = next(iter(samples3.subtasks.values()))
            ut.assert_eq(len(labels), len(samples3), verbose=False)
            pblm.samples = samples3

        from sklearn.utils import random

        if False:
            # Choose labels to balance
            labels = pblm.samples.subtasks['match_state']
            unique_labels, groupxs = ut.group_indices(labels.y_enc)
            #
            # unique_labels, groupxs = ut.group_indices(pblm.samples.encoded_1d())

            # Take approximately the same number of examples from each class type
            n_take = int(np.round(np.median(list(map(len, groupxs)))))
            # rng = np.random.RandomState(0)
            rng = random.check_random_state(0)
            sample_idxs = [
                random.choice(idxs, min(len(idxs), n_take), replace=False,
                              random_state=rng)
                for idxs in groupxs
            ]
            idxs = sorted(ut.flatten(sample_idxs))
            mask = ut.index_to_boolmask(idxs, len(pblm.samples))
            print('Removing %d pairs for class balance' % (len(mask) - sum(mask)))
            pblm.samples = samples4 = pblm.samples.compress(mask)
            # samples4.print_info()
            # print('---------------')
            labels = next(iter(samples4.subtasks.values()))
            ut.assert_eq(len(labels), len(samples4), verbose=False)
            pblm.samples = samples4
            # print('hist(y) = ' + ut.repr4(pblm.samples.make_histogram()))

        # if 0:
        #     print('Random dataset size reduction for development')
        #     rng = np.random.RandomState(1851057325)
        #     num = len(pblm.samples)
        #     to_keep = rng.choice(np.arange(num), 1000)
        #     mask = np.array(ut.index_to_boolmask(to_keep, num))
        #     pblm.samples = pblm.samples.compress(mask)
        #     class_hist = pblm.samples.make_histogram()
        #     print('hist(y) = ' + ut.repr4(class_hist))
        labels = next(iter(pblm.samples.subtasks.values()))
        ut.assert_eq(len(labels), len(pblm.samples), verbose=False)

    def build_feature_subsets(pblm):
        """
        Try to identify a useful subset of features to reduce problem
        dimensionality
        """
        X_dict = pblm.samples.X_dict
        X = X_dict['learn(all)']
        featinfo = AnnotPairFeatInfo(X)
        # print('RAW FEATURE INFO (learn(all)):')
        # print(ut.indent(featinfo.get_infostr()))
        if False:
            # measures_ignore = ['weighted_lnbnn', 'lnbnn', 'weighted_norm_dist',
            #                    'fgweights']
            # Use only local features
            cols = featinfo.select_columns([
                ('measure_type', '==', 'local'),
                # ('local_sorter', 'in', ['weighted_ratio']),
                # ('local_measure', 'not in', measures_ignore),
            ])
            X_dict['learn(local)'] = featinfo.X[sorted(cols)]

        if False:
            # measures_ignore = ['weighted_lnbnn', 'lnbnn', 'weighted_norm_dist',
            #                    'fgweights']
            # Use only local features
            cols = featinfo.select_columns([
                ('measure_type', '==', 'local'),
                ('local_sorter', 'in', ['weighted_ratio']),
                # ('local_measure', 'not in', measures_ignore),
            ])
            X_dict['learn(local,1)'] = featinfo.X[sorted(cols)]

        if False:
            # Use only summary stats
            cols = featinfo.select_columns([
                ('measure_type', '==', 'summary'),
            ])
            X_dict['learn(sum)']  = featinfo.X[sorted(cols)]

        if True:
            # Use summary and global
            cols = featinfo.select_columns([
                ('measure_type', '==', 'summary'),
            ])
            cols.update(featinfo.select_columns([
                ('measure_type', '==', 'global'),
            ]))
            X_dict['learn(sum,glob)'] = featinfo.X[sorted(cols)]

            if True:
                # Remove view columns
                view_cols = featinfo.select_columns([
                    ('measure_type', '==', 'global'),
                    ('measure', 'in', ['yaw_1', 'yaw_2', 'yaw_delta']),
                ])
                cols = set.difference(cols, view_cols)
                X_dict['learn(sum,glob,-view)'] = featinfo.X[sorted(cols)]

        if True:
            # Only allow very specific summary features
            summary_cols = featinfo.select_columns([
                ('measure_type', '==', 'summary'),
                ('summary_op', 'in', ['len']),
            ])
            summary_cols.update(featinfo.select_columns([
                ('measure_type', '==', 'summary'),
                ('summary_op', 'in', ['sum']),
                ('summary_measure', 'in', [
                    'weighted_ratio', 'ratio',
                    'norm_dist', 'weighted_norm_dist',
                    'fgweights',
                    'weighted_lnbnn_norm_dist', 'lnbnn_norm_dist',
                    'norm_y2', 'norm_y1',
                    # 'norm_x1', 'norm_x2',
                    'scale1', 'scale2',
                    # 'weighted_norm_dist',
                    # 'weighted_lnbnn_norm_dist',
                ]),
            ]))
            summary_cols.update(featinfo.select_columns([
                ('measure_type', '==', 'summary'),
                ('summary_op', 'in', ['mean']),
                ('summary_measure', 'in', [
                    'sver_err_xy', 'sver_err_ori',
                    # 'sver_err_scale',
                    'norm_y1', 'norm_y2',
                    'norm_x1', 'norm_x2',
                    'ratio',
                ]),
            ]))
            summary_cols.update(featinfo.select_columns([
                ('measure_type', '==', 'summary'),
                ('summary_op', 'in', ['std']),
                ('summary_measure', 'in', [
                    'norm_y1', 'norm_y2',
                    'norm_x1', 'norm_x2',
                    'scale1', 'scale2',
                    'sver_err_ori', 'sver_err_xy',
                    # 'sver_err_scale',
                    # 'match_dist',
                    'norm_dist', 'ratio'
                ]),
            ]))

            global_cols = featinfo.select_columns([
                ('measure_type', '==', 'global'),
                ('measure', 'not in', [
                    'gps_2[0]', 'gps_2[1]',
                    'gps_1[0]', 'gps_1[1]',
                    # 'time_1', 'time_2',
                ]),
                # NEED TO REMOVE YAW BECAUSE WE USE IT IN CONSTRUCTING LABELS
                ('measure', 'not in', [
                    'yaw_1', 'yaw_2', 'yaw_delta'
                ]),
            ])

            if 0:
                cols = set([])
                cols.update(summary_cols)
                cols.update(global_cols)
                X_dict['learn(sum,glob,3)'] = featinfo.X[sorted(cols)]

            if 0:
                cols = set([])
                cols.update(summary_cols)
                cols.update(global_cols)
                cols.update(featinfo.select_columns([
                    ('measure_type', '==', 'global'),
                    # Add yaw back in if not_comp is explicitly labeled
                    ('measure', 'in', [
                        'yaw_1', 'yaw_2', 'yaw_delta'
                    ]),
                ]))
                X_dict['learn(sum,glob,3,+view)'] = featinfo.X[sorted(cols)]

            # if 0:
            #     summary_cols_ = summary_cols.copy()
            #     summary_cols_ = [c for c in summary_cols_ if 'lnbnn' not in c]
            #     cols = set([])
            #     cols.update(summary_cols_)
            #     cols.update(global_cols)
            #     X_dict['learn(sum,glob,4)'] = featinfo.X[sorted(cols)]

            # if 0:
            #     cols = set([])
            #     cols.update(summary_cols)
            #     cols.update(global_cols)
            #     cols.update(featinfo.select_columns([
            #         ('measure_type', '==', 'local'),
            #         ('local_sorter', 'in', ['weighted_ratio', 'lnbnn_norm_dist']),
            #         ('local_measure', 'in', ['weighted_ratio']),
            #         ('local_rank', '<', 20),
            #         ('local_rank', '>', 0),
            #     ]))
            #     X_dict['learn(loc,sum,glob,5)'] = featinfo.X[sorted(cols)]
        pblm.samples.X_dict = X_dict

    def evaluate_simple_scores(pblm, task_keys=None):
        """
            >>> from ibeis.scripts.script_vsone import *  # NOQA
            >>> pblm = OneVsOneProblem()
            >>> pblm.set_pandas_options()
            >>> pblm.load_features()
            >>> pblm.load_samples()
            >>> pblm.evaluate_simple_scores()
        """
        score_dict = pblm.samples.simple_scores.copy()
        if True:
            # Remove scores that arent worth reporting
            for k in list(score_dict.keys())[:]:
                ignore = [
                    'sum(norm_x', 'sum(norm_y',
                    'sum(sver_err', 'sum(scale',
                    'sum(match_dist)',
                    'sum(weighted_norm_dist',
                ]
                if pblm.qreq_.qparams.featweight_enabled:
                    ignore.extend([
                        # 'sum(norm_dist)',
                        # 'sum(ratio)',
                        # 'sum(lnbnn)',
                        # 'sum(lnbnn_norm_dist)'
                    ])
                flags = [part in k for part in ignore]
                if any(flags):
                    del score_dict[k]

        if task_keys is None:
            task_keys = list(pblm.samples.subtasks.keys())

        simple_aucs = {}
        for task_key in task_keys:
            task_aucs = {}
            labels = pblm.samples.subtasks[task_key]
            for sublabels in labels.gen_one_vs_rest_labels():
                sublabel_aucs = {}
                for scoretype in score_dict.keys():
                    scores = score_dict[scoretype].values
                    auc = sklearn.metrics.roc_auc_score(sublabels.y_enc, scores)
                    sublabel_aucs[scoretype] = auc
                # task_aucs[sublabels.task_key] = sublabel_aucs
                task_aucs[sublabels.task_name.replace(task_key, '')] = sublabel_aucs
            simple_aucs[task_key] = task_aucs
        pblm.simple_aucs = simple_aucs

    def report_simple_scores(pblm, task_key):
        force_keep = ['score_lnbnn_1vM']
        simple_aucs = pblm.simple_aucs
        from utool.experimental.pandas_highlight import to_string_monkey
        n_keep = 6
        df_simple_auc = pd.DataFrame.from_dict(simple_aucs[task_key], orient='index')
        # Take only a subset of the columns that scored well in something
        rankings = df_simple_auc.values.argsort(axis=1).argsort(axis=1)
        rankings = rankings.shape[1] - rankings - 1
        ordered_ranks = np.array(vt.ziptake(rankings.T, rankings.argsort(axis=0).T)).T
        sortx = np.lexsort(ordered_ranks[::-1])
        keep_cols = df_simple_auc.columns[sortx][0:n_keep]
        extra = np.setdiff1d(force_keep, np.intersect1d(keep_cols, force_keep))
        keep_cols = keep_cols[:len(keep_cols) - len(extra)].tolist() + extra.tolist()
        # Now print them
        ut.cprint('\n[None] ROC-AUC of simple scoring measures for %s' % (task_key,), 'yellow')
        print(to_string_monkey(df_simple_auc[keep_cols], highlight_cols='all'))

    def report_classifier_importance(pblm, task_key, clf_key, data_key):
        # ut.qt4ensure()
        # import plottool as pt  # NOQA

        if clf_key != 'RF':
            return

        X = pblm.samples.X_dict[data_key]
        # Take average feature importance
        ut.cprint('MARGINAL IMPORTANCE INFO for %s on task %s' % (data_key, task_key), 'yellow')
        print(' Caption:')
        print(' * The NaN row ensures that `weight` always sums to 1')
        print(' * `num` indicates how many dimensions the row groups')
        print(' * `ave_w` is the average importance a single feature in the row')
        # with ut.Indenter('[%s] ' % (data_key,)):

        clf_list = pblm.task_clfs[task_key][clf_key][data_key]
        feature_importances = np.mean([
            clf_.feature_importances_ for clf_ in clf_list
        ], axis=0)
        importances = ut.dzip(X.columns, feature_importances)

        featinfo = AnnotPairFeatInfo(X, importances)

        featinfo.print_margins('feature')
        featinfo.print_margins('measure_type')
        featinfo.print_margins('summary_op')
        featinfo.print_margins('summary_measure')
        featinfo.print_margins('global_measure')
        # featinfo.print_margins([('measure_type', '==', 'summary'),
        #                     ('summary_op', '==', 'sum')])
        # featinfo.print_margins([('measure_type', '==', 'summary'),
        #                     ('summary_op', '==', 'mean')])
        # featinfo.print_margins([('measure_type', '==', 'summary'),
        #                     ('summary_op', '==', 'std')])
        # featinfo.print_margins([('measure_type', '==', 'global')])
        featinfo.print_margins('local_measure')
        featinfo.print_margins('local_sorter')
        featinfo.print_margins('local_rank')
        # pt.wordcloud(importances)


@ut.reloadable_class
class AnnotPairSamples(clf_helpers.MultiTaskSamples):
    """
    Manages the different ways to assign samples (i.e. feat-label pairs) to
    1-v-1 classification

    CommandLine:
        python -m ibeis.scripts.script_vsone AnnotPairSamples

    Example:
        >>> from ibeis.scripts.script_vsone import *  # NOQA
        >>> pblm = OneVsOneProblem()
        >>> pblm.load_features()
        >>> samples = AnnotPairSamples(pblm.ibs, pblm.raw_simple_scores, {})
        >>> print(samples)
        >>> samples.print_info()
        >>> print(samples.make_sample_hashid())
        >>> assert np.all(samples.index == samples.subtasks['match_state'].encoded_df.index)
        >>> assert np.all(samples.index == samples.subtasks['match_state'].indicator_df.index)
    """
    def __init__(samples, ibs, simple_scores=None, X_dict=None, index=None):
        if simple_scores is not None:
            assert index is None
            index = simple_scores.index
        else:
            assert index is not None
        if X_dict is not None:
            for X in X_dict.values():
                assert np.all(index == X.index)
        super(AnnotPairSamples, samples).__init__(index)
        samples.aid_pairs = np.array(index.tolist())
        samples.ibs = ibs
        samples.X_dict = X_dict
        samples.simple_scores = simple_scores
        samples.annots1 = ibs.annots(samples.aid_pairs.T[0], asarray=True)
        samples.annots2 = ibs.annots(samples.aid_pairs.T[1], asarray=True)
        samples.n_samples = len(index)

        samples.apply_multi_task_multi_label()
        # samples.apply_multi_task_binary_label()

    @property
    def primary_task(samples):
        primary_task_key = 'match_state'
        primary_task =  samples.subtasks[primary_task_key]
        return primary_task

    @ut.memoize
    def make_sample_hashid(samples):
        qvuuids = samples.annots1.visual_uuids
        dvuuids = samples.annots2.visual_uuids
        vsone_uuids = [
            ut.combine_uuids(uuids)
            for uuids in ut.ProgIter(zip(qvuuids, dvuuids), length=len(qvuuids),
                                     label='hashing ids')
        ]
        visual_hash = ut.hashstr_arr27(vsone_uuids, 'vuuids', pathsafe=True)
        label_hash = ut.hashstr_arr27(samples.encoded_1d(), 'labels', pathsafe=True)
        sample_hash = visual_hash + '_' + label_hash
        return sample_hash

    def compress(samples, flags):
        """
        flags = np.zeros(len(samples), dtype=np.bool)
        flags[0] = True
        flags[3] = True
        flags[4] = True
        flags[-1] = True
        """
        assert len(flags) == len(samples), 'mask has incorrect size'
        simple_scores = samples.simple_scores[flags]
        X_dict = ut.map_vals(lambda val: val[flags], samples.X_dict)
        ibs = samples.ibs
        new_labels = AnnotPairSamples(ibs, simple_scores, X_dict)
        return new_labels

    @ut.memoize
    def is_same(samples):
        # Hack to use infr implementation
        from ibeis.algo.hots.graph_iden import AnnotInference
        infr = AnnotInference(ibs=samples.ibs)
        return infr.is_same(samples.aid_pairs)

    @ut.memoize
    def is_photobomb(samples):
        # Hack to use infr implementation
        from ibeis.algo.hots.graph_iden import AnnotInference
        infr = AnnotInference(ibs=samples.ibs)
        return infr.is_photobomb(samples.aid_pairs)

    @ut.memoize
    def is_comparable(samples):
        # Hack to use infr implementation
        from ibeis.algo.hots.graph_iden import AnnotInference
        infr = AnnotInference(ibs=samples.ibs)
        return infr.is_comparable(samples.aid_pairs, allow_guess=True)

    def apply_multi_task_multi_label(samples):
        # multioutput-multiclass / multi-task
        tasks_to_indicators = ut.odict([
            ('match_state', ut.odict([
                ('nomatch', ~samples.is_same() & samples.is_comparable()),
                ('match',    samples.is_same() & samples.is_comparable()),
                ('notcomp', ~samples.is_comparable()),
            ])),
            ('photobomb_state', ut.odict([
                ('notpb', ~samples.is_photobomb()),
                ('pb',   samples.is_photobomb()),
            ]))
        ])
        samples.apply_indicators(tasks_to_indicators)

    def apply_multi_task_binary_label(samples):
        # multioutput-multiclass / multi-task
        tasks_to_indicators = ut.odict([
            ('same_state', ut.odict([
                ('notsame', ~samples.is_same()),
                ('same',     samples.is_same())
                # ('nomatch', ~samples.is_same() | ~samples.is_comparable()),
                # ('match',    samples.is_same() & samples.is_comparable()),
            ])),
            ('photobomb_state', ut.odict([
                ('notpb', ~samples.is_photobomb()),
                ('pb',   samples.is_photobomb()),
            ]))
        ])
        samples.apply_indicators(tasks_to_indicators)

    def apply_single_task_multi_label(samples):
        is_comp = samples.is_comparable()
        is_same = samples.is_same()
        is_pb   = samples.is_photobomb()
        tasks_to_indicators = ut.odict([
            ('match_pb_state', ut.odict([
                ('is_notcomp',       ~is_comp & ~is_pb),
                ('is_match',          is_same & is_comp & ~is_pb),
                ('is_nomatch',       ~is_same & is_comp & ~is_pb),
                ('is_notcomp_pb',    ~is_comp & is_pb),
                ('is_match_pb',       is_same & is_comp & is_pb),
                ('is_nomatch_pb',    ~is_same & is_comp & is_pb),
            ])),
        ])
        samples.apply_indicators(tasks_to_indicators)


@ut.reloadable_class
class AnnotPairFeatInfo(object):
    """
    Used to compute marginal importances over groups of features used in the
    pairwise one-vs-one scoring algorithm
    """
    def __init__(featinfo, X, importances=None):
        featinfo.X = X
        featinfo.importances = importances
        featinfo._summary_keys = ['sum', 'mean', 'med', 'std', 'len']

    def make_pairfeat_cfg(featinfo):
        criteria = [('measure_type', '==', 'local')]
        indices = sorted(map(int, set(map(
            featinfo.local_rank, featinfo.select_columns(criteria)))))
        sorters = sorted(set(map(
            featinfo.local_sorter, featinfo.select_columns(criteria))))

        criteria = [('measure_type', '==', 'global')]
        global_measures = sorted(set(map(
            featinfo.global_measure, featinfo.select_columns(criteria))))
        global_keys = sorted(set([key.split('_')[0]
                                  for key in global_measures]))
        global_keys.remove('speed')  # hack

        criteria = [('measure_type', '==', 'summary')]
        summary_ops = sorted(set(map(
            featinfo.summary_op, featinfo.select_columns(criteria))))
        summary_measures = sorted(set(map(
            featinfo.summary_measure, featinfo.select_columns(criteria))))
        summary_measures.remove('matches')
        pairfeat_cfg = {
            'summary_ops': summary_ops,
            'local_keys': summary_measures,
            'sorters': sorters,
            'indices': indices,
        }
        return pairfeat_cfg, global_keys

    def select_columns(featinfo, criteria, op='and'):
        """
        featinfo.select_columns([
            ('measure_type', '==', 'local'),
            ('local_sorter', 'in', ['weighted_ratio', 'lnbnn_norm_dist']),
        ])
        """
        if op == 'and':
            cols = set(featinfo.X.columns)
            update = cols.intersection_update
        elif op == 'or':
            cols = set([])
            update = cols.update
        else:
            raise Exception(op)
        for group_id, op, value in criteria:
            found = featinfo.find(group_id, op, value)
            update(found)
        return cols

    def find(featinfo, group_id, op, value):
        import six
        if isinstance(op, six.text_type):
            opdict = ut.get_comparison_operators()
            op = opdict.get(op)
        grouper = getattr(featinfo, group_id)
        found = []
        for col in featinfo.X.columns:
            value1 = grouper(col)
            if value1 is None:
                # Only filter out/in comparable things
                found.append(col)
            else:
                try:
                    if value1 is not None:
                        if isinstance(value, int):
                            value1 = int(value1)
                        elif isinstance(value, list):
                            if len(value) > 0 and isinstance(value[0], int):
                                value1 = int(value1)
                    if op(value1, value):
                        found.append(col)
                except:
                    pass
        return found

    def group_importance(featinfo, item):
        name, keys = item
        num = len(keys)
        weight = sum(ut.take(featinfo.importances, keys))
        ave_w = weight / num
        tup = ave_w, weight, num
        # return tup
        df = pd.DataFrame([tup], columns=['ave_w', 'weight', 'num'],
                          index=[name])
        return df

    def print_margins(featinfo, group_id, ignore_trivial=True):
        X = featinfo.X
        if isinstance(group_id, list):
            cols = featinfo.select_columns(criteria=group_id)
            _keys = [(c, [c]) for c in cols]
            try:
                _weights = pd.concat(ut.lmap(featinfo.group_importance, _keys))
            except ValueError:
                _weights = []
                pass
            nice = str(group_id)
        else:
            grouper = getattr(featinfo, group_id)
            _keys = ut.group_items(X.columns, ut.lmap(grouper, X.columns))
            _weights = pd.concat(ut.lmap(featinfo.group_importance, _keys.items()))
            nice = ut.get_funcname(grouper).replace('_', ' ')
            nice = ut.pluralize(nice)
        try:
            _weights = _weights.iloc[_weights['ave_w'].argsort()[::-1]]
        except Exception:
            pass
        if not ignore_trivial or len(_weights) > 1:
            ut.cprint('\nMarginal importance of ' + nice, 'white')
            print(_weights)

    def group_counts(featinfo, item):
        name, keys = item
        num = len(keys)
        tup = (num,)
        # return tup
        df = pd.DataFrame([tup], columns=['num'], index=[name])
        return df

    def print_counts(featinfo, group_id):
        X = featinfo.X
        grouper = getattr(featinfo, group_id)
        _keys = ut.group_items(X.columns, ut.lmap(grouper, X.columns))
        _weights = pd.concat(ut.lmap(featinfo.group_counts, _keys.items()))
        _weights = _weights.iloc[_weights['num'].argsort()[::-1]]
        nice = ut.get_funcname(grouper).replace('_', ' ')
        nice = ut.pluralize(nice)
        print('\nCounts of ' + nice)
        print(_weights)

    def measure(featinfo, key):
        return key[key.find('(') + 1:-1]

    def feature(featinfo, key):
        return key

    def measure_type(featinfo, key):
        if key.startswith('global'):
            return 'global'
        if key.startswith('loc'):
            return 'local'
        if any(key.startswith(p) for p in featinfo._summary_keys):
            return 'summary'

    def summary_measure(featinfo, key):
        if any(key.startswith(p) for p in featinfo._summary_keys):
            return featinfo.measure(key)

    def local_measure(featinfo, key):
        if key.startswith('loc'):
            return featinfo.measure(key)

    def global_measure(featinfo, key):
        if key.startswith('global'):
            return featinfo.measure(key)

    def summary_op(featinfo, key):
        for p in featinfo._summary_keys:
            if key.startswith(p):
                return key[0:key.find('(')]

    def local_sorter(featinfo, key):
        if key.startswith('loc'):
            return key[key.find('[') + 1:key.find(',')]

    def local_rank(featinfo, key):
        if key.startswith('loc'):
            return key[key.find(',') + 1:key.find(']')]

    def get_infostr(featinfo):
        """
        Summarizes the types (global, local, summary) of features in X based on
        standardized dimension names.
        """
        grouped_keys = ut.ddict(list)
        for key in featinfo.X.columns:
            type_ = featinfo.measure_type(key)
            grouped_keys[type_].append(key)

        info_items = ut.odict([
            ('global_measures', ut.lmap(featinfo.global_measure,
                                        grouped_keys['global'])),

            ('local_sorters', set(map(featinfo.local_sorter,
                                       grouped_keys['local']))),
            ('local_ranks', set(map(featinfo.local_rank,
                                     grouped_keys['local']))),
            ('local_measures', set(map(featinfo.local_measure,
                                        grouped_keys['local']))),

            ('summary_measures', set(map(featinfo.summary_measure,
                                          grouped_keys['summary']))),
            ('summary_ops', set(map(featinfo.summary_op,
                                     grouped_keys['summary']))),
        ])

        import textwrap
        def _wrap(list_):
            unwrapped = ', '.join(sorted(list_))
            indent = (' ' * 4)
            lines_ = textwrap.wrap(unwrapped, width=80 - len(indent))
            lines = ['    ' + line for line in lines_]
            return lines

        lines = []
        for item  in info_items.items():
            key, list_ = item
            if len(list_):
                title = key.replace('_', ' ').title()
                if key.endswith('_measures'):
                    groupid = key.replace('_measures', '')
                    num = len(grouped_keys[groupid])
                    title = title + ' (%d)' % (num,)
                lines.append(title + ':')
                if key == 'summary_measures':
                    other = info_items['local_measures']
                    if other.issubset(list_) and len(other) > 0:
                        remain = list_ - other
                        lines.extend(_wrap(['<same as local_measures>'] + list(remain)))
                    else:
                        lines.extend(_wrap(list_))
                else:
                    lines.extend(_wrap(list_))

        infostr = '\n'.join(lines)
        return infostr
        # print(infostr)


def build_features(qreq_, hyper_params):
    """
    Cached output of one-vs-one matches

    Example:
        >>> from ibeis.scripts.script_vsone import *  # NOQA
        >>> pblm = OneVsOneProblem()
        >>> qreq_ = pblm.qreq_
        >>> hyper_params = pblm.hyper_params
    """
    import pandas as pd
    import vtool as vt
    import ibeis

    # ==================================
    # Compute or load one-vs-one results
    # ==================================
    # Get a set of training pairs
    ibs = qreq_.ibs
    cm_list = qreq_.execute()
    infr = ibeis.AnnotInference.from_qreq_(qreq_, cm_list, autoinit=True)

    # Per query choose a set of correct, incorrect, and random training pairs
    aid_pairs_ = infr._cm_training_pairs(rng=np.random.RandomState(42),
                                         **hyper_params.pair_sample)
    pb_aid_pairs = photobomb_samples(ibs)
    # TODO: try to add in more non-comparable samples
    aid_pairs = pb_aid_pairs + aid_pairs_
    # Simplify life by using undirected pairs
    aid_pairs = vt.to_undirected_edges(np.array(aid_pairs), upper=True)
    aid_pairs = ut.lmap(tuple, vt.unique_rows(aid_pairs).tolist())
    # Keep only a random subset
    assert hyper_params.subsample is None

    config = hyper_params.vsone_assign
    pairfeat_cfg = hyper_params.pairwise_feats

    matches, X_all = infr._make_pairwise_features(
        aid_pairs, config=config, pairfeat_cfg=pairfeat_cfg)

    aid_pairs_ = [(m.annot1['aid'], m.annot2['aid']) for m in matches]
    assert aid_pairs_ == aid_pairs, 'edge ordering changed'

    # Pass back just one match to play with
    for match in matches:
        if len(match.fm) > 10:
            break

    # ---------------
    # Construct simple scores to learning comparison
    simple_scores = pd.DataFrame([
        m._make_local_summary_feature_vector(summary_ops={'sum', 'len'})
        for m in ut.ProgIter(matches, 'make simple scores')],
        index=X_all.index,
    )

    if True:
        # Add vsmany_lnbnn to simple scores
        infr.add_aids(ut.unique(ut.flatten(aid_pairs)))
        # Ensure that all annots exist in the graph
        infr.graph.add_edges_from(aid_pairs)
        # test original lnbnn score sep
        infr.apply_match_scores()
        edge_data = [infr.graph.get_edge_data(u, v) for u, v in aid_pairs]
        lnbnn_score_list = [0 if d is None else d.get('score', 0)
                            for d in edge_data]
        lnbnn_score_list = np.nan_to_num(lnbnn_score_list)
        simple_scores = simple_scores.assign(score_lnbnn_1vM=lnbnn_score_list)
    simple_scores[pd.isnull(simple_scores)] = 0

    return aid_pairs, simple_scores, X_all, match


def demo_single_pairwise_feature_vector():
    r"""
    CommandLine:
        python -m ibeis.scripts.script_vsone demo_single_pairwise_feature_vector

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.scripts.script_vsone import *  # NOQA
        >>> match = demo_single_pairwise_feature_vector()
        >>> print(match)
    """
    import vtool as vt
    import ibeis
    ibs = ibeis.opendb('testdb1')
    qaid, daid = 1, 2
    annot1 = ibs.annots([qaid])[0]._make_lazy_dict()
    annot2 = ibs.annots([daid])[0]._make_lazy_dict()

    vt.matching.ensure_metadata_normxy(annot1)
    vt.matching.ensure_metadata_normxy(annot2)

    match = vt.PairwiseMatch(annot1, annot2)
    cfgdict = {'checks': 200, 'symmetric': False}
    match.assign(cfgdict=cfgdict)
    match.apply_ratio_test({'ratio_thresh': .638}, inplace=True)
    match.apply_sver(inplace=True)

    match.add_global_measures(['yaw', 'qual', 'gps', 'time'])
    match.add_local_measures()

    # sorters = ['ratio', 'norm_dist', 'match_dist']
    match.make_feature_vector()
    return match


def photobomb_samples(ibs):
    """
    import ibeis
    ibs = ibeis.opendb('PZ_Master1')
    """
    # all_annots = ibs.annots()
    am_rowids = ibs._get_all_annotmatch_rowids()
    am_tags = ibs.get_annotmatch_case_tags(am_rowids)

    # ut.dict_hist(ut.flatten(am_tags))
    am_flags = ut.filterflags_general_tags(am_tags, has_any=['photobomb'])
    am_rowids_ = ut.compress(am_rowids, am_flags)
    aids1 = ibs.get_annotmatch_aid1(am_rowids_)
    aids2 = ibs.get_annotmatch_aid2(am_rowids_)

    if False:
        a1 = ibs.annots(aids1, asarray=True)
        a2 = ibs.annots(aids2, asarray=True)
        flags = a1.nids == a2.nids
        a1_ = a1.compress(flags)
        a2_ = a2.compress(flags)
        import guitool as gt
        ut.qt4ensure()
        gt.ensure_qapp()
        from vtool import inspect_matches
        import vtool as vt
        i = 1
        annot1 = a1_[i]._make_lazy_dict()
        annot2 = a2_[i]._make_lazy_dict()

        def on_context():
            from ibeis.gui import inspect_gui
            return inspect_gui.make_annotpair_context_options(
                ibs, annot1['aid'], annot1['aid'], None)

        match = vt.PairwiseMatch(annot1, annot2)
        inspect_matches.MatchInspector(match=match,
                                       on_context=on_context).show()
    return list(zip(aids1, aids2))


if __name__ == '__main__':
    r"""
    CommandLine:
        python -m ibeis.scripts.script_vsone
        python -m ibeis.scripts.script_vsone --allexamples
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
