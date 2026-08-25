"""
This module defines the entry point into the IBEIS system
ibeis.opendb and ibeis.main are the main entry points
"""
import sys
import multiprocessing
import platform
import traceback

from loguru import logger
import utool as ut

QUIET = '--quiet' in sys.argv
NOT_QUIET = not QUIET
USE_GUI = '--gui' in sys.argv or '--nogui' not in sys.argv


def _on_ctrl_c(signal, frame):
    proc_name = multiprocessing.current_process().name
    print('[ibeis.main_module] Caught ctrl+c in %s' % (proc_name,))
    sys.exit(0)
    # try:
    #     _close_parallel()
    # except Exception as ex:
    #     print('Something very bad happened' + repr(ex))
    # finally:
    #     print('[ibeis.main_module] sys.exit(0)')
    #     sys.exit(0)

#-----------------------
# private init functions


def _init_signals():
    import signal
    signal.signal(signal.SIGINT, _on_ctrl_c)


def _reset_signals():
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # reset ctrl+c behavior


_REPORTING_EXCEPTION = False
_NATIVE_FAULT_STREAM = None
_NATIVE_FAULT_FPATH = None
_QT_MESSAGE_HANDLER = None
_QT_PREVIOUS_MESSAGE_HANDLER = None


def _install_native_fault_handler():
    """Persist Python stacks for fatal/native process termination."""
    global _NATIVE_FAULT_STREAM
    global _NATIVE_FAULT_FPATH

    if _NATIVE_FAULT_STREAM is not None:
        return _NATIVE_FAULT_FPATH

    log_fpath = ut.get_current_log_fpath()
    if log_fpath is None:
        return None

    import faulthandler
    import os

    fault_fpath = os.path.splitext(str(log_fpath))[0] + '.fault.log'
    stream = open(fault_fpath, 'a', buffering=1, encoding='utf8')
    try:
        faulthandler.enable(file=stream, all_threads=True)
    except Exception:
        stream.close()
        raise

    _NATIVE_FAULT_STREAM = stream
    _NATIVE_FAULT_FPATH = fault_fpath
    logger.info('native fault log: {!r}', fault_fpath)
    return fault_fpath


def _write_native_diagnostic(text):
    """Write diagnostics without going through Qt or the Loguru GUI sink."""
    line = str(text).rstrip('\n') + '\n'
    stream = _NATIVE_FAULT_STREAM
    if stream is not None:
        try:
            stream.write(line)
            stream.flush()
        except Exception:
            pass

    stderr = getattr(sys, '__stderr__', None)
    if stderr is not None:
        try:
            stderr.write(line)
            stderr.flush()
        except Exception:
            pass


def _install_qt_message_handler():
    """Mirror Qt warnings/fatals into the persistent native fault log."""
    global _QT_MESSAGE_HANDLER
    global _QT_PREVIOUS_MESSAGE_HANDLER

    if _QT_MESSAGE_HANDLER is not None or _NATIVE_FAULT_STREAM is None:
        return

    from guitool_ibeis.__PYQT__ import QtCore

    def qt_message_handler(msg_type, context, message):
        category = getattr(context, 'category', None)
        file_ = getattr(context, 'file', None)
        line = getattr(context, 'line', None)
        location = ''
        if file_:
            location = ' {}:{}'.format(file_, line)
        prefix = '[Qt {}{}]'.format(msg_type, location)
        if category:
            prefix += '[{}]'.format(category)
        _write_native_diagnostic('{} {}'.format(prefix, message))
        previous = _QT_PREVIOUS_MESSAGE_HANDLER
        if previous is not None:
            try:
                previous(msg_type, context, message)
            except Exception:
                pass

    _QT_MESSAGE_HANDLER = qt_message_handler
    _QT_PREVIOUS_MESSAGE_HANDLER = QtCore.qInstallMessageHandler(qt_message_handler)


