from ibeis.scripts.script_vsone import OneVsOneProblem
import numpy as np
import utool as ut
import plottool as pt
import vtool as vt
import pathlib
import matplotlib as mpl
from ibeis.algo.graph.state import POSTV, NEGTV, INCMP  # NOQA

TMP_RC = {
    'legend.fontsize': 18,
    'axes.titlesize': 18,
    'axes.labelsize': 18,
    'legend.facecolor': 'w',
    'font.family': 'DejaVu Sans',
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
}

FIG_DPATH = pathlib.Path(ut.truepath('~/latex/crall-thesis-2017/figures_pairclf'))


def build_plots():
    pblm = OneVsOneProblem.from_empty('PZ_PB_RF_TRAIN')
    # pblm = OneVsOneProblem.from_empty('GZ_Master1')
    pblm.eval_task_keys = ['match_state', 'photobomb_state']
    data_key = pblm.default_data_key
    clf_key = pblm.default_clf_key
    pblm.eval_data_keys = [data_key]
    pblm.eval_clf_keys = [clf_key]
    pblm.setup_evaluation()

    # pblm.evaluate_classifiers()
    ibs = pblm.infr.ibs
    pblm.samples.print_info()

    species_code = ibs.get_database_species(pblm.infr.aids)[0]
    if species_code == 'zebra_plains':
        species = 'Plains Zebras'
        data_code = 'PZ_%d' % len(pblm.samples)
    if species_code == 'zebra_grevys':
        species = 'Grévy\'s Zebras'
        data_code = 'GZ_%d' % len(pblm.samples)

    self = ThesisPlots()
    self.species = species
    self.data_code = data_code
    self.data_key = data_key
    self.clf_key = clf_key

    self.build_importance_data(pblm, 'match_state')
    self.build_importance_data(pblm, 'photobomb_state')

    self.build_roc_data_positive(pblm)
    self.build_roc_data_photobomb(pblm)

    self.build_score_freq_positive(pblm)


def draw_plots(self):

    self.draw_score_hist()
    pass


