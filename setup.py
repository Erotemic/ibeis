#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
import six
from utool import util_setup
import setuptools


setman = util_setup.SetupManager()


CHMOD_PATTERNS = [
    'run_tests.sh',
    'test_*.py',
    'ingest_*.py',
]

# python -m utool.util_dev --exec-get_submodules_from_dpath --only_packages
PROJECT_DIRS = ['.', 'ibeis', 'ibeis/algo', 'ibeis/control', 'ibeis/dbio',
                'ibeis/expt', 'ibeis/gui', 'ibeis/init', 'ibeis/other',
                'ibeis/scripts', 'ibeis/templates', 'ibeis/tests', 'ibeis/viz',
                'ibeis/web', 'ibeis/algo/detect', 'ibeis/algo/hots',
                'ibeis/algo/preproc', 'ibeis/algo/hots/smk',
                'ibeis/viz/interact']


CLUTTER_PATTERNS = [
    '\'',
    '*.dump.txt',
    '*.sqlite3',
    '*.prof',
    '*.prof.txt',
    '*.lprof',
    '*.ln.pkg',
    'failed.txt',
    'failed_doctests.txt',
    'failed_shelltests.txt',
    'test_pyflann_index.flann',
    'test_pyflann_ptsdata.npz',
    '_timeings.txt',
    'timeings.txt',
    'test_times.txt',
    'raw_profile.txt',
    'Tgen.sh',
    'IBEISApp.pkg',
    'tempfile1.txt',
    'tempfile2.txt',
]

CLUTTER_DIRS = [
    'logs/',
    'dist/',
    'ibeis/export',
    'ibeis/ingest',
    'ibeis/injest',
    'ibeis/model',
    'ibeis/io',
    'ibeis/dev',
    'testsuite',
    'testdb_dst',
    '__pycache__/',
    # From pyinstaller
    'vtool',
    'utool',
    'plottool',
    'pyrf',
    'pyhesaff',
    'pyflann',
    'webapps',
    'static',
    'templates',
    'web',
    'qt_menu.nib',
]

INSTALL_REQUIRES = [
    'utool >= 1.0.0.dev1',
    'vtool >= 1.0.0.dev1',
    'pyhesaff >= 1.0.0.dev1',
    'pyrf >= 1.0.0.dev1',
    'guitool >= 1.0.0.dev1',
    'plottool >= 1.0.0.dev1',
    'scipy >= 0.13.2',
    'Pillow >= 2.4.0',
    'psutil',
    'requests >= 0.8.2',
    #'setproctitle >= 1.1.8',
    'scikit-learn >= 0.15.2',
    #'decorator',
    'lockfile >= 0.10.2',
    'apipkg',
    'networkx >= 1.9.1',
    #'objgraph',
    #'pycallgraph',
    #'gevent',
    #'PyQt 4/5 >= 4.9.1', # cannot include because pyqt4 is not in pip
]

NUMPY_VERSION_BUG = False
if NUMPY_VERSION_BUG:
    INSTALL_REQUIRES += [
        'matplotlib',
        'numpy',    # 1.10 has hard time in comparison
    ]

else:
    INSTALL_REQUIRES += [
        'numpy >= 1.9.0',
        'matplotlib >= 1.3.1',
    ]

INSTALL_OPTIONAL = [
    'tornado',
    'flask',
    'flask-cors',
    'pynmea2',
    'pygraphviz',
    'pydot',
    #'https://pypi.python.org/packages/source/p/pyparsing/pyparsing-1.5.7.tar.gz#md5=9be0fcdcc595199c646ab317c1d9a709', # pyparsing
    #http://www.graphviz.org/pub/graphviz/stable/windows/graphviz-2.38.msi
    #pip uninstall pydot
    #pip uninstall pyparsing
    #pip install -Iv https://pypi.python.org/packages/source/p/pyparsing/pyparsing-1.5.7.tar.gz#md5=9be0fcdcc595199c646ab317c1d9a709
    #pip install pydot
    #sudo apt-get  install libgraphviz4 libgraphviz-dev -y
    #sudo apt-get install libgraphviz-dev
    #pip install pygraphviz
    #sudo pip3 install pygraphviz
    #    --install-option="--include-path=/usr/include/graphviz"
    #    --install-option="--library-path=/usr/lib/graphviz/"
    #python -c "import pygraphviz; print(pygraphviz.__file__)"
    #python3 -c "import pygraphviz; print(pygraphviz.__file__)"
]

INSTALL_OPTIONAL_DEV = [
    'ansi2html',
    'pygments',
    'autopep8',
    'pyfiglet',
]

"""
# Uninstall unimportant modules:

    pip uninstall pylru
    pip uninstall sphinx
    pip uninstall pygments
"""

if six.PY2:
    INSTALL_REQUIRES.append('requests >= 0.8.2')

INSTALL_REQUIRES += INSTALL_OPTIONAL


@setman.register_command
def autogen_explicit_imports():
    """
    Excpliticly generated injectable code in order to aid auto complete
    programs like jedi as well as allow for a more transparent stack trace.

    python -m ibeis dev_autogen_explicit_injects
    """
    import ibeis  # NOQA
    from ibeis.control import controller_inject
    controller_inject.dev_autogen_explicit_injects()


if __name__ == '__main__':
    print('[setup] Entering IBEIS setup')
    kwargs = util_setup.setuptools_setup(
        setup_fpath=__file__,
        name='ibeis',
        author='Jon Crall, Jason Parham',
        author_email='erotemic@gmail.com',
        packages=util_setup.find_packages(),
        version=util_setup.parse_package_for_version('ibeis'),
        license=util_setup.read_license('LICENSE'),
        long_description=util_setup.parse_readme('README.md'),
        ext_modules=util_setup.find_ext_modules(),
        project_dirs=PROJECT_DIRS,
        chmod_patterns=CHMOD_PATTERNS,
        clutter_patterns=CLUTTER_PATTERNS,
        clutter_dirs=CLUTTER_DIRS,
        install_requires=INSTALL_REQUIRES,
        scripts=[
            '_scripts/ibeis'
        ],
        #cython_files=CYTHON_FILES,
    )

    kwargs['cmdclass'] = setman.get_cmdclass()

    setuptools.setup(**kwargs)
