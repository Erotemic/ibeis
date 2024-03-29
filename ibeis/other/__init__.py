# -*- coding: utf-8 -*-
# Autogenerated on 18:39:13 2016/02/22
# flake8: noqa
from __future__ import absolute_import, division, print_function, unicode_literals
from ibeis.other import dbinfo
from ibeis.other import duct_tape
from ibeis.other import detectcore
from ibeis.other import detectfuncs
from ibeis.other import detecttrain
from ibeis.other import ibsfuncs
import utool
print, rrr, profile = utool.inject2(__name__, '[ibeis.other]')


def reassign_submodule_attributes(verbose=True):
    """
    why reloading all the modules doesnt do this I don't know
    """
    import sys
    if verbose and '--quiet' not in sys.argv:
        print('dev reimport')
    # Self import
    import ibeis.other
    # Implicit reassignment.
    seen_ = set([])
    for tup in IMPORT_TUPLES:
        if len(tup) > 2 and tup[2]:
            continue  # dont import package names
        submodname, fromimports = tup[0:2]
        submod = getattr(ibeis.other, submodname)
        for attr in dir(submod):
            if attr.startswith('_'):
                continue
            if attr in seen_:
                # This just holds off bad behavior
                # but it does mimic normal util_import behavior
                # which is good
                continue
            seen_.add(attr)
            setattr(ibeis.other, attr, getattr(submod, attr))


def reload_subs(verbose=True):
    """ Reloads ibeis.other and submodules """
    if verbose:
        print('Reloading submodules')
    rrr(verbose=verbose)
    def wrap_fbrrr(mod):
        def fbrrr(*args, **kwargs):
            """ fallback reload """
            if verbose:
                print('No fallback relaod for mod=%r' % (mod,))
            # Breaks ut.Pref (which should be depricated anyway)
            # import imp
            # imp.reload(mod)
        return fbrrr
    def get_rrr(mod):
        if hasattr(mod, 'rrr'):
            return mod.rrr
        else:
            return wrap_fbrrr(mod)
    def get_reload_subs(mod):
        return getattr(mod, 'reload_subs', wrap_fbrrr(mod))
    get_rrr(dbinfo)(verbose=verbose)
    get_rrr(duct_tape)(verbose=verbose)
    get_rrr(detectfuncs)(verbose=verbose)
    get_rrr(detectcore)(verbose=verbose)
    get_rrr(detecttrain)(verbose=verbose)
    get_rrr(ibsfuncs)(verbose=verbose)
    rrr(verbose=verbose)
    try:
        # hackish way of propogating up the new reloaded submodule attributes
        reassign_submodule_attributes(verbose=verbose)
    except Exception as ex:
        print(ex)
rrrr = reload_subs

IMPORT_TUPLES = [
    ('dbinfo', None),
    ('duct_tape', None),
    ('detectfuncs', None),
    ('detectcore', None),
    ('detecttrain', None),
    ('ibsfuncs', None),
]
"""
Regen Command:
    cd /home/joncrall/code/ibeis/ibeis/other
    makeinit.py --modname=ibeis.other
"""
