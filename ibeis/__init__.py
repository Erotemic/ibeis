# -*- coding: utf-8 -*-
"""
IBEIS: main package init

TODO: LAZY IMPORTS?
    http://code.activestate.com/recipes/473888-lazy-module-imports/
"""
# flake8: noqa
from __future__ import absolute_import, division, print_function, unicode_literals

__version__ = '2.3.0'

try:
    import cv2  # NOQA
except ImportError as ex:
    msg = ub.paragraph(
        '''
        The ibeis module failed to import the cv2 module.  This may be due to
        an issue https://github.com/opencv/opencv-python/issues/467 which
        prevents us from marking cv2 as package dependency.
        To work around this we require that the user install this package with
        one of the following extras tags:
        `pip install ibeis[graphics]` xor
        `pip install ibeis[headless]`.

        Alternatively, the user can directly install the cv2 package as a post
        processing step via:
        `pip install opencv-python-headless` xor
        `pip install opencv-python`.

        We appologize for this issue and hope this documentation is sufficient.

        orig_ex={!r}
        ''').format(ex)
    raise ImportError(msg)


try:
    import utool as ut
    import dtool_ibeis
except ImportError as ex:
    print('[ibeis !!!] ERROR: Unable to load all core utility modules.')
    print('[ibeis !!!] Perhaps try super_setup.py pull')
    raise

ut.noinject(__name__, '[ibeis.__init__]')
if ut.VERBOSE:
    print('[ibeis] importing ibeis __init__')


if ut.is_developer():
    standard_visualization_functions = [
        'show_image',
        'show_chip',
        'show_chipmatch',
        'show_chipmatches',
        'show_vocabulary',
        #'show_vocabulary',
    ]

# If we dont initialize plottool_ibeis before <something>
# then it causes a crash in windows. Its so freaking weird.
# something is not guitool_ibeis, ibeis.viz
# has to be before control, can be after constants, params, and main_module
#import plottool_ibeis


ENABLE_WILDBOOK_SIGNAL = True


try:
    from ibeis import constants
    from ibeis import constants as const
    from ibeis import params
    from ibeis import main_module
    from ibeis import other
    from ibeis.init import sysres
    #main_module._preload()

    from ibeis import control
    from ibeis import dbio
    #from ibeis import web

    from ibeis.init import sysres
    from ibeis.main_module import (main, _preload, _init_numpy, main_loop,
                                   opendb, opendb_in_background, opendb_bg_web)
    from ibeis.control.IBEISControl import IBEISController
    from ibeis.algo.hots.query_request import QueryRequest
    from ibeis.algo.hots.chip_match import ChipMatch, AnnotMatch
    from ibeis.algo.graph.core import AnnotInference
    from ibeis.init.sysres import (get_workdir, set_workdir, ensure_pz_mtest,
                                   ensure_nauts, ensure_wilddogs, list_dbs)
    from ibeis.init import main_helpers

    from ibeis import algo

    from ibeis import expt
    from ibeis import templates
    from ibeis.templates import generate_notebook
    from ibeis.control.controller_inject import register_preprocs
    from ibeis import core_annots
    from ibeis import core_images

    try:
        from ibeis.scripts import postdoc
    except ImportError:
        pass
except Exception as ex:
    ut.printex(ex, 'Error when importing ibeis', tb=True)
    raise

def import_subs():
    # Weird / Fancy loading.
    # I want to make this simpler
    from ibeis import algo
    from ibeis import viz
    from ibeis import web
    from ibeis import gui
    from ibeis import templates