def _format_exception_report(exc_type, exc_value, tb):
    """Build the text a user can copy into a bug report."""
    import ibeis

    log_fpath = ut.get_current_log_fpath()
    traceback_text = ''.join(traceback.format_exception(exc_type, exc_value, tb))
    lines = [
        'IBEIS unexpected error report',
        'IBEIS version: {}'.format(ibeis.__version__),
        'Python: {}'.format(sys.version.replace('\n', ' ')),
        'Platform: {}'.format(platform.platform()),
        'Log file: {}'.format(log_fpath if log_fpath is not None else '<none>'),
        'Native fault log: {}'.format(
            _NATIVE_FAULT_FPATH if _NATIVE_FAULT_FPATH is not None else '<none>'),
        '',
        traceback_text.rstrip(),
    ]
    return '\n'.join(lines)


def _show_exception_dialog(exc_text, report):
    """Show a nonfatal error report when a Qt application is available."""
    if not USE_GUI:
        return
    try:
        import guitool_ibeis as gt
        from guitool_ibeis.__PYQT__ import QtCore

        qapp = gt.get_qtapp()
        if qapp is None or QtCore.QThread.currentThread() != qapp.thread():
            return
        log_fpath = ut.get_current_log_fpath()
        log_note = ''
        if log_fpath is not None:
            log_note = '\n\nThe full traceback was also written to:\n{}'.format(log_fpath)
        msg = (
            'The current action failed. IBEIS kept the application open.\n'
            'If anything looks inconsistent, restart IBEIS before continuing.\n\n'
            'Error: {}\n\n'
            'Click "Show Details..." and copy the report when requesting support.'
            '{}'
        ).format(exc_text, log_note)
        gt.msgbox(title='IBEIS Error', msg=msg, detailed_msg=report)
    except Exception:
        # Do not recurse if Qt itself is involved in the failure.
        logger.exception('Failed to show the IBEIS error dialog')


def _queue_exception_dialog(exc_type, exc_value, report):
    """Show the dialog only after the current Qt event has unwound."""
    if not USE_GUI:
        return
    try:
        import guitool_ibeis as gt
        from guitool_ibeis.__PYQT__ import QtCore

        qapp = gt.get_qtapp()
        if qapp is None or QtCore.QThread.currentThread() != qapp.thread():
            return
        exc_text = '{}: {}'.format(exc_type.__name__, exc_value)
        QtCore.QTimer.singleShot(
            0, lambda text=exc_text, detail=report: _show_exception_dialog(text, detail)
        )
    except Exception:
        logger.exception('Failed to queue the IBEIS error dialog')


def _ibeis_excepthook(exc_type, exc_value, tb):
    """Log an uncaught exception and present a copyable GUI report."""
    global _REPORTING_EXCEPTION
    if _REPORTING_EXCEPTION:
        sys.__excepthook__(exc_type, exc_value, tb)
        return

    _REPORTING_EXCEPTION = True
    try:
        report = _format_exception_report(exc_type, exc_value, tb)
        logger.opt(exception=(exc_type, exc_value, tb)).critical('Unhandled exception')
        _queue_exception_dialog(exc_type, exc_value, report)
    except Exception:
        # Exception reporting must never hide the original failure.
        sys.__excepthook__(exc_type, exc_value, tb)
    finally:
        _REPORTING_EXCEPTION = False


def _install_exception_hook():
    """Ensure Qt callbacks and normal Python failures share one report path."""
    sys.excepthook = _ibeis_excepthook


def _parse_args():
    from ibeis import params
    params.parse_args()


def _init_matplotlib():
    from plottool_ibeis import __MPL_INIT__
    __MPL_INIT__.init_matplotlib()


def _init_gui(activate=True):
    import guitool_ibeis
    if NOT_QUIET:
        print('[main] _init_gui()')
    guitool_ibeis.ensure_qtapp()
    _install_qt_message_handler()
    #USE_OLD_BACKEND = '--old-backend' in sys.argv
    #if USE_OLD_BACKEND:
    from ibeis.gui import guiback
    back = guiback.MainWindowBackend()
    #else:
    #    from ibeis.gui import newgui
    #    back = newgui.IBEISGuiWidget()
    if activate:
        guitool_ibeis.activate_qwindow(back.mainwin)
    return back