@ut.reloadable_class
class ThesisPlots(object):
    def __init__(self):
        self.species = None
        self.data_code = None
        self.data_key = None
        self.clf_key = None
        # info
        self.task_importance = {}
        self.task_rocs = {}
        self.hard_cases = {}

        self.score_freq_lnbnn = None
        self.score_freq_pairclf = None

    def build_importance_data(self, pblm, task_key):
        self.task_importance[task_key] = pblm.feature_importance(task_key=task_key)

    def build_score_freq_positive(self, pblm):
        task_key = 'match_state'
        freq_plotdata = pblm.simple_scores_plotdata('score_lnbnn_1vM',
                                                    task_key=task_key,
                                                    target_class=POSTV)
        prob_plotdata = pblm.learned_prob_plotdata(task_key=task_key,
                                                   target_class=POSTV)
        self.score_freq_lnbnn = freq_plotdata
        self.score_freq_pairclf = prob_plotdata

    def build_roc_data_positive(self, pblm):
        task_key = 'match_state'
        target_class = POSTV
        res = pblm.task_combo_res[task_key][self.clf_key][self.data_key]
        c2 = pblm.simple_confusion('score_lnbnn_1vM', task_key=task_key)
        c3 = res.confusions(target_class)
        self.task_rocs[task_key] = [
            {'label': 'LNBNN', 'fpr': c2.fpr, 'tpr': c2.tpr, 'auc': c2.auc},
            {'label': 'pairwise', 'fpr': c3.fpr, 'tpr': c3.tpr, 'auc': c3.auc},
        ]

    def build_roc_data_photobomb(self, pblm, task_key):
        task_key = 'photobomb_state'
        target_class = 'pb'
        res = pblm.task_combo_res[task_key][self.clf_key][self.data_key]
        c1 = res.confusions(target_class)
        self.task_rocs[task_key] = [
            {'label': 'pairwise', 'fpr': c1.fpr, 'tpr': c1.tpr, 'auc': c1.auc},
        ]

    def build_hard_cases(self, pblm, task_key):
        # Find a failure case for each class
        res = pblm.task_combo_res[task_key][self.clf_key][self.data_key]
        case_df = res.hardness_analysis(pblm.samples, pblm.infr)

        failure_cases = case_df[(case_df['real_conf'] > 0) & case_df['failed']]
        if len(failure_cases) == 0:
            print('No reviewed failures exist. Do pblm.qt_review_hardcases')

        cases = []
        for (pred, real), group in failure_cases.groupby(('pred', 'real')):
            group = group.sort_values(['real_conf', 'easiness'])
            case = group.iloc[0]
            edge = tuple(ut.take(case, ['aid1', 'aid2']))
            cases.append({
                'edge': edge,
                'real': res.class_names[real],
                'pred': res.class_names[pred],
                'probs': res.probs_df.loc[edge]
            })
        self.hard_cases[task_key] = cases

    def draw_hard_cases(self, task_key, pblm):
        infr = pblm.infr
        dbname = pblm.infr.ibs.dbname
        dpath = FIG_DPATH.joinpath(dbname + '_' + task_key + '_failures')
        ut.ensuredir(str(dpath))

        from ibeis.constants import REVIEW
        for case in self.hard_cases[task_key]:
            aid1, aid2 = case['edge']
            real_name = case['real']
            pred_name = case['pred']
            real_nice, pred_nice = ut.take(REVIEW.CODE_TO_NICE,
                                           [real_name, pred_name])
            # Draw case
            fig = pt.figure(fnum=1, clf=True)
            ax = pt.gca()
            if False:
                infr.draw_aids([aid1, aid2], fnum=1)
            else:
                probs = case['probs'].to_dict()
                order = list(REVIEW.CODE_TO_NICE.values())
                order = ut.setintersect(order, probs.keys())
                probs = ut.map_dict_keys(REVIEW.CODE_TO_NICE, probs)
                probstr = ut.repr2(probs, precision=2, strkeys=True, nobr=True,
                                   key_order=order)
                xlabel = 'real={}, pred={},\n{}'.format(real_nice, pred_nice, probstr)

                config = pblm.hyper_params['vsone_match'].asdict()
                config.update(pblm.hyper_params['vsone_kpts'])
                match = infr._exec_pairwise_match([(aid1, aid2)], config)[0]
                match.show(ax, vert=False, ell_alpha=.3, modifysize=True)
                ax.set_xlabel(xlabel)
                fname = 'fail_{}_{}_{}_{}_{}_overlay.jpg'.format(task_key, real_nice,
                                                                 pred_nice, aid1, aid2)
                fpath = dpath.joinpath(fname)
                fig.savefig(str(fpath), dpi=256)
                vt.clipwhite_ondisk(str(fpath), str(fpath))

                ax.cla()
                match.show(ax, vert=False, overlay=False, modifysize=True)
                ax.set_xlabel(xlabel)
                fname = 'fail_{}_{}_{}_{}_{}.jpg'.format(task_key, real_nice,
                                                         pred_nice, aid1, aid2)
                fpath = dpath.joinpath(fname)
                fig.savefig(str(fpath), dpi=256)
                vt.clipwhite_ondisk(str(fpath), str(fpath))

        # nid1, nid2 = infr.pos_graph.node_labels(aid1, aid2)
        # cc1 = infr.pos_graph.connected_to(aid1)
        # cc2 = infr.pos_graph.connected_to(aid2)
        # cc3 = set.union(cc1, cc2)
        pass

    def draw_score_hist(self, freq_plotdata):
        key = freq_plotdata.get('key', freq_plotdata.get('data_key'))
        fname = 'scorehist_%s_%s.png' % (key, freq_plotdata['data_code'],)
        fig_fpath = FIG_DPATH.joinpath(fname)

        import plottool as pt
        fnum = 1
        pnum = (1, 1, 1)
        fnum = pt.ensure_fnum(fnum)
        bins = freq_plotdata['bins']
        pos_freq = freq_plotdata['pos_freq']
        neg_freq = freq_plotdata['neg_freq']
        true_color = pt.TRUE_BLUE
        false_color = pt.FALSE_RED
        score_colors = (false_color, true_color)
        fig = pt.multi_plot(
            bins, (neg_freq, pos_freq),
            label_list=('negative', 'positive'),
            fnum=fnum, color_list=score_colors, pnum=pnum, kind='bar',
            width=np.diff(bins)[0], alpha=.7, stacked=True, edgecolor='none',
            rcParams=TMP_RC,
            xlabel='positive probability', ylabel='frequency',
            title='pairwise probability separation')

        pt.adjust_subplots(top=.8, bottom=.2, left=.12, right=.9, wspace=.2,
                           hspace=.2)
        fig.set_size_inches([7.4375,  3.125])
        fig.savefig(str(fig_fpath), dpi=256)
        vt.clipwhite_ondisk(str(fig_fpath))

    def draw_roc(roc_data):
        mpl.rcParams.update(TMP_RC)

        target_class = roc_data['class']
        if target_class == 'pb':
            target_class = 'photobomb'
        if target_class == 'match':
            target_class = 'positive'

        fname = 'roc_%s_%s.png' % (target_class, roc_data['data_code'],)
        fig_fpath = FIG_DPATH.joinpath(fname)

        fig = pt.figure(fnum=1)  # NOQA
        ax = pt.gca()
        for algo in roc_data['algos']:
            ax.plot(algo['fpr'], algo['tpr'], label='%s AUC=%.2f' % (
                algo['label'], algo['auc']))
        ax.set_xlabel('false positive rate')
        ax.set_ylabel('true positive rate')
        ax.set_title('%s ROC for %s' % (target_class.title(),
                                        roc_data['species'],))
        ax.legend()
        pt.adjust_subplots(top=.8, bottom=.2, left=.12, right=.9, wspace=.2,
                           hspace=.2)
        fig.set_size_inches([7.4375,  3.125])
        fig.savefig(str(fig_fpath), dpi=256)
        vt.clipwhite_ondisk(str(fig_fpath))

    def draw_wordcloud(self, wc_data):
        import plottool as pt
        fnum = 2
        fname = 'wc_%s_%s.png' % (wc_data['task'], wc_data['data_code'],)
        fig_fpath = FIG_DPATH.joinpath(fname)
        fig = pt.figure(fnum=fnum)
        importances = wc_data['importances']
        importances = ut.map_keys(feat_map, importances)
        pt.wordcloud(importances, fnum=fnum)
        fig.savefig(str(fig_fpath), dpi=256)
        vt.clipwhite_ondisk(str(fig_fpath))

    def print_top_importance():
        # Print info for latex table
        importances = wc_data['importances']
        print('TOP 5 importances for ' + wc_data['task'])
        print('# of dimensions: %d' % (len(importances)))
        vals = importances.values()
        items = importances.items()
        top_dims = ut.sortedby(items, vals)[::-1]
        lines = []
        for k, v in top_dims[:5]:
            k = feat_map(k)
            k = k.replace('_', '\\_')
            lines.append('{} & {:.4f} \\\\'.format(k, v))
        print('\n'.join(ut.align_lines(lines, '&')))


