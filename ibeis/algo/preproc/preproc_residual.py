# -*- coding: utf-8 -*-
"""
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from loguru import logger
import utool as ut


def add_residual_params_gen(ibs, fid_list, qreq_=None):
    return None


def on_delete(ibs, featweight_rowid_list):
    logger.info('Warning: Not Implemented')
    logger.info('Probably nothing to do here')


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    testable_list = [
    ]
    ut.doctest_funcs(testable_list)