def _init_ibeis(dbdir=None, verbose=None, use_cache=True, web=None,
                make_backups=True, **kwargs):
    """
    Private function that calls code to create an ibeis controller
    """
    import utool as ut
    from ibeis import params
    from ibeis.control import IBEISControl
    if verbose is None:
        verbose = ut.VERBOSE
    if verbose and NOT_QUIET:
        print('[main] _init_ibeis()')
    # Use command line dbdir unless user specifies it
    if dbdir is None:
        ibs = None
        print('[main!] WARNING: args.dbdir is None')
    else:
        kwargs = kwargs.copy()
        request_dbversion = kwargs.pop('request_dbversion', None)
        force_serial = kwargs.get('force_serial', None)
        ibs = IBEISControl.request_IBEISController(
            dbdir=dbdir, use_cache=use_cache,
            request_dbversion=request_dbversion,
            force_serial=force_serial, make_backups=make_backups)
        if web is None:
            web = ut.get_argflag(('--webapp', '--webapi', '--web', '--browser'),
                                 help_='automatically launch the web app / web api')
            #web = params.args.webapp
        if web:
            from ibeis.web import app
            port = params.args.webport
            app.start_from_ibeis(ibs, port=port, **kwargs)
    return ibs


def _init_parallel():
    import utool as ut
    if ut.VERBOSE:
        print('_init_parallel')
    from utool import util_parallel
    from ibeis import params
    # Import any modules which parallel process will use here
    # so they are accessable when the program forks
    #from utool import util_sysreq
    #util_sysreq.ensure_in_pythonpath('hesaff')
    #util_sysreq.ensure_in_pythonpath('pyrf')
    #util_sysreq.ensure_in_pythonpath('code')
    #import pyhesaff  # NOQA
    #import pyrf  # NOQA
    from ibeis import core_annots  # NOQA
    #.algo.preproc import preproc_chip  # NOQA
    util_parallel.set_num_procs(params.args.num_procs)
    #if PREINIT_MULTIPROCESSING_POOLS:
    #    util_parallel.init_pool(params.args.num_procs)


# def _close_parallel():
#     #if ut.VERBOSE:
#     #    print('_close_parallel')
#     try:
#         from utool import util_parallel
#         util_parallel.close_pool(terminate=True)
#     except Exception as ex:
#         import utool as ut
#         ut.printex(ex, 'error closing parallel')
#         raise


def _init_numpy():
    import utool as ut
    import numpy as np
    if ut.VERBOSE:
        print('_init_numpy')
    error_options = ['ignore', 'warn', 'raise', 'call', 'print', 'log']
    on_err = error_options[0]
    #np.seterr(divide='ignore', invalid='ignore')
    numpy_err = {
        'divide':  on_err,
        'over':    on_err,
        'under':   on_err,
        'invalid': on_err,
    }
    np.seterr(**numpy_err)


#-----------------------
# private loop functions


def _guitool_loop(main_locals, ipy=False):
    import guitool_ibeis
    from ibeis import params
    print('[main] guitool_ibeis loop')
    back = main_locals.get('back', None)
    if back is not None:
        loop_freq = params.args.loop_freq
        ipy = ipy or params.args.cmd
        guitool_ibeis.qtapp_loop(qwin=back.mainwin, ipy=ipy, frequency=loop_freq, init_signals=False)
        if ipy:  # If we're in IPython, the qtapp loop won't block, so we need to refresh
            back.refresh_state()
    else:
        if NOT_QUIET:
            print('WARNING: back was not expected to be None')