def feat_map(k):
    # presentation values for feature dimension
    k = k.replace('weighted_', 'wgt_')
    k = k.replace('norm_x', 'x')
    k = k.replace('yaw', 'view')
    return k


def thesis_expt():
    pt.qtensure()
    # pblm = OneVsOneProblem.from_empty('PZ_PB_RF_TRAIN')
    pblm = OneVsOneProblem.from_empty('GZ_Master1')
    pblm.eval_task_keys = ['match_state', 'photobomb_state']
    data_key = pblm.default_data_key
    clf_key = pblm.default_clf_key
    pblm.eval_data_keys = [data_key]
    pblm.eval_clf_keys = [clf_key]
    pblm.setup_evaluation()
    # pblm.evaluate_classifiers()
    ibs = pblm.infr.ibs
    pblm.samples.print_info()

    species_code = ibs.get_database_species(pblm.infr.aids)[0]
    if species_code == 'zebra_plains':
        species = 'Plains Zebras'
        data_code = 'PZ_%d' % len(pblm.samples)
    if species_code == 'zebra_grevys':
        species = 'Grévy\'s Zebras'
        data_code = 'GZ_%d' % len(pblm.samples)

    task_key = 'match_state'
    match_wc_data = {
        'species': species,
        'task': task_key,
        'data_code': data_code,
        'importances': pblm.feature_importance(task_key=task_key),
    }
    draw_wordcloud(match_wc_data)
    print_top_importance(match_wc_data)

    # c1 = pblm.simple_confusion('sum(ratio)')
    task_key = 'match_state'
    match_state_res = pblm.task_combo_res[task_key][clf_key][data_key]
    target_class = POSTV
    c2 = pblm.simple_confusion('score_lnbnn_1vM')
    c3 = match_state_res.confusions(target_class)
    c2.label = 'LNBNN'
    c3.label = 'pairwise'
    roc_data = {
        'data_code': data_code,
        'class': 'positive',
        'species': species,
        'algos': [
            {'label': c2.label, 'fpr': c2.fpr, 'tpr': c2.tpr, 'auc': c2.auc},
            {'label': c3.label, 'fpr': c3.fpr, 'tpr': c3.tpr, 'auc': c3.auc},
        ],
    }
    draw_roc(roc_data)

    freq_plotdata = pblm.simple_scores_plotdata('score_lnbnn_1vM',
                                                task_key='match_state',
                                                target_class=POSTV)
    prob_plotdata = pblm.learned_prob_plotdata(task_key='match_state',
                                               target_class=POSTV)
    freq_plotdata['data_code'] = data_code
    prob_plotdata['data_code'] = data_code
    draw_score_hist(freq_plotdata)
    draw_score_hist(prob_plotdata)

    # Draw histogram

    latex_confusion(pblm, match_state_res)
    metric_df, confusion_df = match_state_res.extended_clf_report(verbose=False)
    print(metric_df[['precision', 'recall', 'mcc']].loc['ave/sum'])

    # Phototomb state plots
    task_key = 'photobomb_state'
    pb_state_res = pblm.task_combo_res[task_key][clf_key][data_key]
    importances = pblm.feature_importance(task_key=task_key)
    target_class = 'pb'
    c1 = pb_state_res.confusions(target_class)
    c1.label = 'pairwise'
    roc_data = {
        'data_code': data_code,
        'class': target_class,
        'species': species,
        'algos': [
            {'label': c1.label, 'fpr': c1.fpr, 'tpr': c1.tpr, 'auc': c1.auc},
        ],
    }
    draw_roc(roc_data)

    task_key = 'photobomb_state'
    importances = pblm.feature_importance(task_key=task_key)
    wc_data = {
        'species': species,
        'task': task_key,
        'data_code': data_code,
        'importances': importances,
    }
    print_top_importance(wc_data)
    draw_wordcloud(wc_data)

    pb_state_res.extended_clf_report()
    latex_confusion(pblm, pb_state_res)


