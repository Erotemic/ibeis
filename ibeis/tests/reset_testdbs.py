#!/usr/bin/env python
"""
downloads standard test datasets. can delete them as well
"""
import utool as ut
from os.path import join
from itertools import cycle

__test__ = False  # This is not a test


def testdb2_stuff():
    """
    This can be removed.

    tar -zcvf testdb2.tar.gz testdb2/
    """
    import ibeis
    ibs = ibeis.opendb('testdb2')

    #ibs.ensure_contributor_rowids()

    gid_list = ibs.get_valid_gids()

    # Group gids by species
    image_species_list = ut.get_list_column(
        ibs.unflat_map(ibs.get_annot_species_rowids, ibs.get_image_aids(gid_list)), 0)

    new_contributor_rowid1 = ibs.add_new_temp_contributor(offset=len(ibs.get_valid_contributor_rowids()))
    new_contributor_rowid2 = ibs.add_new_temp_contributor(offset=len(ibs.get_valid_contributor_rowids()))

    gids1, gids2 = list(ut.group_items(gid_list, image_species_list).values())

    party_rowids = ibs.add_party(['TestCar1', 'TestCar2'])
    partyid1, partyid2 = party_rowids
    ibs.set_image_contributor_rowid(gids1, [new_contributor_rowid1] * len(gids1))
    ibs.set_image_contributor_rowid(gids2, [new_contributor_rowid2] * len(gids2))
    ibs.set_image_party_rowids(gids1, [partyid1] * len(gids1))
    ibs.set_image_party_rowids(gids2, [partyid2] * len(gids2))

    #image_contributor_rowid_list = ibs.get_image_contributor_rowid(gid_list)


def get_testdata_dir(ensure=True, key='testdb1'):
    """
    Gets test img directory and downloads it if it doesn't exist
    """
    from ibeis.tests import demodata2
    # New content addressable data
    fpath = demodata2.DEMODATA.grab(key)
    # testdata_map = {
    #     # TODO: content addressable data
    #     'testdb1': 'https://cthulhu.dyn.wildme.io/public/data/testdata.zip',
    # }
    # zipped_testdata_url = testdata_map[key]
    from ibeis.util import util_grabdata
    testdata_dir = util_grabdata.grab_zipped_url(
        None,
        appname=demodata2.DEMODATA.appname,
        existing_zip_fpath=fpath,
        # zipped_testdata_url,
        # zipped_testdata_url,
        ensure=ensure
    )
    # Hack:
    # if testdata_dir.name == 'testdb1':
    #     testdata_dir.parent / 'testdata'

    return testdata_dir


# Convert stanadardized names to true names
TEST_DBNAMES_MAP = {
    'nauts':         'NAUT_test',
    'mtest':         'PZ_MTEST',
    'testdb0':       'testdb0',
    'testdb1':       'testdb1',
    'testdb2':       'testdb2',
    'testdb_guiall': 'testdb_guiall',
    'wds':           'wd_peter2',
}


def delete_dbdir(dbname):
    from ibeis.init import sysres
    ut.delete(join(sysres.get_workdir(), dbname), ignore_errors=False)