def set_newfile_permissions():
    r"""
    sets this processes default permission bits when creating new files

    CommandLine:
        python -m ibeis.main_module set_newfile_permissions

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.main_module import *  # NOQA
        >>> import os
        >>> import shutil
        >>> import tempfile
        >>> import ubelt as ub
        >>> dpath = tempfile.mkdtemp()
        >>> fpath1 = os.path.join(dpath, 'tempfile1.txt')
        >>> fpath2 = os.path.join(dpath, 'tempfile2.txt')
        >>> # write before umask
        >>> _ = ub.Path(fpath1).write_text('foo')
        >>> stat_result1 = os.stat(fpath1)
        >>> # apply umask
        >>> prev_mask = set_newfile_permissions()
        >>> _ = ub.Path(fpath2).write_text('foo')
        >>> stat_result2 = os.stat(fpath2)
        >>> # verify results
        >>> print('old masked all bits = %o' % (stat_result1.st_mode))
        >>> print('new masked all bits = %o' % (stat_result2.st_mode))
        >>> # restore process state and cleanup
        >>> _ = os.umask(prev_mask)
        >>> shutil.rmtree(dpath)
    """
    import os
    #import stat
    # Set umask so all files written will be group read and writable
    # To get the permissions we want subtract what you want from 0o0666 because
    # umask subtracts the mask you give it.
    #mask = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH
    #mask = 0o000  # most permissive umask
    mask = 0o000  # most permissive umask
    prev_mask = os.umask(mask)
    return prev_mask


def main(gui=True, dbdir=None, defaultdb='cache',
         allow_newdir=False, db=None,
         delete_ibsdir=False,
         **kwargs):
    """
    Program entry point
    Inits the system environment, an IBEISControl, and a GUI if requested

    Args:
        gui (bool): (default=True) If gui is False a gui instance will not be created
        dbdir (None): full directory of a database to load
        db (None): name of database to load relative to the workdir
        allow_newdir (bool): (default=False) if False an error is raised if a
            a new database is created
        defaultdb (str): codename of database to load if db and dbdir is None. a value
            of 'cache' will open the last database opened with the GUI.

    Returns:
        dict: main_locals
    """
    set_newfile_permissions()
    from ibeis.init import main_commands
    from ibeis.init import sysres
    # Display a visible intro message
    msg = '''
    _____ ______  _______ _____ _______
      |   |_____] |______   |   |______
    __|__ |_____] |______ __|__ ______|
    '''
    if NOT_QUIET:
        print(msg)
    # Init the only two main system api handles
    ibs = None
    back = None
    if NOT_QUIET:
        print('[main] ibeis.main_module.main()')
    _preload()
    DIAGNOSTICS = NOT_QUIET
    if DIAGNOSTICS:
        import os
        import utool as ut
        import ibeis
        print('[main] MAIN DIAGNOSTICS')
        print('[main]  * username = %r' % (ut.get_user_name()))
        print('[main]  * ibeis.__version__ = %r' % (ibeis.__version__,))
        print('[main]  * computername = %r' % (ut.get_computer_name()))
        print('[main]  * cwd = %r' % (os.getcwd(),))
        print('[main]  * sys.argv = %r' % (sys.argv,))
    # Parse directory to be loaded from command line args and explicit kwargs.
    # ``--no-database`` is a GUI startup mode: it suppresses the cached
    # default while still constructing the normal main window.
    from ibeis import params
    no_database = bool(params.args.no_database)
    if no_database:
        explicit_db = any([dbdir is not None, db is not None,
                           params.args.dbdir is not None, params.args.db is not None])
        if explicit_db:
            raise ValueError('--no-database cannot be combined with --db or --dbdir')
        if delete_ibsdir:
            raise ValueError('--no-database cannot be combined with delete_ibsdir')
        dbdir = None
    else:
        if defaultdb in ['testdb1', 'testdb0']:
            from ibeis.tests.reset_testdbs import ensure_smaller_testingdbs
            ensure_smaller_testingdbs()
        dbdir = sysres.get_args_dbdir(defaultdb=defaultdb,
                                      allow_newdir=allow_newdir, db=db,
                                      dbdir=dbdir)
    if delete_ibsdir is True:
        from ibeis.other import ibsfuncs
        assert allow_newdir, 'must be making new directory if you are deleting everything!'
        ibsfuncs.delete_ibeis_database(dbdir)

    #limit = sys.getrecursionlimit()
    #if limit == 1000:
    #    print('Setting Recursion Limit to 3000')
    #    sys.setrecursionlimit(3000)
    # Execute preload commands
    main_commands.preload_commands(dbdir, **kwargs)  # PRELOAD CMDS
    try:
        # Build IBEIS Control object
        ibs = _init_ibeis(dbdir)
        if gui and USE_GUI:
            back = _init_gui(activate=kwargs.get('activate', True))
            back.connect_ibeis_control(ibs)
    except Exception as ex:
        print('[main()] IBEIS LOAD encountered exception: %s %s' % (type(ex), ex))
        raise
    if ibs is not None:
        main_commands.postload_commands(ibs, back)  # POSTLOAD CMDS
    main_locals = {'ibs': ibs, 'back': back}
    return main_locals


