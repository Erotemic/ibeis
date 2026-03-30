import numpy as np


def in1d_port(arr1, arr2, assume_unique=False, invert=False):
    """
    Compatibility wrapper for NumPy's legacy `np.in1d`.

    Matches:
        np.in1d(arr1, arr2, assume_unique=..., invert=...)

    Returns a 1D boolean array of length arr1.size (raveled semantics).
    Falls back to an equivalent implementation using np.isin if np.in1d
    is unavailable.

    Example:
        >>> import ubelt as ub
        >>> from ibeis.util import util_compat
        >>> result = util_compat.in1d_port([1, 2], [1, 3, 4])
        >>> print(f'result = {ub.urepr(result, nl=1)}')
        result = np.array([ True, False]...)
    """
    try:
        return np.in1d(arr1, arr2, assume_unique=assume_unique, invert=invert)
    except AttributeError:
        a = np.asarray(arr1)
        # np.isin preserves shape by default; force legacy 1D output semantics
        return np.isin(a.ravel(), arr2, assume_unique=assume_unique, invert=invert)
