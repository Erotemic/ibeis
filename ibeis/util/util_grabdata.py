"""
import liberator
import utool as ut
lib = liberator.Liberator()
lib.add_dynamic(ut.grab_zipped_url)
lib.close(['utool'])
print(lib.current_sourcecode())
"""
import ubelt as ub
from os.path import (
    exists, join, realpath, split, basename, splitext, normpath, expanduser)
import tarfile
import zipfile
from os.path import dirname
from os.path import commonprefix


QUIET = ub.argflag('--quiet')


def _extract_archive(archive_fpath, archive_file, archive_namelist, output_dir,
                     force_commonprefix=True, prefix=None,
                     dryrun=False, verbose=not QUIET, overwrite=None):
    """
    archive_fpath = zip_fpath
    archive_file = zip_file
    """
    # force extracted components into a subdirectory if force_commonprefix is
    # on return_path = output_diG
    # FIXMpathE doesn't work right
    if prefix is not None:
        output_dir = join(output_dir, prefix)
        ub.Path(output_dir).ensuredir()

    archive_basename, ext = split_archive_ext(basename(archive_fpath))
    if force_commonprefix and commonprefix(archive_namelist) == '':
        # use the archivename as the default common prefix
        output_dir = join(output_dir, archive_basename)
        ub.Path(output_dir).ensuredir()

    for member in archive_namelist:
        (dname, fname) = split(member)
        dpath = join(output_dir, dname)
        ub.Path(dpath).ensuredir()
        if verbose:
            print('[utool] Unarchive ' + fname + ' in ' + dpath)

        if not dryrun:
            if overwrite is False:
                if exists(join(output_dir, member)):
                    continue
            archive_file.extract(member, path=output_dir)
    return output_dir


def unzip_file(zip_fpath, force_commonprefix=True, output_dir=None,
               prefix=None, dryrun=False, overwrite=None):
    zip_file = zipfile.ZipFile(zip_fpath)
    if output_dir is None:
        output_dir  = dirname(zip_fpath)
    archive_namelist = zip_file.namelist()
    output_dir  = _extract_archive(zip_fpath, zip_file, archive_namelist,
                                   output_dir, force_commonprefix,
                                   prefix=prefix, dryrun=dryrun,
                                   overwrite=overwrite)
    zip_file.close()
    return output_dir


def untar_file(targz_fpath, force_commonprefix=True):
    tar_file = tarfile.open(targz_fpath, 'r:gz')
    output_dir = dirname(targz_fpath)
    archive_namelist = [mem.path for mem in tar_file.getmembers()]
    output_dir = _extract_archive(targz_fpath, tar_file, archive_namelist,
                                  output_dir, force_commonprefix)
    tar_file.close()
    return output_dir


def unarchive_file(archive_fpath, force_commonprefix=True):
    print('Unarchive: %r' % archive_fpath)
    if tarfile.is_tarfile(archive_fpath):
        return untar_file(archive_fpath, force_commonprefix=force_commonprefix)
    elif zipfile.is_zipfile(archive_fpath):
        return unzip_file(archive_fpath, force_commonprefix=force_commonprefix)
    elif archive_fpath.endswith('.gz') and not archive_fpath.endswith('.tar.gz'):
        """
        from utool.util_grabdata import *
        archive_fpath = '/home/joncrall/.config/utool/train-images-idx3-ubyte.gz'
        """
        # FIXME: unsure if this is general
        output_fpath = splitext(archive_fpath)[0]
        import gzip
        with gzip.open(archive_fpath, 'rb') as gzfile_:
            contents = gzfile_.read()
            with open(output_fpath, 'wb') as file_:
                file_.write(contents)
        return output_fpath
    #elif archive_fpath.endswith('.gz'):
    #    # This is to handle .gz files (not .tar.gz) like how MNIST is stored
    #    # Example: http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz
    #    return ungz_file(archive_fpath)
    else:
        if archive_fpath.endswith('.zip') or archive_fpath.endswith('.tar.gz'):
            raise AssertionError('archive is corrupted: %r' % (archive_fpath,))
        raise AssertionError('unknown archive format: %r' % (archive_fpath,))