def run_experiment(e='print', db='PZ_MTEST', dbdir=None, a=['unctrl'], t=['default'],
                   initial_aids=None, qaid_override=None, daid_override=None,
                   lazy=False, **kwargs):
    """
    Convience function

    CommandLine:
        ibeis -e print

    Args:
        e (str): (default = 'print')
        db (str): (default = 'PZ_MTEST')
        a (list): (default = ['unctrl'])
        t (list): (default = ['default'])
        qaid_override (None): (default = None)
        lazy (bool): (default = False)

    Returns:
        function: func -  live python function

    CommandLine:
        python -m ibeis.__init__ --exec-run_experiment --show

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis import *  # NOQA
        >>> e = 'rank_cmc'
        >>> db = 'testdb1'
        >>> a = ['default:species=primary']
        >>> t = ['default']
        >>> initial_aids = [2, 3, 4, 7, 9, 10, 11]
        >>> qaid_override = [1, 9, 10, 11, 2, 3]
        >>> testres = run_experiment(e, db, a, t, qaid_override=qaid_override,
        >>>                          initial_aids=initial_aids)
        >>> result = ('testres = %s' % (str(testres),))
        >>> print(result)
        >>> ut.quit_if_noshow()
        >>> testres.draw_func()
        >>> ut.show_if_requested()
    """
    import functools
    def find_expt_func(e):
        import utool as ut
        import ibeis.dev
        for tup in ibeis.dev.REGISTERED_DOCTEST_EXPERIMENTS:
            modname, funcname = tup[:2]
            aliases = tup[2] if len(tup) == 3 else []
            if e == funcname or e in aliases:
                module = ut.import_modname(modname)
                func = module.__dict__[funcname]
                return func
        # hack in --tf magic
        func = ut.find_testfunc('ibeis', funcname)[0]
        return func

    def build_commandline(e=e, **kwargs):
        # Equivalent command line version of this func
        import ibeis.dev
        valid_e_flags = ut.flatten([[tup[1]] if len(tup) == 2 else [tup[1]] + tup[2]
                                    for tup in ibeis.dev.REGISTERED_DOCTEST_EXPERIMENTS])
        if e in valid_e_flags:
            epref = '-e'
        else:
            # hack to use tf
            epref = '--tf'

        if dbdir is not None:
            db_flag = '--dbdir'
            db_value = dbdir
        else:
            db_flag = '--db'
            db_value = db
        command_parts = ['ibeis',
                         epref, e,
                         db_flag, db_value,
                         '-a', ' '.join(a).replace('(', '\(').replace(')', '\)'),
                         '-t', ' '.join(t),
                        ]
        if qaid_override is not None:
            command_parts.extend(['--qaid=' + ','.join(map(str, qaid_override))])
        if daid_override is not None:
            command_parts.extend(['--daid-override=' + ','.join(map(str, daid_override))])
        if 'disttype' in kwargs:
            command_parts.extend(['--disttype=', ','.join(map(str, kwargs['disttype']))])

        # hack parse out important args that were on command line
        if 'f' in kwargs:
            command_parts.extend(['-f', ' '.join(kwargs['f'])])
        if 'test_cfgx_slice' in kwargs:
            # very hacky, much more than checking for f
            slice_ = kwargs['test_cfgx_slice']
            slice_attrs = [getattr(slice_, attr, '')
                           for attr in ['start', 'stop', 'step']]
            slice_attrs = ut.replace_nones(slice_attrs, '')
            slicestr = ':'.join(map(str, slice_attrs))
            command_parts.extend(['--test_cfgx_slice', slicestr])

        command_parts.extend(['--show'])

        command_line_str = ' '.join(command_parts)
        # Warning, not always equivalent
        print('Equivalent Command Line:')
        print(command_line_str)
        return command_line_str
    command_line_str = build_commandline(**kwargs)


    def draw_cases(testres, **kwargs):
        e_ = 'draw_cases'
        func = find_expt_func(e_)
        ibs = testres.ibs
        build_commandline(e=e_, **kwargs)
        lazy_func = functools.partial(func, ibs, testres, show_in_notebook=True, **kwargs)
        return lazy_func

    def draw_taghist(testres, **kwargs):
        e_ = 'taghist'
        func = find_expt_func(e_)
        ibs = testres.ibs
        build_commandline(e=e_, **kwargs)
        lazy_func = functools.partial(func, ibs, testres, **kwargs)
        return lazy_func

    def execute_test():
        func = find_expt_func(e)
        assert func is not None, 'unknown experiment e=%r' % (e,)

        argspec = ut.get_func_argspec(func)
        if len(argspec.args) >= 2 and argspec.args[0] == 'ibs' and argspec.args[1] == 'testres':
            # most experiments need a testres
            expts_kw = dict(defaultdb=db, dbdir=dbdir, a=a, t=t,
                            qaid_override=qaid_override,
                            daid_override=daid_override,
                            initial_aids=initial_aids
                           )
            testdata_expts_func = functools.partial(main_helpers.testdata_expts, **expts_kw)

            ibs, testres = testdata_expts_func()
            # Build the requested drawing funciton
            draw_func = functools.partial(func, ibs, testres, **kwargs)
            testres.draw_func = draw_func
            ut.inject_func_as_method(testres, draw_cases)
            ut.inject_func_as_method(testres, draw_taghist)
            #testres.draw_cases = draw_cases
            return testres
        else:
            raise AssertionError('Unknown type of function for experiment')

    if lazy:
        return execute_test
    else:
        testres = execute_test()
        return testres


