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
    import ibeis
    from ibeis.init import sysres
    import ubelt as ub
    ibeis.ENABLE_WILDBOOK_SIGNAL = False
    workdir = ub.Path(sysres.get_workdir()).ensuredir()
    (workdir / 'testdb0').delete()
    (workdir / 'testdb1').delete()
    ensure_smaller_testingdbs()


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

    # Just do this one
    ensure_synthetic_db1(reset=True)

    # Step 3) Ensure DBs that dont exist
    ensure_smaller_testingdbs()
    workdir = sysres.get_workdir()
    if not ut.checkpath(join(workdir, 'PZ_MTEST'), verbose=True):
        ibeis.ensure_pz_mtest()
    if not ut.checkpath(join(workdir, 'NAUT_test'), verbose=True):
        ibeis.ensure_nauts()
    # if not ut.checkpath(join(workdir, 'wd_peter2'), verbose=True):
    #     ibeis.ensure_wilddogs()
    if not ut.checkpath(join(workdir, 'testdb2'), verbose=True):
        sysres.ensure_testdb2()

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


def generate_synthetic_images(raw_img_dpath, image_size=512, images_per_name=4, num_names=10):
    import ubelt as ub
    synthetic_items = []
    for name_idx in range(1, num_names + 1):
        creature_name = f'creature_{name_idx:04d}'
        for variant in range(images_per_name):
            stem = f"{creature_name}__v{variant:02d}"
            name_dpath = (raw_img_dpath / creature_name)
            image_fpath = name_dpath / f"{stem}.png"
            synthetic_items.append({
                'creature_name': creature_name,
                'variant': variant,
                'image_fpath': image_fpath,
            })

    depends = {
        'image_size': image_size,
        'num_names': num_names,
        'images_per_name': images_per_name,
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
