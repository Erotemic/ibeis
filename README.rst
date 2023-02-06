|ReadTheDocs| |Pypi| |Downloads| |Codecov| |GithubActions| 


.. image:: https://i.imgur.com/L0k84xQ.png

This project is a component of the WildMe / WildBook project: See https://github.com/WildbookOrg/

NOTE: This IBEIS software is the result of my (Jon Crall's) PhD work. After I
graduated, the image analysis components of IBEIS and the core HotSpotter
program have been transferred and are now being developed by the WildMe
organization. While this software is maintained and supported, it can only
handle medium scale populations and its it GUI interface can be difficult to
work with. If you have a larger population or the need for simpler and scalable
web interfaces  please reach out to the WildMe project at services@wildme.org
(more info: https://www.wildme.org/#/services/ ). 


IBEIS - Image Analysis 
----------------------

I.B.E.I.S. = Image Based Ecological Information System
------------------------------------------------------

.. image:: http://i.imgur.com/TNCiEBe.png
    :alt: "(Note: the rhino and wildebeest mathces may be dubious. Other species do work well though")


Installation Instructions (updated 2020-Nov-01)
-----------------------------------------------

The IBEIS software is now available on `pypi
<https://pypi.org/project/ibeis/>`_ for Linux systems. This means if you have
`Python installed
<https://xdoctest.readthedocs.io/en/latest/installing_python.html>`_. You can
simply run:


.. code:: bash

    pip install ibeis

to install the software. Then the command to run the GUI is:


.. code:: bash

    ibeis

On Windows / OSX I recommend using a Linux virtual machine. However, if you are
computer savvy it is possible to build all of the requirements on from source.
The only tricky components are installing the packages with binary
dependencies: ``pyhesaff`` and ``vtool_ibeis``. If you have these built then
the rest of the dependencies can be installed from pypi even on OSX / Windows.

NOTE: When using a VM on windows, you may encounter an error:

.. code:: 

    qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in 
    ... even though it was found. This application failed to start because no
    Qt platform plugin could be initialized. Reinstalling the application may
    fix this problem.

    Available platform plugins are: xcb, eglfs, ...

    Core dumped

The reason the issue happens appears to be because the opencv-python package
includes libraries also packaged with PyQt5 and those are conflicting. 

The workaround is to uninstall opencv-python and then install a variant that
does not include extra Qt libs:

.. code:: bash

    pip uninstall opencv-python
    pip install opencv-python-headless

    
Basic Usage (updated 2020-Nov-01)
---------------------------------

After installation running the ``ibeis`` command will open the GUI:


If you have already made a database, it will automatically open the most recently used database.

.. image:: https://i.imgur.com/xXF7w8P.png

If this is the first time you've run the program it will not have a database opened:

.. image:: https://i.imgur.com/Ey9Urcv.png

Select new database, (which will first ask you to select a work directory where all of your databases will live).
Then you will be asked to create a database name. Select one and then create the database in your work directory.


You can drag and drop images into the GUI to add them to the database.  Double
clicking an image lets you add "annotations":


.. image:: https://i.imgur.com/t0LQZot.png

You can also right click one or more images and click "Add annotations from
entire images" if your images are already localized to a single individual.

It important than when you add an annotation, you set its species. You can
right click multiple annotations and click "set annotation species". Change
this to anything other than "____".

Once you have annotations with species, you can click one and press "q" to
query for matches in the database of other annotations:


.. image:: https://i.imgur.com/B0ilafa.png

Right clicking and marking each match as "True" or "False" (or alternatively
selecting a row and pressing "T" or "F") will mark images as the same or
different individuals. Groups marked as the same individual will appear in the
"Tree of Names".

Note there are also batch identification methods in the "ID Encounters" "ID
Exemplars" and "Advanced ID Interface" (my personal recommendation). Play
around with different right-click menus (although note that some of these are
buggy and will crash the program), but the main simple identification
procedures are robust and should not crash.


Program Description
-------------------

IBEIS program for the storage and management of images and derived data for
use in computer vision algorithms. It aims to compute who an animal is, what
species an animal is, and where an animal is with the ultimate goal being to
ask important why biological questions.  This This repo Image Analysis image
analysis module of IBEIS. It is both a python module and standalone program. 

Currently the system is build around and SQLite database, a PyQt4 / PyQt5 GUI,
and matplotlib visualizations. Algorithms employed are: random forest species
detection and localization, hessian-affine keypoint detection, SIFT keypoint
description, LNBNN identification using approximate nearest neighbors.
Algorithms in development are SMK (selective match kernel) for identification
and deep neural networks for detection and localization. 

The core of IBEIS is the IBEISController class. It provides an API into IBEIS
data management and algorithms. The IBEIS API Documentation can be found here:
`http://erotemic.github.io/ibeis`

The IBEIS GUI (graphical user interface) is built on top of the API. 
We are also experimenting with a new web frontend that bypasses the older GUI code.

Self Installing Executables
---------------------------

Unfortunately we have not released self-installing-executables for IBEIS yet. 
We ~plan~ hope to release these "soon". 

However there are old HotSpotter (the software which IBEIS is based on)
binaries available. 

.. These can be downloaded from: `http://cs.rpi.edu/hotspotter/`

Dropbox should still be hosting the download links: 

* Win32 Installer: https://www.dropbox.com/s/5j1xyx2hq1wzqz2/hotspotter-win32-setup.exe?dl=0 

* OSX Installer: https://www.dropbox.com/s/q0vzz3xnjbxhsda/hotspotter_installer_mac.dmg?dl=0

IPFS CIDs for the previous installers are QmSnyetkniriHUwTxvzwhkysPKjUj7udBqq5mpK24VJXVM and QmZ3WknrAaxPZhZebdQWZ45EEKwu1Tr6bkFWJzfPRtENs7.

If you are unfamiliar with IPFS use the following gateway links:

https://ipfs.io/ipfs/QmSnyetkniriHUwTxvzwhkysPKjUj7udBqq5mpK24VJXVM 

https://ipfs.io/ipfs/QmZ3WknrAaxPZhZebdQWZ45EEKwu1Tr6bkFWJzfPRtENs7


Visual Demo
-----------


.. image:: http://i.imgur.com/QWrzf9O.png
   :width: 600
   :alt: Feature Extraction

.. image:: http://i.imgur.com/iMHKEDZ.png
   :width: 600
   :alt: Nearest Neighbors


Match Scoring 
-------------

.. image:: http://imgur.com/Hj43Xxy.png
   :width: 600
   :alt: Match Inspection

Spatial Verification
--------------------

.. image:: http://i.imgur.com/VCz0j9C.jpg
   :width: 600
   :alt: sver


.. code:: bash

    python -m vtool.spatial_verification spatially_verify_kpts --show

Name Scoring
------------

.. image:: http://i.imgur.com/IDUnxu2.jpg
   :width: 600
   :alt: namematch


.. code:: bash

    python -m ibeis.algo.hots.chip_match show_single_namematch --qaid 1 --show

Identification Ranking 
----------------------

.. image:: http://i.imgur.com/BlajchI.jpg
   :width: 600
   :alt: rankedmatches


.. code:: bash

    python -m ibeis.algo.hots.chip_match show_ranked_matches --show --qaid 86

Inference
---------

.. image:: http://i.imgur.com/RYeeENl.jpg
   :width: 600
   :alt: encgraph


.. code:: bash

    # broken
    # python -m ibeis.algo.preproc.preproc_encounter compute_encounter_groups --show

Internal Modules
----------------

In the interest of modular code we are actively developing several different modules. 

+-----------------------------------------------------------------+--------------------------------+
| `ibeis <https://github.com/Erotemic/ibeis>`_                    | |ibeisGithubActions|           |
+-----------------------------------------------------------------+--------------------------------+
| `utool <https://github.com/Erotemic/utool>`_                    | |utoolGithubActions|           |
+-----------------------------------------------------------------+--------------------------------+
| `plottool_ibeis <https://github.com/Erotemic/plottool_ibeis>`_  | |plottool_ibeisGithubActions|  |
+-----------------------------------------------------------------+--------------------------------+
| `guitool_ibeis <https://github.com/Erotemic/guitool_ibeis>`_    | |guitool_ibeisGithubActions|   |
+-----------------------------------------------------------------+--------------------------------+
| `dtool_ibeis <https://github.com/Erotemic/dtool_ibeis>`_        | |dtool_ibeisGithubActions|     |
+-----------------------------------------------------------------+--------------------------------+
| `pyhesaff <https://github.com/Erotemic/pyhesaff>`_              | |pyhesaffGithubActions|        |
+-----------------------------------------------------------------+--------------------------------+
| `pyflann_ibeis <https://github.com/Erotemic/pyflann_ibeis>`_    | |pyflann_ibeisGithubActions|   |
+-----------------------------------------------------------------+--------------------------------+
| `vtool_ibeis <https://github.com/Erotemic/vtool_ibeis>`_        | |vtool_ibeis_extGithubActions| |
+-----------------------------------------------------------------+--------------------------------+
| `futures_actors <https://github.com/Erotemic/futures_actors>`_  |  ---                           |
+-----------------------------------------------------------------+--------------------------------+

.. |ibeisGithubActions| image:: https://github.com/Erotemic/ibeis/actions/workflows/tests.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/ibeis/actions?query=branch%3Amain
.. |utoolGithubActions| image:: https://github.com/Erotemic/utool/actions/workflows/tests.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/utool/actions?query=branch%3Amain
.. |vtool_ibeisGithubActions| image:: https://github.com/Erotemic/vtool_ibeis/actions/workflows/tests.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/vtool_ibeis/actions?query=branch%3Amain
.. |dtool_ibeisGithubActions| image:: https://github.com/Erotemic/dtool_ibeis/actions/workflows/tests.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/dtool_ibeis/actions?query=branch%3Amain
.. |plottool_ibeisGithubActions| image:: https://github.com/Erotemic/plottool_ibeis/actions/workflows/tests.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/plottool_ibeis/actions?query=branch%3Amain
.. |guitool_ibeisGithubActions| image:: https://github.com/Erotemic/guitool_ibeis/actions/workflows/tests.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/guitool_ibeis/actions?query=branch%3Amain
.. |pyhesaffGithubActions| image:: https://github.com/Erotemic/pyhesaff/actions/workflows/tests.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/pyhesaff/actions?query=branch%3Amain
.. |pyflann_ibeisGithubActions| image:: https://github.com/Erotemic/pyflann_ibeis/actions/workflows/test_binaries.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/pyflann_ibeis/actions?query=branch%3Amain
.. |vtool_ibeis_extGithubActions| image:: https://github.com/Erotemic/vtool_ibeis_ext/actions/workflows/tests.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/vtool_ibeis_ext/actions?query=branch%3Amain


bluemellophone's IBEIS Image Analysis modules

* https://github.com/WildbookOrg/detecttools
* https://github.com/WildbookOrg/pyrf
  docs: http://bluemellophone.github.io/pyrf


Building from source
--------------------

To build from source you need to be able to build the following 3 projects with
binary dependences. These depened on having a development version of OpenCV and
LZ4.

* https://github.com/Erotemic/vtool_ibeis_ext

* https://github.com/Erotemic/pyflann_ibeis

* https://github.com/Erotemic/pyhesaff

If you are on Linux simply using the wheels for the above projects (
i.e. ``pip install vtool_ibeis_ext  pyflann_ibeis pyhesaff`` is recommended).
On OSX and Win32 these need to be build manually (any contributions to help
these build win32 or osx wheels on their respective project CI would be
amazing!).

The rest of the dependency repos (``guitool_ibeis``, ``plottool_ibeis``,
``dtool_ibeis``, ``vtool_ibeis``,)  are pure python and can be installed in
development mode with the normal clone the repo, and run ``pip install -e .``
inside the repo process.

Given a Python environment where each of the dependency modules is installed
this repo can be installed with ``pip install -e .`` as well. 


Running Tests
-------------

If you have a source install of the dataset you can run tests. But first you
must ensure you have test (~400MB) data downloaded and available. This can be
done via:

.. code:: python

   python dev/reset_dbs.py

Which will ensure that the test datasets are downloaded and in a clean state.
If you don't have a "workdir" set, it will ask you for one. A workdir is where
IBEIS will store your databases by default. Also note that it downloads the
data from an IPFS gateway, which may be slow and require several attempts
before it works.

Once you have the test data you can use the ``run_doctests.sh`` or
``run_tests.py`` script to execute the system tests.

Caveats / Things we are not currently doing
-------------------------------------------

* We do not add or remove points from kdtrees. They are always rebuilt

.. |CircleCI| image:: https://circleci.com/gh/Erotemic/ibeis.svg?style=svg
    :target: https://circleci.com/gh/Erotemic/ibeis
.. |Travis| image:: https://img.shields.io/travis/Erotemic/ibeis/master.svg?label=Travis%20CI
   :target: https://travis-ci.org/Erotemic/ibeis?branch=master
.. |Appveyor| image:: https://ci.appveyor.com/api/projects/status/github/Erotemic/ibeis?branch=master&svg=True
   :target: https://ci.appveyor.com/project/Erotemic/ibeis/branch/master
.. |Codecov| image:: https://codecov.io/github/Erotemic/ibeis/badge.svg?branch=master&service=github
   :target: https://codecov.io/github/Erotemic/ibeis?branch=master
.. |Pypi| image:: https://img.shields.io/pypi/v/ibeis.svg
   :target: https://pypi.python.org/pypi/ibeis
.. |Downloads| image:: https://img.shields.io/pypi/dm/ibeis.svg
   :target: https://pypistats.org/packages/ibeis
.. |ReadTheDocs| image:: https://readthedocs.org/projects/ibeis/badge/?version=latest
    :target: http://ibeis.readthedocs.io/en/latest/
.. |GithubActions| image:: https://github.com/Erotemic/ibeis/actions/workflows/tests.yml/badge.svg?branch=main
    :target: https://github.com/Erotemic/ibeis/actions?query=branch%3Amain
