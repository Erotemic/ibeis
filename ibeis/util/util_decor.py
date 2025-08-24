"""
import liberator
import utool as ut
lib = liberator.Liberator()
lib.add_dynamic(ut.accepts_numpy)
lib.add_dynamic(ut.accepts_scalar_input)
lib.add_dynamic(ut.accepts_scalar_input2)
lib.add_dynamic(ut.accepts_scalar_input_vector_output)
lib.add_dynamic(ut.ignores_exc_tb)
lib.close(['utool'])
print(lib.current_sourcecode())
"""
import numpy as np
import functools
import inspect
import os
import six
import textwrap
from utool import util_arg
from utool import util_iter
import sys
from utool._internal import meta_util_six
from utool import util_dbg


def ignores_exc_tb(*args, **kwargs):
    """
    PYTHON 3 VERSION

    ignore_exc_tb decorates a function and remove both itself
    and the function from any exception traceback that occurs.

    This is useful to decorate other trivial decorators
    which are polluting your stacktrace.

    if IGNORE_TRACEBACK is False then this decorator does nothing
    (and it should do nothing in production code!)

    References:
        https://github.com/jcrocholl/pep8/issues/34  # NOQA
        http://legacy.python.org/dev/peps/pep-3109/
    """
    outer_wrapper = kwargs.get('outer_wrapper', True)
    def ignores_exc_tb_closure(func):
        # HACK JUST TURN THIS OFF
        return func

        if not IGNORE_TRACEBACK:
            # if the global enforces that we should not ignore anytracebacks
            # then just return the original function without any modifcation
            return func
        #@wraps(func)
        def wrp_noexectb(*args, **kwargs):
            try:
                #import utool
                #if utool.DEBUG:
                #    print('[IN IGNORETB] args=%r' % (args,))
                #    print('[IN IGNORETB] kwargs=%r' % (kwargs,))
                return func(*args, **kwargs)
            except Exception:
                # PYTHON 3.3 NEW METHODS
                exc_type, exc_value, exc_traceback = sys.exc_info()
                # Code to remove this decorator from traceback
                # Remove two levels to remove this one as well
                exc_type, exc_value, exc_traceback = sys.exc_info()
                try:
                    exc_traceback = exc_traceback.tb_next
                    exc_traceback = exc_traceback.tb_next
                except Exception:
                    pass
                ex = exc_type(exc_value)
                ex.__traceback__ = exc_traceback
                raise ex
        if outer_wrapper:
            wrp_noexectb = preserve_sig(wrp_noexectb, func)
        return wrp_noexectb
    if len(args) == 1:
        # called with one arg means its a function call
        func = args[0]
        return ignores_exc_tb_closure(func)
    else:
        # called with no args means kwargs as specified
        return ignores_exc_tb_closure


def accepts_scalar_input_vector_output(func):
    """
    DEPRICATE IN FAVOR OF accepts_scalar_input2

    accepts_scalar_input_vector_output

    Notes:
        Input:                           Excpeted Output 1to1   Expected Output 1toM
            scalar         : 1           x                      [X]
            n element list : [1, 2, 3]   [x, y, z]              [[X], [Y], [Z]]
            1 element list : [1]         [x]                    [[X]]
            0 element list : []          []                     []
        There seems to be no real issue here, I be the thing that tripped me up
        was when using sql and getting multiple columns that returned the
        values inside of the N-tuple whereas when you get one column you get
        one element inside of a 1-tuple, no that still makes sense.  There was
        something where when you couln't unpack it becuase it was already
        empty...
    """
    @ignores_exc_tb(outer_wrapper=False)
    #@wraps(func)
    def wrp_asivo(self, input_, *args, **kwargs):
        #import utool
        #if utool.DEBUG:
        #    print('[IN SIVO] args=%r' % (args,))
        #    print('[IN SIVO] kwargs=%r' % (kwargs,))
        if util_iter.isiterable(input_):
            # If input is already iterable do default behavior
            return func(self, input_, *args, **kwargs)
        else:
            # If input is scalar, wrap input, execute, and unpack result
            result = func(self, (input_,), *args, **kwargs)
            # The output length could be 0 on a scalar input
            if len(result) == 0:
                return []
            else:
                assert len(result) == 1, 'error in asivo'
                return result[0]
    return wrp_asivo


ONEX_REPORT_INPUT = ('--onex-report-input' in sys.argv)


