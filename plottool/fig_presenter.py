from __future__ import absolute_import, division, print_function
import utool
import sys
import textwrap
import time
import warnings
# maptlotlib
import matplotlib as mpl
import matplotlib.pyplot as plt
# PyQt
from PyQt4 import QtGui
from PyQt4.QtCore import Qt
# Science
import numpy as np
from .custom_figure import get_fig
from .custom_constants import golden_wh


QT4_WINS = []
(print, print_, printDBG, rrr, profile) = utool.inject(__name__, '[df2]', DEBUG=False)


def unregister_qt4_win(win):
    global QT4_WINS
    if win == 'all':
        QT4_WINS = []


def register_qt4_win(win):
    global QT4_WINS
    QT4_WINS.append(win)


def OooScreen2():
    nRows = 1
    nCols = 1
    x_off = 30 * 4
    y_off = 30 * 4
    x_0 = -1920
    y_0 = 30
    w = (1912 - x_off) / nRows
    h = (1080 - y_off) / nCols
    return dict(num_rc=(1, 1), wh=(w, h), xy_off=(x_0, y_0), wh_off=(0, 10),
                row_first=True, no_tile=False)


# ---- GENERAL FIGURE COMMANDS ----

def set_geometry(fnum, x, y, w, h):
    fig = get_fig(fnum)
    qtwin = fig.canvas.manager.window
    qtwin.setGeometry(x, y, w, h)


def get_geometry(fnum):
    fig = get_fig(fnum)
    qtwin = fig.canvas.manager.window
    (x1, y1, x2, y2) = qtwin.geometry().getCoords()
    (x, y, w, h) = (x1, y1, x2 - x1, y2 - y1)
    return (x, y, w, h)


def get_screen_info():
    from PyQt4 import Qt, QtGui  # NOQA
    desktop = QtGui.QDesktopWidget()
    mask = desktop.mask()  # NOQA
    layout_direction = desktop.layoutDirection()  # NOQA
    screen_number = desktop.screenNumber()  # NOQA
    normal_geometry = desktop.normalGeometry()  # NOQA
    num_screens = desktop.screenCount()  # NOQA
    avail_rect = desktop.availableGeometry()  # NOQA
    screen_rect = desktop.screenGeometry()  # NOQA
    QtGui.QDesktopWidget().availableGeometry().center()  # NOQA
    normal_geometry = desktop.normalGeometry()  # NOQA


def get_all_figures():
    all_figures_ = [manager.canvas.figure for manager in
                    mpl._pylab_helpers.Gcf.get_all_fig_managers()]
    all_figures = []
    # Make sure you dont show figures that this module closed
    for fig in iter(all_figures_):
        if not 'df2_closed' in fig.__dict__.keys() or not fig.df2_closed:
            all_figures.append(fig)
    # Return all the figures sorted by their number
    all_figures = sorted(all_figures, key=lambda fig: fig.number)
    return all_figures


def get_all_qt4_wins():
    return QT4_WINS


def all_figures_show():
    for fig in iter(get_all_figures()):
        time.sleep(.1)
        fig.show()
        fig.canvas.draw()


def all_figures_tight_layout():
    for fig in iter(get_all_figures()):
        fig.tight_layout()
        #adjust_subplots()
        time.sleep(.1)


def ensure_app_is_running():
    import guitool
    app, is_root = guitool.init_qtapp()


def get_monitor_geom(monitor_num=0):
    from PyQt4 import QtGui  # NOQA
    ensure_app_is_running()
    desktop = QtGui.QDesktopWidget()
    rect = desktop.availableGeometry(screen=monitor_num)
    geom = (rect.x(), rect.y(), rect.width(), rect.height())
    return geom


def get_monitor_geometries():
    from PyQt4 import QtGui  # NOQA
    ensure_app_is_running()
    monitor_geometries = {}
    desktop = QtGui.QDesktopWidget()
    for screenx in xrange(desktop.numScreens()):
        rect = desktop.availableGeometry(screen=screenx)
        geom = (rect.x(), rect.y(), rect.width(), rect.height())
        monitor_geometries[screenx] = geom
    return monitor_geometries