def ensure_smaller_testingdbs():
    """
    Makes the smaller test databases
    """
    from ibeis.init import sysres
    def make_testdb0():
        """ makes testdb0 """
        def get_test_gpaths(ndata=None, names=None, **kwargs):
            # Read ndata from args or command line
            """ DEPRICATE """
            ndata_arg = ut.get_argval('--ndata', type_=int, default=None, help_='use --ndata to specify bigger data')
            if ndata_arg is not None:
                ndata = ndata_arg
            imgdir = get_testdata_dir(**kwargs)
            gpath_list = sorted(list(ut.list_images(imgdir, full=True, recursive=True)))
            # Get only the gpaths of certain names
            if names is not None:
                gpath_list = [gpath for gpath in gpath_list if
                              ut.basename_noext(gpath) in names]
            # Get a some number of test images
            if ndata is not None:
                gpath_cycle = cycle(gpath_list)
                gpath_list  = [next(gpath_cycle) for _ in range(ndata)]
            return gpath_list
        workdir = sysres.get_workdir()
        TESTDB0 = join(workdir, 'testdb0')
        # import ibeis
        from ibeis.main_module import main as ibeis_main
        main_locals = ibeis_main(dbdir=TESTDB0, gui=False, allow_newdir=True)
        ibs = main_locals['ibs']
        assert ibs is not None, str(main_locals)
        gpath_list = list(map(ut.unixpath, get_test_gpaths()))
        #print('[RESET] gpath_list=%r' % gpath_list)
        gid_list = ibs.add_images(gpath_list)  # NOQA
        valid_gids = ibs.get_valid_gids()
        valid_aids = ibs.get_valid_aids()
        try:
            assert len(valid_aids) == 0, 'there are more than 0 annotations in an empty database!'
        except Exception as ex:
            ut.printex(ex, key_list=['valid_aids'])
            raise
        gid_list = valid_gids[0:1]
        bbox_list = [(0, 0, 100, 100)]
        aid = ibs.add_annots(gid_list, bbox_list=bbox_list)[0]
        #print('[RESET] NEW RID=%r' % aid)
        aids = ibs.get_image_aids(gid_list)[0]
        try:
            assert aid in aids, ('bad annotation adder: aid = %r, aids = %r' % (aid, aids))
        except Exception as ex:
            ut.printex(ex, key_list=['aid', 'aids'])
            raise

    get_testdata_dir(True)
    if not ut.checkpath(join(sysres.get_workdir(), 'testdb0'), verbose=True):
        print("\n\nMAKE TESTDB0\n\n")
        make_testdb0()
    if not ut.checkpath(join(sysres.get_workdir(), 'testdb1'), verbose=True):
        print("\n\nMAKE TESTDB1\n\n")
        from ibeis.dbio import ingest_database
        ingest_database.ingest_standard_database('testdb1')


def reset_ci_testdbs():
    """Reset the deterministic databases used by automated tests."""
    import ibeis
    from ibeis.init import sysres
    import ubelt as ub
    ibeis.ENABLE_WILDBOOK_SIGNAL = False
    workdir = ub.Path(sysres.get_workdir()).ensuredir()
    (workdir / 'testdb0').delete()
    (workdir / 'testdb1').delete()
    ensure_smaller_testingdbs()
    ensure_synthetic_match_db(reset=True)


def reset_testdbs(**kwargs):
    # Step 0) Parse Args
    import ibeis
    from ibeis.init import sysres
    ibeis.ENABLE_WILDBOOK_SIGNAL = False
    default_args = {'reset_' + key: False
                    for key in TEST_DBNAMES_MAP.keys()}
    default_args['reset_all'] = False
    default_args.update(kwargs)
    argdict = ut.parse_dict_from_argv(default_args)
    if not any(list(argdict.values())):
        # Default behavior is to reset the small dbs
        argdict['reset_testdb0'] = True
        argdict['reset_testdb1'] = True
        argdict['reset_testdb_guiall'] = True

    # Step 1) Delete DBs to be Reset
    for key, dbname in TEST_DBNAMES_MAP.items():
        if argdict.get('reset_' + key, False) or argdict['reset_all']:
            delete_dbdir(dbname)

    # Synthetic fixtures are the default test data. Historical remote demo
    # datasets are provisioned only when their reset flag is explicitly given.
    ensure_synthetic_db1(reset=True)

    # Step 3) Ensure the ordinary local test databases and the synthetic
    # matching fixture. PZ_MTEST is separate historical/demo data and is only
    # downloaded when its explicit reset flag is requested.
    ensure_smaller_testingdbs()
    ensure_synthetic_match_db(reset=argdict['reset_all'])
    if argdict.get('reset_mtest', False) or argdict['reset_all']:
        sysres.ensure_pz_mtest()

    # Keep remote fixtures available for explicit compatibility / integration
    # testing without putting network access on the default test path.
    if argdict.get('reset_nauts', False) or argdict['reset_all']:
        ibeis.ensure_nauts()
    if argdict.get('reset_testdb2', False) or argdict['reset_all']:
        sysres.ensure_testdb2()
    if argdict.get('reset_wds', False) or argdict['reset_all']:
        ibeis.ensure_wilddogs()

    # Step 4) testdb1 becomes the main database
    workdir = sysres.get_workdir()
    TESTDB1 = join(workdir, 'testdb1')
    sysres.set_default_dbdir(TESTDB1)


def reset_mtest():
    r"""
    CommandLine:
        python -m ibeis --tf reset_mtest

    Example:
        >>> # xdoctest: +SKIP
        >>> from ibeis.tests.reset_testdbs import *  # NOQA
        >>> result = reset_mtest()
    """
    return reset_testdbs(reset_mtest=True)