def on_exception_report_input(func_=None, force=False, keys=None):
    """
    If an error is thrown in the scope of this function's stack frame then the
    decorated function name and the arguments passed to it will be printed to
    the utool print function.
    """
    def _closure_onexceptreport(func):
        if not ONEX_REPORT_INPUT and not force:
            return func
        @ignores_exc_tb(outer_wrapper=False)
        #@wraps(func)
        def wrp_onexceptreport(*args, **kwargs):
            try:
                #import utool
                #if utool.DEBUG:
                #    print('[IN EXCPRPT] args=%r' % (args,))
                #    print('[IN EXCPRPT] kwargs=%r' % (kwargs,))
                return func(*args, **kwargs)
            except Exception as ex:
                from utool import util_str
                print('ERROR occured! Reporting input to function')
                if keys is not None:
                    from utool import util_inspect
                    from utool import util_list
                    from utool import util_dict
                    argspec = util_inspect.get_func_argspec(func)
                    in_kwargs_flags = [key in kwargs for key in keys]
                    kwarg_keys = util_list.compress(keys, in_kwargs_flags)
                    kwarg_vals = [kwargs.get(key) for key in kwarg_keys]
                    flags = util_list.not_list(in_kwargs_flags)
                    arg_keys = util_list.compress(keys, flags)
                    arg_idxs = [argspec.args.index(key) for key in arg_keys]
                    num_nodefault = len(argspec.args) - len(argspec.defaults)
                    default_vals = (([None] * (num_nodefault)) +
                                    list(argspec.defaults))
                    args_ = list(args) + default_vals[len(args) + 1:]
                    arg_vals = util_list.take(args_, arg_idxs)
                    requested_dict = dict(util_list.flatten(
                        [zip(kwarg_keys, kwarg_vals), zip(arg_keys, arg_vals)]))
                    print('input dict = ' + util_str.repr4(
                        util_dict.dict_subset(requested_dict, keys)))
                    # (print out specific keys only)
                    pass
                arg_strs = ', '.join([repr(util_str.truncate_str(str(arg)))
                                      for arg in args])
                kwarg_strs = ', '.join([
                    util_str.truncate_str('%s=%r' % (key, val))
                    for key, val in six.iteritems(kwargs)])
                msg = ('\nERROR: funcname=%r,\n * args=%s,\n * kwargs=%r\n' % (
                    meta_util_six.get_funcname(func), arg_strs, kwarg_strs))
                msg += ' * len(args) = %r\n' % len(args)
                msg += ' * len(kwargs) = %r\n' % len(kwargs)
                util_dbg.printex(ex, msg, pad_stdout=True)
                raise
        wrp_onexceptreport = preserve_sig(wrp_onexceptreport, func)
        return wrp_onexceptreport
    if func_ is None:
        return _closure_onexceptreport
    else:
        return _closure_onexceptreport(func_)


def __assert_param_consistency(args, argx_list_):
    """
    debugging function for accepts_scalar_input2
    checks to make sure all the iterable inputs are of the same length
    """
    if util_arg.NO_ASSERTS:
        return
    if len(argx_list_) == 0:
        return True
    argx_flags = [util_iter.isiterable(args[argx]) for argx in argx_list_]
    try:
        assert all([argx_flags[0] == flag for flag in argx_flags]), (
            'invalid mixing of iterable and scalar inputs')
    except AssertionError as ex:
        print('!!! ASSERTION ERROR IN UTIL_DECOR !!!')
        for argx in argx_list_:
            print('[util_decor] args[%d] = %r' % (argx, args[argx]))
        raise ex


def accepts_scalar_input2(argx_list=[0], outer_wrapper=True):
    r"""
    FIXME: change to better name. Complete implementation.

    used in IBEIS setters

    accepts_scalar_input2 is a decorator which expects to be used on class
    methods.  It lets the user pass either a vector or a scalar to a function,
    as long as the function treats everything like a vector. Input and output
    is sanitized to the user expected format on return.

    Args:
        argx_list (list): indexes of args that could be passed in as scalars to
            code that operates on lists. Ensures that decorated function gets
            the argument as an iterable.
    """
    assert isinstance(argx_list, (list, tuple)), (
        'accepts_scalar_input2 must be called with argument positions')

    def closure_asi2(func):
        #@on_exception_report_input
        @ignores_exc_tb(outer_wrapper=False)
        def wrp_asi2(self, *args, **kwargs):
            # Hack in case wrapping a function with varargs
            argx_list_ = [argx for argx in argx_list if argx < len(args)]
            __assert_param_consistency(args, argx_list_)
            if all([util_iter.isiterable(args[ix]) for ix in argx_list_]):
                # If input is already iterable do default behavior
                return func(self, *args, **kwargs)
            else:
                # If input is scalar, wrap input, execute, and unpack result
                args_wrapped = [(arg,) if ix in argx_list_ else arg
                                for ix, arg in enumerate(args)]
                ret = func(self, *args_wrapped, **kwargs)
                if ret is not None:
                    return ret[0]
        if outer_wrapper:
            wrp_asi2 = on_exception_report_input(preserve_sig(wrp_asi2, func))
        return wrp_asi2
    return closure_asi2


