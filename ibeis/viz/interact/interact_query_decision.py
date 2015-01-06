from __future__ import absolute_import, division, print_function
import utool
import utool as ut
import ibeis
from plottool import interact_helpers as ih
from plottool import draw_func2 as df2
from ibeis.viz.interact import interact_matches  # NOQA
# from ibeis.gui import guiback
from functools import partial
import guitool
from ibeis.viz import viz_chip
from ibeis.viz import viz_matches
from plottool.abstract_interaction import AbstractInteraction
ut.noinject(__name__, '[interact_query_decision]')
#(print, print_, printDBG, rrr, profile) = utool.inject(__name__,
#                                                       '[interact_query_decision]', DEBUG=False)


#==========================
# query interaction
#==========================

NUM_TOP = 3


def test_QueryVerificationInteraction():
    """
    CommandLine:
        python -m ibeis.viz.interact.interact_query_decision --test-test_QueryVerificationInteraction

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.viz.interact.interact_query_decision import *  # NOQA
        >>> # build test data
        >>> # execute function
        >>> result = test_QueryVerificationInteraction()
        >>> # verify results
        >>> print(result)
    """
    ibs = ibeis.opendb('testdb1')
    valid_aids = ibs.get_valid_aids()
    qaids = valid_aids[0:1]
    daids = valid_aids[1:]
    qres = ibs.query_chips(qaids, daids)[0]
    comp_aids = qres.get_top_aids(ibs=ibs, name_scoring=True)[0:NUM_TOP]
    suggest_aids = comp_aids[0:1]
    qvi = QueryVerificationInteraction(
        ibs, qres, comp_aids, suggest_aids, progress_current=42, progress_total=1337)
    qvi.fig.show()
    exec(df2.present())