def generate_synthetic_images(
        raw_img_dpath, image_size=512, images_per_name=4, num_names=10,
        name_sizes=None):
    import ubelt as ub
    if name_sizes is None:
        name_sizes = [images_per_name] * num_names
    else:
        name_sizes = list(name_sizes)
        num_names = len(name_sizes)

    synthetic_items = []
    for name_idx, num_variants in enumerate(name_sizes, start=1):
        creature_name = f'creature_{name_idx:04d}'
        for variant in range(num_variants):
            stem = f"{creature_name}__v{variant:02d}"
            name_dpath = (raw_img_dpath / creature_name)
            image_fpath = name_dpath / f"{stem}.png"
            synthetic_items.append({
                'name_idx': name_idx,
                'creature_name': creature_name,
                'variant': variant,
                'image_fpath': image_fpath,
            })

    depends = {
        'image_size': image_size,
        'name_sizes': tuple(name_sizes),
    }
    imgstamp = ub.CacheStamp('img_stamp', dpath=raw_img_dpath, depends=depends)
    if imgstamp.expired():
        from ibeis.demo import synthetic_creature
        for item in ub.ProgIter(synthetic_items, desc='generating synthetic data'):
            creature_name = item['creature_name']
            variant = item['variant']
            image_fpath = item['image_fpath']
            params = synthetic_creature.random_params(creature_name, variant, image_size)
            img, meta = synthetic_creature.compose_creature(params, debug=False)
            image_fpath.parent.ensuredir()
            img.save(image_fpath)
        imgstamp.renew()
    return synthetic_items



def synthetic_match_spec():
    """Describe the deterministic matching/inference fixture used by tests.

    This fixture deliberately has its own identity.  It is not PZ_MTEST and
    does not attempt to preserve PZ_MTEST rowids or image content.  Instead we
    own the data contract: enough repeated sightings for matching/inference,
    three viewpoints/occurrences, and explicit mother/foal case tags for
    filtering paths that historically used those properties of PZ_MTEST.
    """
    num_names = 40
    images_per_name = 3
    return {
        'dbname': 'synthetic_match',
        'num_names': num_names,
        'images_per_name': images_per_name,
        'num_annots': num_names * images_per_name,
        'image_size': 384,
        'family_pairs': 6,
    }


def _prepare_synthetic_match_db(ibs, synthetic_items, spec):
    """Populate deterministic metadata and graph state for synthetic matching."""
    import ibeis
    import numpy as np
    from ibeis.init import sysres

    aids = ibs.get_valid_aids()
    gids = ibs.get_valid_gids()

    ibs.set_annot_species(aids, [ibeis.const.TEST_SPECIES.ZEB_PLAIN] * len(aids))
    ibs.set_annot_quality_texts(aids, [ibeis.const.QUAL_GOOD] * len(aids))
    view_cycle = ['left', 'front', 'right']
    view_codes = [view_cycle[item['variant'] % len(view_cycle)]
                  for item in synthetic_items]
    ibs.set_annot_viewpoint_code(aids, view_codes)
    ibs.update_annot_semantic_uuids(aids)

    # Each variant represents a repeat sighting at a different occurrence.
    for variant in range(3):
        variant_gids = [gid for gid, item in zip(gids, synthetic_items)
                        if item['variant'] == variant]
        ibs.set_image_imagesettext(
            variant_gids,
            ['Occurrence {}'.format(variant + 1)] * len(variant_gids),
        )

    unixtimes = [1_600_000_000 + (idx * 3600) for idx in range(len(gids))]
    ibs.set_image_unixtime(gids, unixtimes)
    gps = np.array([
        [-1.40 + ((idx % 17) * 0.001), 36.80 + ((idx % 23) * 0.001)]
        for idx in range(len(gids))
    ])
    ibs.set_image_gps(gids, gps)

    # Encode a few explicit family roles.  All sightings of a selected
    # identity carry the same role, so filtering tests can make stable semantic
    # assertions without depending on arbitrary annotation rowids.
    family_pairs = spec['family_pairs']
    mother_name_idxs = set(range(1, 2 * family_pairs + 1, 2))
    foal_name_idxs = set(range(2, 2 * family_pairs + 1, 2))
    mother_aids = [aid for aid, item in zip(aids, synthetic_items)
                   if item['name_idx'] in mother_name_idxs]
    foal_aids = [aid for aid, item in zip(aids, synthetic_items)
                 if item['name_idx'] in foal_name_idxs]
    assert len(mother_aids) == family_pairs * spec['images_per_name']
    assert len(foal_aids) == family_pairs * spec['images_per_name']
    ibs.append_annot_case_tags(mother_aids, ['mother'] * len(mother_aids))
    ibs.append_annot_case_tags(foal_aids, ['foal'] * len(foal_aids))

    ibs.set_exemplars_from_quality_and_viewpoint()
    ibs.update_all_image_special_imageset()
    sysres.reset_test_graph(ibs)
    return ibs