def split_archive_ext(path):
    special_exts = ['.tar.gz', '.tar.bz2']
    for ext in special_exts:
        if path.endswith(ext):
            name, ext = path[:-len(ext)], path[-len(ext):]
            break
    else:
        name, ext = splitext(path)
    return name, ext


def clean_dropbox_link(dropbox_url):
    """
    Dropbox links should be en-mass downloaed from dl.dropbox

    Example:
        >>> # ENABLE_DOCTEST
        >>> dropbox_url = 'www.dropbox.com/s/123456789abcdef/foobar.zip?dl=0'
        >>> cleaned_url = clean_dropbox_link(dropbox_url)
        >>> result = str(cleaned_url)
        >>> print(result)
        dl.dropbox.com/s/123456789abcdef/foobar.zip
    """
    cleaned_url = dropbox_url.replace('www.dropbox', 'dl.dropbox')
    postfix_list = [
        '?dl=0'
    ]
    for postfix in postfix_list:
        if cleaned_url.endswith(postfix):
            cleaned_url = cleaned_url[:-1 * len(postfix)]
    # cleaned_url = cleaned_url.rstrip('?dl=0')
    return cleaned_url


def grab_zipped_url(zipped_url, ensure=True, appname='utool',
                    download_dir=None, force_commonprefix=True, cleanup=False,
                    redownload=False, existing_zip_fpath=None):
    r"""
    downloads and unzips the url

    Args:
        zipped_url (str): url which must be either a .zip of a .tar.gz file
        ensure (bool):  eager evaluation if True(default = True)
        appname (str): (default = 'utool')
        download_dir (str): containing downloading directory
        force_commonprefix (bool): (default = True)
        cleanup (bool): (default = False)
        redownload (bool): (default = False)

    Examples:
        >>> # DISABLE_DOCTEST
        >>> zipped_url = 'https://lev.cs.rpi.edu/public/data/testdata.zip'
        >>> zipped_url = 'http://www.spam.com/eggs/data.zip'

    """
    if zipped_url is not None:
        zipped_url = clean_dropbox_link(zipped_url)
        zip_fname = split(zipped_url)[1]
    if existing_zip_fpath is not None:
        existing_zip_fpath = ub.Path(existing_zip_fpath)
        zip_fname = existing_zip_fpath.name
    data_name = split_archive_ext(zip_fname)[0]
    # Download zipfile to
    if download_dir is None:
        download_dir = ub.Path.appdir(appname)
    # Zipfile should unzip to:
    data_dir = join(download_dir, data_name)
    if ensure or redownload:
        if redownload:
            ub.Path(data_dir).delete()
        ub.Path(download_dir).ensuredir()
        if not exists(data_dir) or redownload:
            # Download and unzip testdata
            if existing_zip_fpath:
                zip_fpath =  existing_zip_fpath
            else:
                zip_fpath = realpath(join(download_dir, zip_fname))
            #print('[utool] Downloading archive %s' % zip_fpath)
            if not exists(zip_fpath) or redownload:
                assert not existing_zip_fpath
                do_http_download = True
                if zipped_url and '/ipfs/' in zipped_url and ub.find_exe('ipfs'):
                    # Use a real ipfs client if we can.
                    ipfs_address = zipped_url.split('/ipfs/')[-1]
                    try:
                        ub.cmd(f'ipfs get {ipfs_address} -o {zip_fpath}', verbose=3)
                    except Exception:
                        ...
                    else:
                        do_http_download = False

                if do_http_download:
                    import safer
                    with safer.open(zip_fpath, 'wb') as file:
                        ub.download(zipped_url, file, chunksize=2 ** 20)
            unarchive_file(zip_fpath, force_commonprefix)
            if cleanup:
                assert exists(data_dir)
                ub.Path(zip_fpath).delete()  # Cleanup
    if cleanup:
        assert exists(data_dir)
    return unixpath(data_dir)


def truepath(path):
    """ Normalizes and returns absolute path with so specs """
    return normpath(realpath(expanduser(path)))


def unixpath(path):
    """
    TODO: rename to unix_truepath
    Corrects fundamental problems with windows paths.~ """
    return truepath(path).replace('\\', '/')