def opendb_in_background(*args, **kwargs):
    """
    Starts a web server in the background
    """
    import utool as ut
    import time
    sec = kwargs.pop('wait', 0)
    if sec != 0:
        raise AssertionError('wait is depricated')
        print('waiting %s seconds for startup' % (sec,))
    proc = ut.spawn_background_process(opendb, *args, **kwargs)
    if sec != 0:
        raise AssertionError('wait is depricated')
        time.sleep(sec)  # wait for process to initialize
    return proc


def opendb_bg_web(*args, **kwargs):
    """
    Wrapper around opendb_in_background, returns a nice web_ibs
    object to execute web calls using normal python-like syntax

    Args:
        *args: passed to opendb_in_background
        **kwargs:
            port (int):
            domain (str): if specified assumes server is already running
                somewhere otherwise kwargs is passed to opendb_in_background
            start_job_queue (bool)

    Returns:
        web_ibs - this is a KillableProcess object with special functions

    CommandLine:
        python -m ibeis.main_module opendb_bg_web

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.main_module import *  # NOQA
        >>> args = tuple()
        >>> kwargs = {}
        >>> print('Opening a web_ibs')
        >>> web_ibs = opendb_bg_web()
        >>> print('SUCESS Opened a web_ibs!')
        >>> print(web_ibs)
        >>> print('Now kill the web_ibs')
        >>> web_ibs.terminate2()
    """
    import utool as ut
    from ibeis.web import appfuncs
    domain = kwargs.pop('domain', ut.get_argval('--domain', type_=str, default=None))
    port = kwargs.pop('port', appfuncs.DEFAULT_WEB_API_PORT)

    if 'wait' in kwargs:
        print('NOTE: No need to specify wait param anymore. '
              'This is automatically taken care of.')

    if domain is None:
        # Requesting a local test server
        _kw = dict(web=True, browser=False)
        _kw.update(kwargs)
        web_ibs = opendb_in_background(*args, **_kw)
    else:
        # Using a remote controller, no need to spin up anything
        web_ibs = ut.DynStruct()
        web_ibs.terminate2 = lambda: None
    # Augment web instance with usefull test functions
    if domain is None:
        domain = 'http://127.0.1.1'
    if not domain.startswith('http://'):
        domain = 'http://' + domain
    baseurl = domain  + ':' + str(port)

    web_ibs.domain = domain
    web_ibs.port = port
    web_ibs.baseurl = baseurl

    def get(suffix, **kwargs):
        import requests
        return requests.get(baseurl + suffix)

    def post(suffix, **kwargs):
        import requests
        return requests.post(baseurl + suffix)

    def send_ibeis_request(suffix, type_='post', **kwargs):
        """
        Posts a request to a url suffix
        """
        import requests
        import utool as ut
        if not suffix.endswith('/'):
            raise Exception('YOU PROBABLY WANT A / AT THE END OF YOUR URL')
        payload = ut.map_dict_vals(ut.to_json, kwargs)
        if type_ == 'post':
            resp = requests.post(baseurl + suffix, data=payload)
            json_content = resp._content
        elif type_ == 'get':
            resp = requests.get(baseurl + suffix, data=payload)
            json_content = resp.content
        try:
            content = ut.from_json(json_content)
        except ValueError:
            raise Exception('Expected JSON string but got json_content=%r' % (json_content,))
        else:
            # print('content = %r' % (content,))
            if content['status']['code'] != 200:
                print(content['status']['message'])
                raise Exception(content['status']['message'])
        request_response = content['response']
        return request_response

    def wait_for_results(jobid, timeout=None, delays=[1, 3, 10]):
        """
        Waits for results from an engine
        """
        for _ in ut.delayed_retry_gen(delays):
            print('Waiting for jobid = %s' % (jobid,))
            status_response = web_ibs.send_ibeis_request('/api/engine/job/status/', jobid=jobid)
            if status_response['jobstatus'] == 'completed':
                break
        return status_response

    def read_engine_results(jobid):
        result_response = web_ibs.send_ibeis_request('/api/engine/job/result/', jobid=jobid)
        return result_response

    def send_request_and_wait(suffix, type_='post', timeout=None, **kwargs):
        jobid = web_ibs.send_ibeis_request(suffix, type_=type_, **kwargs)
        status_response = web_ibs.wait_for_results(jobid, timeout)  # NOQA
        result_response = web_ibs.read_engine_results(jobid)
        #>>> cmdict = ut.from_json(result_response['json_result'])[0]
        return result_response

    web_ibs.send_ibeis_request = send_ibeis_request
    web_ibs.wait_for_results = wait_for_results
    web_ibs.read_engine_results = read_engine_results
    web_ibs.send_request_and_wait = send_request_and_wait
    web_ibs.get = get
    web_ibs.post = post

    def wait_until_started():
        """ waits until the web server responds to a request """
        import requests
        for count in ut.delayed_retry_gen([1], timeout=15):
            if True or ut.VERBOSE:
                print('Waiting for server to be up. count=%r' % (count,))
            try:
                web_ibs.send_ibeis_request('/api/test/heartbeat/', type_='get')
                break
            except requests.ConnectionError:
                pass
    wait_until_started()
    return web_ibs