IGNORE_TRACEBACK = (not (('--nosmalltb' in sys.argv) or ('--noignoretb' in sys.argv)))


def accepts_scalar_input(func):
    """
    DEPRICATE in favor of accepts_scalar_input2
    only accepts one input as vector

    accepts_scalar_input is a decorator which expects to be used on class
    methods.  It lets the user pass either a vector or a scalar to a function,
    as long as the function treats everything like a vector. Input and output
    is sanitized to the user expected format on return.

    Args:
        func (func):

    Returns:
        func: wrp_asi

    CommandLine:
        python -m utool.util_decor accepts_scalar_input

    Example:
        >>> # ENABLE_DOCTEST
        >>> from utool.util_decor import *  # NOQA
        >>> @accepts_scalar_input
        ... def foobar(self, list_):
        ...     return [x + 1 for x in list_]
        >>> self = None  # dummy self because this decorator is for classes
        >>> assert 2 == foobar(self, 1)
        >>> assert [2, 3] == foobar(self, [1, 2])
    """
    #@on_exception_report_input
    @ignores_exc_tb(outer_wrapper=False)
    #@wraps(func)
    def wrp_asi(self, input_, *args, **kwargs):
        #if HAVE_PANDAS:
        #    if isinstance(input_, (pd.DataFrame, pd.Series)):
        #        input_ = input_.values
        if util_iter.isiterable(input_):
            # If input is already iterable do default behavior
            return func(self, input_, *args, **kwargs)
        else:
            # If input is scalar, wrap input, execute, and unpack result
            #ret = func(self, (input_,), *args, **kwargs)
            ret = func(self, [input_], *args, **kwargs)
            if ret is not None:
                return ret[0]
    wrp_asi = preserve_sig(wrp_asi, func)
    return wrp_asi


SIG_PRESERVE = util_arg.get_argflag('--sigpreserve')