def testdata_expts(*args, **kwargs):
    ibs, testres = main_helpers.testdata_expts(*args, **kwargs)
    return testres

#import_subs()
#from ibeis import gui
#from ibeis import algo
#from ibeis import templates
#from ibeis import viz
#from ibeis import web


#class _VizProxy(object):
#    def __init__(self):
#        pass

#    def getattr(self, key):
#        import ibeis.viz as viz
#        return getattr(viz, key)

#    def setattr(self, key, val):
#        import ibeis.viz as viz
#        return getattr(viz, key, val)


#viz = _VizProxy
#import apipkg
#apipkg.initpkg(__name__, {
#    'viz': {
#        'clone': "ibeis.viz",
#    }
#}
#)

from ibeis.init import main_helpers
testdata_cm = main_helpers.testdata_cm
testdata_cmlist = main_helpers.testdata_cmlist
testdata_qreq_ = main_helpers.testdata_qreq_
testdata_pipecfg = main_helpers.testdata_pipecfg
testdata_filtcfg = main_helpers.testdata_filtcfg
testdata_expts = main_helpers.testdata_expts
testdata_expanded_aids = main_helpers.testdata_expanded_aids
testdata_aids = main_helpers.testdata_aids

# Utool generated init makeinit.py
print, rrr, profile = ut.inject2(__name__)

def reload_subs(verbose=True):
    """ Reloads ibeis and submodules """
    import_subs()
    rrr(verbose=verbose)
    getattr(constants, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(main_module, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(params, 'rrr', lambda verbose: None)(verbose=verbose)
    getattr(other, 'reload_subs', lambda verbose: None)(verbose=verbose)
    getattr(dbio, 'reload_subs', lambda verbose: None)(verbose=verbose)
    getattr(algo, 'reload_subs', lambda verbose: None)(verbose=verbose)
    getattr(control, 'reload_subs', lambda verbose: None)(verbose=verbose)
    getattr(viz, 'reload_subs', lambda: None)()

    getattr(gui, 'reload_subs', lambda verbose: None)(verbose=verbose)
    getattr(algo, 'reload_subs', lambda verbose: None)(verbose=verbose)
    getattr(viz, 'reload_subs', lambda verbose: None)(verbose=verbose)
    getattr(web, 'reload_subs', lambda verbose: None)(verbose=verbose)

    rrr(verbose=verbose)
rrrr = reload_subs


from ibeis.control.DB_SCHEMA_CURRENT import VERSION_CURRENT

"""
Regen Command:
    Kinda have to work with the output of these. This module is hard to
    autogenerate correctly.

    cd /home/joncrall/code/ibeis/ibeis/other
    makeinit.py -x web viz tests gui
    makeinit.py -x constants params main_module other control dbio tests
"""

if __name__ == '__main__':
    r"""
    CommandLine:
        python -m ibeis
        python -m ibeis --allexamples
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