def opendb_fg_web(*args, **kwargs):
    """
    Ignore:
        >>> # xdoctest: +SKIP
        >>> from ibeis.main_module import *  # NOQA
        >>> kwargs = {'db': 'testdb1'}
        >>> args = tuple()
        >>> import ibeis
        >>> ibs = ibeis.opendb_fg_web()
    """
    # Gives you context inside the web app for testing
    kwargs['start_web_loop'] = False
    kwargs['web'] = True
    kwargs['browser'] = False
    ibs = opendb(*args, **kwargs)
    from ibeis.control import controller_inject
    app = controller_inject.get_flask_app()
    ibs.app = app
    return ibs


def opendb(db=None, dbdir=None, defaultdb='cache', allow_newdir=False,
           delete_ibsdir=False, verbose=False, use_cache=True,
           web=None, make_backups=True, **kwargs):
    """
    main without the preload (except for option to delete database before
    opening)

    Args:
        db (str):  database name in your workdir used only if dbdir is None
        dbdir (None): full database path
        defaultdb (str): dbdir search stratagy when db is None and dbdir is
            None
        allow_newdir (bool): (default=True) if True errors when opening a
            nonexisting database
        delete_ibsdir (bool): BE CAREFUL! (default=False) if True deletes the
            entire
        verbose (bool): verbosity flag
        web (bool): starts webserver if True (default=param specification)
        use_cache (bool): if True will try to return a previously loaded
            controller
        make_backups (bool): if False, skip automatic database backups
            while opening the controller

    Returns:
        ibeis.IBEISController: ibs

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.main_module import *  # NOQA
        >>> db = None
        >>> dbdir = None
        >>> defaultdb = 'cache'
        >>> allow_newdir = False
        >>> delete_ibsdir = False
        >>> verbose = False
        >>> use_cache = True
        >>> ibs = opendb(db, dbdir, defaultdb, allow_newdir, delete_ibsdir,
        >>>              verbose, use_cache)
        >>> result = str(ibs)
        >>> print(result)
    """
    from ibeis.init import sysres
    from ibeis.other import ibsfuncs
    dbdir = sysres.get_args_dbdir(defaultdb=defaultdb,
                                  allow_newdir=allow_newdir, db=db,
                                  dbdir=dbdir)
    if delete_ibsdir is True:
        assert allow_newdir, (
            'must be making new directory if you are deleting everything!')
        ibsfuncs.delete_ibeis_database(dbdir)
    ibs = _init_ibeis(
        dbdir, verbose=verbose, use_cache=use_cache, web=web,
        make_backups=make_backups, **kwargs)
    return ibs


