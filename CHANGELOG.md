# Changelog

We are currently working on porting this changelog to the specifications in
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## Version 2.5.0 - Unreleased

### Changed

* Dropped Python 3.9 and 3.10 support; the minimum is now Python 3.11.
* The default workdir (when none is configured) is now a per-user data
  directory instead of a CWD-relative path; an existing legacy
  `ibeis_default_workdir` is still respected.
* CI and installer builds install ecosystem dependencies from PyPI; the
  `tpl/` submodules are for local development only.
* `run_developer_setup.sh` reworked: creates/uses `.venv`, installs ibeis
  editable with test deps, and wires the pure-python `tpl/` submodules in
  as editable installs.

### Added

* Windows installer: bundle `.py` sources so runtime source introspection
  works in frozen builds (fixes the Advanced ID interface crash), a frozen
  self-test gate (`IBEIS_FROZEN_SELFTEST=1`), and the installer version is
  now derived from `ibeis.__version__`.
* CI runs the plain pytest suites (previously only doctests ran).

### Fixed

* Hotspotter convert script.
* Issue when querying in a database without any species information
* `safe_pdist` issues with scipy 1.17.0
* Fix np.in1d issue
* Stale inconsistency bookkeeping (`nid_to_errors`) when merging two
  inconsistent PCCs in the graph identification algorithm.
* Compatibility with new dependency releases: networkx (`union_all([])`,
  `selfloop_edges`), scikit-learn >= 1.9 (all-zero sample weights), and
  Python 3.13 minimum pins for pyzmq/simplejson/coverage.
* Windows correctness: `os.devnull` instead of `/dev/null`, path splitting
  on `os.sep`, UTF-8 encoding on the name-change log and smart-patrol XML.


### [Version 2.4.0] - Released 2025-08-24

### Changed
* Support 312, 313, 314

### Added
* Can now dump a simplified version of the database to a kwcoco file

### Fixed
* Fix linkrot issues.
* Fix numpy 2.x issues with np.unique

### [Version 2.3.2] - Released 2024-02-01

### Fixed:
* Removed codecov from test requirements
* Fixed pandas 2.0 issue.
* Fixed ubelt.Cacher issue.
* Minor compatibility tweaks.
* Replaced `utool.grab_test_imgpath` with `kwimage.grab_test_image_fpath` in tests.


## [Version 2.3.1]  - Released 2023-02-06

### Changed
* Ported some utool code to ibeis.util for more direct coupling with this
  library.
* ibeis will no longer prompt you for a workdir if one is not set. It will just use `ibeis_default_workdir` in the current directory. Old behavior can be restored by setting the `LEGACY_WORKDIR_BEHAVIOR` environment variable.

### Fixed
* Fixed issue with numpy 1.24
* Numpy dtype issues
* Fixed 3.11 change with random.Random

### Changed
* We have real passing CI now! WOO!
* Unofficial 3.11 support (should work, but was having issues on CI)
* Added loose / strict dependency versioning


## [Version 2.2.6]  - Released 2020-July-4

### Fixed
* Fix np.float, np.bool, and np.int issue
* Fixed distutils version issue

## [Version 2.2.5]  - Released 2020-July-4

### Fixed

* Warnings about "is" instead of "==" for integer comparisons in web stuff.
* Update to `dtool_ibeis` 1.0.2, which fixes the issue with dumping CSV tables.


### Changed
* `dump_database_csv` now returns the dump directory. 


## [Version 2.2.4]  - Released 2020 Jan 25

### Fixed
* pypi deps should now be fixed


## [Version 2.1.0]

### Added
    * First semi-usable pip release
