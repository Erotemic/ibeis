"""Explicit, isolated database fixtures for IBEIS tests.

The fixture database is deliberately tiny.  It is constructed once for each
IBEIS schema / fixture revision, cached outside the repository, and then copied
for every test that needs writable state.  Tests therefore get a real IBEIS
database without sharing mutations with another test.

Usage is intentionally explicit::

    from ibeis.tests.fixtures import IBEISControllerFixture

    with IBEISControllerFixture() as ibs:
        ...

There is no doctest namespace injection and no pytest fixture magic here.  A
doctest opts into mutable state by constructing this class directly.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path


_FIXTURE_REVISION = 1
_READY_FNAME = '_ibeis_test_fixture_ready.txt'
_SEED_IMAGE_NAMES = (
    'fixture-a.ppm',
    'fixture-b.ppm',
    'fixture-c.ppm',
)


def _safe_component(text):
    return re.sub(r'[^A-Za-z0-9_.-]+', '-', str(text))


def _fixture_seed_key():
    from ibeis.control import DB_SCHEMA_CURRENT
    from ibeis.control import STAGING_SCHEMA_CURRENT

    core_version = _safe_component(DB_SCHEMA_CURRENT.VERSION_CURRENT)
    staging_version = _safe_component(STAGING_SCHEMA_CURRENT.VERSION_CURRENT)
    return (
        f'fixture-v{_FIXTURE_REVISION}'
        f'-core-{core_version}'
        f'-staging-{staging_version}'
    )


def _fixture_cache_dpath():
    import ubelt as ub

    return Path(ub.Path.appdir('ibeis/test-fixtures').ensuredir())


def _close_controller(ibs):
    """Release database handles owned by a disposable controller."""
    try:
        if getattr(ibs, 'db', None) is not None:
            ibs.disconnect_sqldatabase()
    finally:
        ibs.unregister_controller()


def _write_seed_images(image_dpath):
    """Write three tiny deterministic images without external test data."""
    image_dpath.mkdir(parents=True, exist_ok=True)
    image_paths = []
    for index, name in enumerate(_SEED_IMAGE_NAMES):
        width = 16
        height = 12
        pixels = bytearray()
        for y in range(height):
            for x in range(width):
                pixels.extend((
                    (x * 13 + index * 47) % 256,
                    (y * 17 + index * 71) % 256,
                    ((x + y) * 11 + index * 29) % 256,
                ))
        path = image_dpath / name
        path.write_bytes(f'P6\n{width} {height}\n255\n'.encode() + pixels)
        image_paths.append(path)
    return image_paths


def _build_seed_database(dbdir):
    """Build the small canonical writable-test database at ``dbdir``."""
    import ibeis

    image_paths = _write_seed_images(Path(dbdir).parent / 'seed-inputs')

    previous_wildbook_signal = ibeis.ENABLE_WILDBOOK_SIGNAL
    ibeis.ENABLE_WILDBOOK_SIGNAL = False
    ibs = None
    try:
        ibs = ibeis.opendb(
            dbdir=os.fspath(dbdir),
            allow_newdir=True,
            use_cache=False,
            web=False,
        )
        gid_list = ibs.add_images(
            [os.fspath(path) for path in image_paths],
            auto_localize=True,
        )
        if len(gid_list) != len(image_paths) or any(gid is None for gid in gid_list):
            raise RuntimeError('Failed to populate the IBEIS test fixture images')

        localized_uris = ibs.get_image_uris(gid_list)
        ibs.set_image_uris_original(gid_list, localized_uris, overwrite=True)

        aid_list = ibs.use_images_as_annotations(
            gid_list,
            name_list=['fixture_alpha', 'fixture_alpha', 'fixture_beta'],
            notes_list=['fixture-a', 'fixture-b', 'fixture-c'],
        )
        if len(aid_list) != len(gid_list):
            raise RuntimeError('Failed to populate the IBEIS test fixture annotations')

        ibs.set_image_imagesettext(
            gid_list,
            ['fixture-images'] * len(gid_list),
        )
    finally:
        try:
            if ibs is not None:
                _close_controller(ibs)
        finally:
            ibeis.ENABLE_WILDBOOK_SIGNAL = previous_wildbook_signal


def get_testdb_seed_dpath():
    """Return the canonical tiny test database, constructing it only once.

    The directory is immutable by convention.  Callers that need writable
    state should copy it, which :class:`IBEISControllerFixture` does for them.
    """
    cache_dpath = _fixture_cache_dpath()
    seed_dpath = cache_dpath / _fixture_seed_key()
    ready_fpath = seed_dpath / _READY_FNAME
    if ready_fpath.is_file():
        return seed_dpath

    if seed_dpath.exists():
        raise RuntimeError(
            'The cached IBEIS test fixture is incomplete. Remove this path and '
            f'retry: {seed_dpath}'
        )

    build_root = Path(
        tempfile.mkdtemp(prefix=seed_dpath.name + '-build-', dir=cache_dpath)
    )
    build_dbdir = build_root / 'database'
    try:
        _build_seed_database(build_dbdir)
        (build_dbdir / _READY_FNAME).write_text(
            'This directory is the canonical IBEIS test fixture.\n'
            'Tests must clone it before opening it writable.\n'
        )
        try:
            os.rename(build_dbdir, seed_dpath)
        except OSError:
            # Another test process may have built the exact same schema seed
            # while this process was doing so.  Only accept the race winner if
            # it published a complete seed.
            if not ready_fpath.is_file():
                raise
        return seed_dpath
    finally:
        shutil.rmtree(build_root, ignore_errors=True)


class IBEISControllerFixture:
    """Own one writable clone of the canonical tiny IBEIS test database.

    ``__enter__`` returns the IBEIS controller directly.  ``__exit__`` closes
    every database owned by that controller before removing the clone, which is
    important on Windows where an open SQLite file cannot be deleted.
    """

    def __init__(self):
        self.ibs = None
        self.dbdir = None
        self._tempdir = None
        self._used = False

    def __enter__(self):
        if self._used:
            raise RuntimeError('IBEISControllerFixture instances are single-use')
        self._used = True

        import ibeis

        seed_dpath = get_testdb_seed_dpath()
        self._tempdir = tempfile.TemporaryDirectory(prefix='ibeis-testdb-')
        self.dbdir = Path(self._tempdir.name) / 'database'
        shutil.copytree(seed_dpath, self.dbdir)

        previous_wildbook_signal = ibeis.ENABLE_WILDBOOK_SIGNAL
        ibeis.ENABLE_WILDBOOK_SIGNAL = False
        try:
            self.ibs = ibeis.opendb(
                dbdir=os.fspath(self.dbdir),
                allow_newdir=False,
                use_cache=False,
                web=False,
            )
        except Exception:
            self._tempdir.cleanup()
            self._tempdir = None
            self.dbdir = None
            raise
        finally:
            ibeis.ENABLE_WILDBOOK_SIGNAL = previous_wildbook_signal
        return self.ibs

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if self.ibs is not None:
                _close_controller(self.ibs)
                self.ibs = None
        finally:
            if self._tempdir is not None:
                self._tempdir.cleanup()
                self._tempdir = None
        return False