def test_mcc():
    num = 100
    xdata = np.linspace(0, 1, num * 2)
    ydata = np.linspace(1, -1, num * 2)
    pt.plt.plot(xdata, ydata, '--k',
                label='linear')

    y_true = [1] * num + [0] * num
    y_pred = y_true[:]
    import sklearn.metrics
    xs = []
    for i in range(0, len(y_true)):
        y_pred[-i] = 1 - y_pred[-i]
        xs.append(sklearn.metrics.matthews_corrcoef(y_true, y_pred))

    import plottool as pt
    pt.plot(xdata, xs, label='change one class at a time')

    y_true = ut.flatten(zip([1] * num, [0] * num))
    y_pred = y_true[:]
    import sklearn.metrics
    xs = []
    for i in range(0, len(y_true)):
        y_pred[-i] = 1 - y_pred[-i]
        xs.append(sklearn.metrics.matthews_corrcoef(y_true, y_pred))

    pt.plot(xdata, xs, label='change classes evenly')
    pt.gca().legend()


def latex_confusion(pblm, res):
    import sklearn.metrics
    res.augment_if_needed()
    pred_enc = res.clf_probs.argmax(axis=1)
    y_pred = pred_enc
    y_true = res.y_test_enc
    sample_weight = res.sample_weight
    target_names = res.class_names

    ibs = pblm.infr.ibs
    try:
        target_nices = ut.take(ibs.const.REVIEW.CODE_TO_NICE, target_names)
    except:
        target_nices = target_names

    cm = sklearn.metrics.confusion_matrix(
        y_true, y_pred, sample_weight=sample_weight)
    confusion = cm  # NOQA
    import pandas as pd
    pred_id = ['p(%s)' % m for m in target_nices]
    real_id = ['r(%s)' % m for m in target_nices]
    sum_pred = 'Σp'
    sum_real = 'Σr'
    confusion_df = pd.DataFrame(confusion, columns=pred_id, index=real_id)
    confusion_df = confusion_df.append(pd.DataFrame(
        [confusion.sum(axis=0)], columns=pred_id, index=[sum_pred]))
    import numpy as np
    confusion_df[sum_real] = np.hstack([confusion.sum(axis=1), [np.nan]])

    latex_str = confusion_df.to_latex(
        float_format=lambda x: '' if np.isnan(x) else str(int(x)),
    )
    latex_str = latex_str.replace(sum_pred, '$\sum$ predicted')
    latex_str = latex_str.replace(sum_real, '$\sum$ real')
    colfmt = '|l|' + 'r' * len(target_nices) + '|l|'
    newheader = '\\begin{tabular}{%s}' % (colfmt,)
    latex_str = '\n'.join([newheader] + latex_str.split('\n')[1:])
    lines = latex_str.split('\n')
    lines = lines[0:-4] + ['\\midrule'] + lines[-4:]
    latex_str = '\n'.join(lines)
    latex_str = latex_str.replace('midrule', 'hline')
    # sum_real = '\\sum real'
    print(latex_str)