class QueryVerificationInteraction(AbstractInteraction):
    def __init__(self, ibs, qres, comp_aids, suggest_aids, progress_current=None,
                 progress_total=None, update_callback=None,
                 backend_callback=None, name_decision_callback=None, **kwargs):
        print('[matchver] __init__')
        super(QueryVerificationInteraction, self).__init__(**kwargs)
        print('[matchver] comp_aids=%r' % (comp_aids,))
        print('[matchver] suggest_aids=%r' % (suggest_aids,))
        self.ibs = ibs
        self.qres = qres
        self.query_aid = self.qres.get_qaid()
        ibs.assert_valid_aids(comp_aids, verbose=True)
        ibs.assert_valid_aids(suggest_aids, verbose=True)
        ibs.assert_valid_aids((self.query_aid,), verbose=True)
        assert(len(comp_aids) <= NUM_TOP)
        self.comp_aids = comp_aids
        self.suggest_aids = suggest_aids
        self.progress_current = progress_current
        self.progress_total = progress_total
        if update_callback is None:
            update_callback = lambda: None
        if backend_callback is None:
            backend_callback = lambda: None
        if name_decision_callback is None:
            name_decision_callback = lambda aids: None
        self.update_callback = update_callback  # if something like qt needs a manual refresh on change
        self.backend_callback = backend_callback
        self.name_decision_callback = name_decision_callback
        self.checkbox_states = {}
        self.qres_callback = kwargs.get('qres_callback', None)
        self.infer_data()
        self.show_page(bring_to_front=True)

    def infer_data(self):
        """ Initialize data related to the input aids """
        ibs = self.ibs

        self.query_nid = ibs.get_annot_name_rowids(self.query_aid)
        self.comp_nids = ibs.get_annot_name_rowids(self.comp_aids)
        self.query_name = ibs.get_annot_names(self.query_aid)
        self.comp_names = ibs.get_annot_names(self.comp_aids)

        self.aid_list = [self.query_aid] + self.comp_aids

        # qres = ibs.query_chips(query_aid,)

        #HACK: make sure that comp_aids is of length NUM_TOP
        if len(self.comp_aids) != NUM_TOP:
            self.comp_aids += [None for i in range(NUM_TOP - len(self.comp_aids))]

        #column for each comparasion + the none button
        #row for the query, row for the comparasions
        self.nCols = len(self.comp_aids)
        self.nRows = 2

    def prepare_page(self):
        figkw = {
            'fnum': self.fnum,
            'doclf': True,
            'docla': True,
        }
        self.fig = df2.figure(**figkw)
        ih.disconnect_callback(self.fig, 'button_press_event')
        # ih.connect_callback(self.fig, 'button_press_event', self.figure_clicked)

    def show_page(self, bring_to_front=False):
        """ Plots all subaxes on a page """
        print('[querydec] show_page()')
        self.prepare_page()
        # Variables we will work with to paint a pretty picture
        #ibs = self.ibs
        nRows = self.nRows
        nCols = self.nCols

        #Plot the Comparisions
        for count, c_aid in enumerate(self.comp_aids):
            if c_aid is not None:
                px = nCols + count + 1
                if c_aid in self.suggest_aids:
                    self.plot_chip(c_aid, nRows, nCols, px, title_suffix='SUGGESTED BY IBEIS')
                else:
                    self.plot_chip(c_aid, nRows, nCols, px)
            else:
                df2.imshow_null(fnum=self.fnum, pnum=(nRows, nCols, nCols + count + 1), title='NO RESULT')

        #Plot the Query Chip last
        with ut.EmbedOnException():
            query_title = 'Identify This Animal'
            self.plot_chip(self.query_aid, nRows, 1, 1, title_suffix=query_title)

        self.show_hud()
        df2.adjust_subplots_safe(top=0.88, hspace=0.12)
        self.draw()
        self.show()
        if bring_to_front:
            self.bring_to_front()
        #self.update()

    def plot_chip(self, aid, nRows, nCols, px, **kwargs):
        """ Plots an individual chip in a subaxis """
        ibs = self.ibs
        if aid in self.comp_aids:
            score    = self.qres.get_aid_scores([aid])[0]
            rawscore = self.qres.get_aid_scores([aid], rawscore=True)[0]
            title_suf = kwargs.get('title_suffix', '')
            title_suf += '\n score=%0.2f' % score
            title_suf += '\n rawscore=%0.2f' % rawscore
        else:
            title_suf = kwargs.get('title_suffix', '')
        #nid = ibs.get_annot_name_rowids(aid)
        viz_chip_kw = {
            'fnum': self.fnum,
            'pnum': (nRows, nCols, px),
            'nokpts': True,
            'show_name': True,
            'show_gname': False,
            'show_aidstr': False,
            'show_exemplar': False,
            'show_num_gt': False,
            'show_gname': False,
            'enable_chip_title_prefix': False,
            'title_suffix': title_suf,
            # 'text_color': kwargs.get('color'),
        }

        viz_chip.show_chip(ibs, aid, **viz_chip_kw)
        ax = df2.gca()
        if kwargs.get('make_buttons', True):
            divider = df2.ensure_divider(ax)
            butkw = {
                'divider': divider,
                'size': '13%'
            }

        if aid in self.comp_aids:
            callback = partial(self.select, aid)
            self.append_button('Select This Animal', callback=callback, **butkw)
            #Hack to toggle colors
            if aid in self.checkbox_states:
                #If we are selecting it, then make it green, otherwise change it back to grey
                button = self.checkbox_states[aid]  # NOQA
                if self.checkbox_states[aid]:
                    df2.draw_border(ax, color=(0, 1, 0), lw=4)
                else:
                    df2.draw_border(ax, color=(.7, .7, .7), lw=4)
            else:
                self.checkbox_states[aid] = False
            self.append_button('Examine', callback=partial(self.examine, aid), **butkw)

    def select(self, aid, event=None):
        print(' selected aid %r as best choice' % aid)
        state = self.checkbox_states[aid]
        self.checkbox_states[aid] = not state
        # if self.checkbox_states[aid]:
        #     df2.draw_border(ax, color=(0, 1, 0), lw=4)
        # else:
        #     df2.draw_border(ax, color=(.7, .7, .7), lw=4)
        self.update_callback()
        self.backend_callback()
        self.show_page()

    def examine(self, aid, event=None):
        print(' examining aid %r against the query result' % aid)
        figtitle = 'Examine a specific image against the query'
        #interact_matches.ishow_matches(self.ibs, self.qres, aid, figtitle=figtitle)
        fig = df2.figure(fnum=510, pnum=(1, 1, 1), doclf=True, docla=True)
        viz_matches.show_matches(self.ibs, self.qres, aid, figtitle=figtitle)
        fig.show()
        # this is only relevant to matplotlib.__version__ < 1.4.2
        #raise Exception(
        #    'BLACK MAGIC: error intentionally included as a workaround that seems'
        #    'to fix a gui hang on certain computers.')

    def show_hud(self):
        """ Creates heads up display """
        # Button positioners
        hl_slot, hr_slot = df2.make_bbox_positioners(y=.02, w=.16,
                                                     h=3 * utool.PHI_B ** 4,
                                                     xpad=.02, startx=0, stopx=1)

        select_none_text = 'None of these'
        if len(self.suggest_aids) == 0:
            select_none_text += '\n(SUGGESTED BY IBEIS)'

        self.append_button(select_none_text, callback=partial(self.select_none), rect=hl_slot(0))
        self.append_button('Confirm Selection', callback=partial(self.confirm), rect=hl_slot(1))
        if self.progress_current is not None and self.progress_total is not None:
            self.progress_string = str(self.progress_current) + '/' + str(self.progress_total)
        else:
            self.progress_string = ''
        figtitle_fmt = '''
        Animal Identification {progress_string}
        '''
        figtitle = figtitle_fmt.format(**self.__dict__)  # sexy: using obj dict as fmtkw
        df2.set_figtitle(figtitle)

    def select_none(self, event=None):
        for aid in self.comp_aids:
            self.checkbox_states[aid] = False
        self.confirm()

    def confirm(self, event=None):
        """

        CommandLine:
            python -m ibeis.viz.interact.interact_query_decision --test-confirm

        Example:
            >>> # DISABLE_DOCTEST
            >>> from ibeis.viz.interact.interact_query_decision import *  # NOQA
            >>> import utool as ut
            >>> # build test data
            >>> import ibeis
            >>> ibs = ibeis.opendb('testdb1')
            >>> self = ibs
            >>> self.ibs = ibs
            >>> selected_aids = ut.get_list_column(ibs.get_name_aids(ibs.get_valid_nids()), 0)
            >>> comfirm_res = 'jeff'
            >>> # execute function
            >>> #result = self.confirm(event)
            >>> # verify results
            >>> #print(result)
        """
        print('[interact_query_decision] Confirming selected animals.')

        selected_aids = [aid for aid in self.comp_aids
                         if aid is not None and self.checkbox_states[aid]]
        if len(selected_aids) == 0:
            print('[interact_query_decision] Confirming no match.')
            chosen_aids = []
        elif len(selected_aids) == 1:
            print('[interact_query_decision] Confirming single match')
            chosen_aids = selected_aids
        else:
            print('[interact_query_decision] Confirming merge')
            msg = ut.textblock(
                '''
                You have selected more than one animal as a match to the query
                animal.  By doing this you are telling IBEIS that these are ALL
                the SAME ANIMAL.  \n\n\nIf this is not what you want, click
                Cancel.  If it is what you want, choose one of the names below
                as the name to keep.
                ''')
            selected_names = self.ibs.get_annot_names(selected_aids)
            options = selected_names
            parent = None
            title = 'Confirm Merge'
            merge_name = guitool.user_option(parent, msg=msg, title=title,
                                             options=options)
            if merge_name is None:
                print('[interact_query_decision] cancelled merge')
                self.update_callback()
                self.backend_callback()
                self.show_page()
                return
            else:
                print('[interact_query_decision] confirmed merge')
                is_merge_name = [merge_name == name_ for name_ in selected_names]
                chosen_aids = ut.sortedby(selected_aids, is_merge_name)[::-1]

        print('[interact_query_decision] Calling update callbacks')
        self.update_callback()
        self.backend_callback()
        print('[interact_query_decision] Calling decision callback')
        print('[interact_query_decision] self.name_decision_callback = %r' % (self.name_decision_callback,))
        chosen_names = self.ibs.get_annot_names(chosen_aids)
        self.name_decision_callback(chosen_names)
        print('[interact_query_decision] sent name_decision_callback(chosen_names=%r)' % (chosen_names,))


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.viz.interact.interact_query_decision
        python -m ibeis.viz.interact.interact_query_decision --allexamples
        python -m ibeis.viz.interact.interact_query_decision --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