def start(*args, **kwargs):
    """ alias for main() """  # + main.__doc__
    return main(*args, **kwargs)


def opendb_test(gui=True, dbdir=None, defaultdb='cache', allow_newdir=False,
                db=None):
    """ alias for main() """  # + main.__doc__
    from ibeis.init import sysres
    _preload()
    dbdir = sysres.get_args_dbdir(defaultdb=defaultdb,
                                  allow_newdir=allow_newdir, db=db,
                                  dbdir=dbdir)
    ibs = _init_ibeis(dbdir)
    return ibs


def _preload(mpl=True, par=True, logging=True):
    """ Sets up python environment """
    import utool as ut
    #from ibeis.init import main_helpers
    from ibeis import params
    if  multiprocessing.current_process().name != 'MainProcess':
        return
    if ut.VERBOSE:
        print('[ibeis] _preload')
    _parse_args()
    # mpl backends
    from ibeis import logging_config
    logging_config.configure_logging(
        enable_file=bool(logging and not params.args.nologging),
        appname='ibeis',
    )
    try:
        _install_native_fault_handler()
    except Exception:
        logger.exception('Failed to enable native fault diagnostics')
    if mpl:
        _init_matplotlib()
    # numpy print settings
    _init_numpy()
    # parallel servent processes
    if par:
        _init_parallel()
    # ctrl+c
    _init_signals()
    # Install traceback reporting before the Qt event loop starts.
    _install_exception_hook()


def main_loop(main_locals, rungui=True, ipy=False, persist=True):
    """
    Runs the qt loop if the GUI was initialized and returns an executable string
    for embedding an IPython terminal if requested.

    If rungui is False the gui will not loop even if back has been created

    the main locals dict must be callsed main_locals in the scope you call this
    function in.

    Args:
        main_locals (dict_):
        rungui      (bool):
        ipy         (bool):
        persist     (bool):

    Returns:
        str: execstr
    """
    print('[main] ibeis.main_module.main_loop()')
    from ibeis import params
    import utool as ut
    #print('current process = %r' % (multiprocessing.current_process().name,))
    #== 'MainProcess':
    if rungui and not params.args.nogui:
        try:
            _guitool_loop(main_locals, ipy=ipy)
        except Exception as ex:
            ut.printex(ex, 'error in main_loop')
            raise
    #if not persist or params.args.cmd:
    #    main_close()
    # Put locals in the exec namespace
    ipycmd_execstr = ut.ipython_execstr()
    locals_execstr = ut.execstr_dict(main_locals, 'main_locals')
    execstr = locals_execstr + '\n' + ipycmd_execstr
    return execstr


def main_close(main_locals=None):
    #import utool as ut
    #if ut.VERBOSE:
    #    print('main_close')
    # _close_parallel()
    _reset_signals()


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.main_module
        python -m ibeis.main_module --allexamples
        python -m ibeis.main_module --allexamples --noface --nosrc
    """
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