def preserve_sig(wrapper, orig_func, force=False):
    """
    Decorates a wrapper function.

    It seems impossible to presever signatures in python 2 without eval
    (Maybe another option is to write to a temporary module?)

    Args:
        wrapper: the function wrapping orig_func to change the signature of
        orig_func: the original function to take the signature from

    References:
        http://emptysqua.re/blog/copying-a-python-functions-signature/
        https://code.google.com/p/micheles/source/browse/decorator/src/decorator.py

    TODO:
        checkout funcsigs
        https://funcsigs.readthedocs.org/en/latest/

    CommandLine:
        python -m utool.util_decor preserve_sig

    Example:
        >>> # ENABLE_DOCTEST
        >>> import utool as ut
        >>> #ut.rrrr(False)
        >>> def myfunction(self, listinput_, arg1, *args, **kwargs):
        >>>     " just a test function "
        >>>     return [x + 1 for x in listinput_]
        >>> #orig_func = ut.take
        >>> orig_func = myfunction
        >>> wrapper = ut.accepts_scalar_input2([0])(orig_func)
        >>> #_wrp_preserve1 = ut.preserve_sig(wrapper, orig_func, True)
        >>> _wrp_preserve2 = ut.preserve_sig(wrapper, orig_func, False)
        >>> #print('_wrp_preserve2 = %r' % (_wrp_preserve1,))
        >>> print('_wrp_preserve2 = %r' % (_wrp_preserve2,))
    """
    #if True:
    #    import functools
    #    return functools.wraps(orig_func)(wrapper)
    from utool._internal import meta_util_six
    from utool import util_str
    from utool import util_inspect

    if wrapper is orig_func:
        # nothing to do
        return orig_func
    orig_docstr = meta_util_six.get_funcdoc(orig_func)
    orig_docstr = '' if orig_docstr is None else orig_docstr
    orig_argspec = util_inspect.get_func_argspec(orig_func)
    wrap_name = wrapper.__code__.co_name
    orig_name = meta_util_six.get_funcname(orig_func)

    # At the very least preserve info in a dictionary
    _utinfo = {}
    _utinfo['orig_func'] = orig_func
    _utinfo['wrap_name'] = wrap_name
    _utinfo['orig_name'] = orig_name
    _utinfo['orig_argspec'] = orig_argspec

    if hasattr(wrapper, '_utinfo'):
        parent_wrapper_utinfo = wrapper._utinfo
        _utinfo['parent_wrapper_utinfo'] = parent_wrapper_utinfo
    if hasattr(orig_func, '_utinfo'):
        parent_orig_utinfo = orig_func._utinfo
        _utinfo['parent_orig_utinfo'] = parent_orig_utinfo

    # environment variable is set if you are building documentation
    # preserve sig if building docs
    building_docs = os.environ.get('UTOOL_AUTOGEN_SPHINX_RUNNING', 'OFF') == 'ON'

    if force or SIG_PRESERVE or building_docs:
        # PRESERVES ALL SIGNATURES WITH EXECS
        src_fmt = r'''
        def _wrp_preserve{defsig}:
            """ {orig_docstr} """
            try:
                return wrapper{callsig}
            except Exception as ex:
                import utool as ut
                msg = ('Failure in signature preserving wrapper:\n')
                ut.printex(ex, msg)
                raise
        '''
        raise NotImplementedError('broke in 311, but probably unused')
        # Put wrapped function into a scope
        globals_ =  {'wrapper': wrapper}
        locals_ = {}
        # argspec is :ArgSpec(args=['bar', 'baz'], varargs=None, keywords=None,
        # defaults=(True,))
        # get orig functions argspec
        # get functions signature
        # Get function call signature (no defaults)
        # Define an exec function
        argspec = inspect.getargspec(orig_func)
        (args, varargs, varkw, defaults) = argspec
        defsig = inspect.formatargspec(*argspec)
        callsig = inspect.formatargspec(*argspec[0:3])
        # TODO:
        src_fmtdict = dict(defsig=defsig, callsig=callsig, orig_docstr=orig_docstr)
        src = textwrap.dedent(src_fmt).format(**src_fmtdict)
        # Define the new function on the fly
        # (I wish there was a non exec / eval way to do this)
        #print(src)
        code = compile(src, '<string>', 'exec')
        six.exec_(code, globals_, locals_)
        #six.exec_(src, globals_, locals_)
        # Use functools.update_wapper to complete preservation
        _wrp_preserve = functools.update_wrapper(locals_['_wrp_preserve'], orig_func)
        # Keep debug info
        _utinfo['src'] = src
        # Set an internal sig variable that we may use
        #_wrp_preserve.__sig__ = defsig
    else:
        # PRESERVES SOME SIGNATURES NO EXEC
        # signature preservation is turned off. just preserve the name.
        # Does not use any exec or eval statments.
        _wrp_preserve = functools.update_wrapper(wrapper, orig_func)
        # Just do something to preserve signature

    DEBUG_WRAPPED_DOCSTRING = False
    if DEBUG_WRAPPED_DOCSTRING:
        new_docstr_fmtstr = util_str.codeblock(
            '''
            Wrapped function {wrap_name}({orig_name})

            orig_argspec = {orig_argspec}

            orig_docstr = {orig_docstr}
            '''
        )
    else:
        new_docstr_fmtstr = util_str.codeblock(
            '''
            {orig_docstr}
            '''
        )
    new_docstr = new_docstr_fmtstr.format(
        wrap_name=wrap_name, orig_name=orig_name, orig_docstr=orig_docstr,
        orig_argspec=orig_argspec)
    _wrp_preserve.__doc__ = new_docstr
    _wrp_preserve._utinfo = _utinfo
    return _wrp_preserve


def accepts_numpy(func):
    """ Allows the first input to be a numpy array and get result in numpy form """
    #@ignores_exc_tb
    #@wraps(func)
    def wrp_accepts_numpy(self, input_, *args, **kwargs):
        if not isinstance(input_, np.ndarray):
            # If the input is not numpy, just call the function
            return func(self, input_, *args, **kwargs)
        else:
            # TODO: use a variant of util_list.unflat_unique_rowid_map
            # If the input is a numpy array, and return the output with the same
            # shape as the input
            # Remove redundant input (because we are passing it to SQL)
            # HACK: ravel to get the pre numpy 2.x behavior
            input_list, inverse_unique = np.unique(input_.ravel(), return_inverse=True)
            print(f'inverse_unique.shape={inverse_unique.shape}')
            # Call the function in list format
            # TODO: is this necessary?
            input_list = input_list.tolist()
            output_list = func(self, input_list, *args, **kwargs)
            # Put the output back into numpy
            # Reconstruct redundant queries
            try:
                unique_output = np.array(output_list)
            except ValueError:
                # Workaround numpy 1.24 issue
                unique_output = np.array(output_list, dtype=object)
            output_arr = unique_output[inverse_unique]
            output_shape = tuple(list(input_.shape) + list(output_arr.shape[1:]))
            return np.array(output_arr).reshape(output_shape)
    wrp_accepts_numpy = preserve_sig(wrp_accepts_numpy, func)
    return wrp_accepts_numpy