def all_figures_tile(num_rc=None, wh=400, xy_off=(0, 0), wh_off=(0, 0),
                     row_first=True, no_tile=False, override1=False,
                     adaptive=False, monitor_num=0, **kwargs):
    """
    Lays out all figures in a grid. if wh is a scalar, a golden ratio is used
    """
    if 'nRows' in kwargs and 'nCols' in kwargs:
        num_rc = (kwargs['nRows'], kwargs['nCols'])

    print('[df2] all_figures_tile()')
    # RCOS TODO:
    # I want this function to layout all the figures and qt windows within the
    # bounds of a rectangle. (taken from the get_monitor_geom, or specified by
    # the user i.e. left half of monitor 0). It should lay them out
    # rectangularly and choose figure sizes such that all of them will fit.
    if no_tile:
        return

    if not np.iterable(wh):
        wh = golden_wh(wh)

    all_figures = get_all_figures()
    all_qt4wins = get_all_qt4_wins()

    if adaptive:
        print('adaptive tile')
        nFigures = len(all_figures)
        x, y, w, h = get_monitor_geom(monitor_num)
        if nFigures < 4:
            num_rc = num_rc = (nFigures, 1)
        else:
            num_rc = (4, np.ceil(nFigures // 4))
        wh = ((w / 2) / num_rc[1], h / num_rc[0])

    if override1:
        if len(all_figures) == 1:
            fig = all_figures[0]
            win = fig.canvas.manager.window
            win.setGeometry(0, 0, 900, 900)
            update()
            return

    #nFigs = len(all_figures) + len(all_qt4_wins)

    # Win7 Areo
    win7_sizes = {
        'os_border_x':   20,
        'os_border_y':   35,
        'os_border_h':   30,
        'win_border_x':  17,
        'win_border_y':  10,
        'mpl_toolbar_y': 10,
    }

    # Ubuntu (Medeterrainian Dark)
    gnome3_sizes = {
        'os_border_x':    0,
        'os_border_y':   35,  # for gnome3 title bar
        'os_border_h':    0,
        'win_border_x':   5,
        'win_border_y':  30,
        'mpl_toolbar_y':  0,
    }

    w, h = wh
    x_off, y_off = xy_off
    w_off, h_off = wh_off
    x_pad, y_pad = (0, 0)
    # Good offset measurements for...
    #Windows 7
    if sys.platform.startswith('win32'):
        stdpxls = win7_sizes
    if sys.platform.startswith('linux'):
        stdpxls = gnome3_sizes
    x_off +=  0
    y_off +=  0
    w_off +=  stdpxls['win_border_x']
    h_off +=  stdpxls['win_border_y'] + stdpxls['mpl_toolbar_y']
    # Pads are applied to all windows
    x_pad +=  stdpxls['os_border_x']
    y_pad +=  stdpxls['os_border_y']

    effective_w = w + w_off
    effective_h = h + h_off
    startx = 0
    starty = 0

    if num_rc is None:
        monitor_geometries = get_monitor_geometries()
        printDBG('[df2] monitor_geometries = %r' % (monitor_geometries,))
        geom = monitor_geometries[0]
        # Use all of monitor 0
        available_geom = (geom[0], geom[1], geom[2] - stdpxls['os_border_h'], geom[3])
        startx = available_geom[0]
        starty = available_geom[1]
        avail_width = available_geom[2] - available_geom[0]
        avail_height = available_geom[3] - available_geom[1]
        printDBG('[df2] available_geom = %r' % (available_geom,))
        printDBG('[df2] avail_width = %r' % (avail_width,))
        printDBG('[df2] avail_height = %r' % (avail_height,))

        nRows = int(avail_height // (effective_h))
        nCols = int(avail_width // (effective_w))
    else:
        nRows, nCols = num_rc

    printDBG('[df2] Tile all figures: ')
    printDBG('[df2]     wh = %r' % ((w, h),))
    printDBG('[df2]     xy_offsets = %r' % ((x_off, y_off),))
    printDBG('[df2]     wh_offsets = %r' % ((w_off, h_off),))
    printDBG('[df2]     wh_effective = %r' % ((effective_w, effective_h),))
    printDBG('[df2]     xy_pads = %r' % ((x_pad, y_pad),))
    printDBG('[df2]     nRows, nCols = %r' % ((nRows, nCols),))

    def position_window(ix, win):
        try:
            QMainWin = mpl.backends.backend_qt4.MainWindow
        except Exception as ex:
            try:
                utool.printex(ex, 'warning', '[df2]')
                QMainWin = mpl.backends.backend_qt4.QtGui.QMainWindow
            except Exception as ex1:
                utool.printex(ex1, 'warning', '[df2]')
                QMainWin = object

        isqt4_mpl = isinstance(win, QMainWin)
        isqt4_back = isinstance(win, QtGui.QMainWindow)
        if not isqt4_mpl and not isqt4_back:
            raise NotImplementedError('%r-th Backend %r is not a Qt Window' %
                                      (ix, win))
        if row_first:
            rowx = ix % nRows
            colx = int(ix // nRows)
        else:
            colx = (ix % nCols)
            rowx = int(ix // nCols)
        x = startx + colx * (effective_w)
        y = starty + rowx * (effective_h)
        printDBG('ix=%r) rowx=%r colx=%r, x=%r y=%r, w=%r, h=%r' %
                 (ix, rowx, colx, x, y, w, h))
        try:
            #(x, y, w1, h1) = win.getGeometry()
            win.setGeometry(x + x_pad, y + y_pad, w, h)
        except Exception as ex:
            print(ex)
    ioff = 0
    for i, win in enumerate(all_qt4wins):
        position_window(i, win)
        ioff += 1
    for i, fig in enumerate(all_figures):
        win = fig.canvas.manager.window
        position_window(i + ioff, win)


def all_figures_bring_to_front():
    try:
        all_figures = get_all_figures()
        for fig in iter(all_figures):
            bring_to_front(fig)
    except Exception as ex:
        print(ex)


def close_all_figures():
    all_figures = get_all_figures()
    for fig in iter(all_figures):
        close_figure(fig)


def close_figure(fig):
    fig.clf()
    fig.df2_closed = True
    qtwin = fig.canvas.manager.window
    qtwin.close()


def bring_to_front(fig):
    #what is difference between show and show normal?
    qtwin = fig.canvas.manager.window
    qtwin.raise_()
    qtwin.activateWindow()
    qtwin.setWindowFlags(Qt.WindowStaysOnTopHint)
    qtwin.setWindowFlags(Qt.WindowFlags(0))
    qtwin.show()


def show():
    all_figures_show()
    all_figures_bring_to_front()
    plt.show()


def reset():
    close_all_figures()


def draw():
    all_figures_show()


def update():
    draw()
    all_figures_bring_to_front()


def iupdate():
    if utool.inIPython():
        update()

iup = iupdate


def present(*args, **kwargs):
    'execing present should cause IPython magic'
    print('[df2] Presenting figures...')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        all_figures_tile(*args, **kwargs)
        all_figures_show()
        all_figures_bring_to_front()
    # Return an exec string
    execstr = utool.ipython_execstr()
    execstr += textwrap.dedent('''
    if not embedded:
        if not '--quiet' in sys.argv:
            print('[df2] Presenting in normal shell.')
            print('[df2] ... plt.show()')
        plt.show()
    ''')
    return execstr