def ensure_synthetic_match_db(reset=False, image_size=None):
    """Build the canonical local matching/inference fixture for tests.

    The database is generated entirely from deterministic synthetic images and
    metadata.  It never downloads or aliases a historical demo database.
    """
    import os
    import ubelt as ub
    import ibeis
    from ibeis.control import IBEISControl
    from ibeis.init import sysres

    spec = synthetic_match_spec()
    if image_size is None:
        image_size = spec['image_size']

    ibeis.ENABLE_WILDBOOK_SIGNAL = False
    workdir = ub.Path(sysres.get_workdir()).ensuredir()
    dbdir = workdir / spec['dbname']
    source_dpath = workdir / '_synthetic_testdata' / 'match'

    if reset:
        dbdir.delete()
        source_dpath.delete()

    if dbdir.exists():
        ibs = ibeis.opendb(dbdir=os.fspath(dbdir))
        if (len(ibs.get_valid_aids()) == spec['num_annots'] and
                len(ibs.get_valid_nids()) == spec['num_names']):
            return ibs
        raise AssertionError(
            'Refusing to reuse an unexpected synthetic match fixture at {!r}'
            .format(os.fspath(dbdir)))

    raw_img_dpath = (source_dpath / 'raw_images').ensuredir()
    synthetic_items = generate_synthetic_images(
        raw_img_dpath,
        image_size=image_size,
        images_per_name=spec['images_per_name'],
        num_names=spec['num_names'],
    )

    dbdir.ensuredir()
    ibs = IBEISControl.request_IBEISController(os.fspath(dbdir))
    image_paths = [os.fspath(item['image_fpath']) for item in synthetic_items]
    names = [item['creature_name'] for item in synthetic_items]
    gids = ibs.add_images(image_paths)
    bbox_list = [[0, 0, image_size, image_size] for _ in gids]
    aids = ibs.add_annots(gids, bbox_list=bbox_list)
    ibs.set_annot_name_texts(aids, names)

    assert len(ibs.get_valid_aids()) == spec['num_annots']
    assert len(ibs.get_valid_nids()) == spec['num_names']
    return _prepare_synthetic_match_db(ibs, synthetic_items, spec)

def ensure_synthetic_db1(reset=False):
    """
    New 2025 mechanism for test database with completed matching state.

    Example:
        >>> from ibeis.tests.reset_testdbs import *  # NOQA
        >>> ibs = ensure_synthetic_db1()
    """
    import ubelt as ub
    import os
    from ibeis.control import IBEISControl
    import ibeis
    ibeis.ENABLE_WILDBOOK_SIGNAL = False
    img_dpath = ub.Path.appdir('ibeis/demodata/synthetic_images1')
    if reset:
        # FIXME: deleting a database directory does not seem to close or
        # invalidate any existing open databases.
        img_dpath.delete()

    raw_img_dpath = (img_dpath / 'raw_images').ensuredir()
    dbname = 'synthetic_db1'
    dbdir = (img_dpath / 'database' / dbname)

    image_size = 512
    images_per_name = 4
    num_names = 10

    dbstamp = ub.CacheStamp('create_stamp', dpath=dbdir)
    if dbstamp.expired():
        dbdir.ensuredir()
        synthetic_items = generate_synthetic_images(raw_img_dpath,
                                                    image_size=image_size,
                                                    images_per_name=images_per_name,
                                                    num_names=num_names)
        ibs = IBEISControl.request_IBEISController(dbdir)
        image_paths = [os.fspath(item['image_fpath']) for item in synthetic_items]
        names = [item['creature_name'] for item in synthetic_items]
        image_ids = ibs.add_images(image_paths)
        bbox_list = [[0, 0, image_size, image_size] for _ in image_ids]
        annot_ids = ibs.add_annots(image_ids, bbox_list=bbox_list)
        ibs.set_annot_name_texts(annot_ids, names)
        dbstamp.renew()
    else:
        ibs = ibeis.opendb(dbdir=dbdir)
    return ibs


if __name__ == '__main__':
    r"""
    CommandLine:
        python -m ibeis.tests.reset_testdbs
    """
    import multiprocessing
    multiprocessing.freeze_support()  # For windows
    #ibeis._preload()
    reset_testdbs()
