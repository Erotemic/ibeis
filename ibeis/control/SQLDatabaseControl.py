from __future__ import absolute_import, division, print_function
# Python
import six
from six.moves import map, zip
from os.path import join, exists, dirname, realpath
import utool
# Tools
from ibeis import constants
from ibeis.control._sql_helpers import (_unpacker, sanatize_sql,
                                        SQLExecutionContext, PRINT_SQL)
from ibeis.control import __SQLITE3__ as lite
(print, print_, printDBG, rrr, profile) = utool.inject(__name__, '[sql]')


def default_decorator(func):
    return func
    #return profile(func)
    #return utool.indent_func('[sql.' + func.__name__ + ']')(func)

VERBOSE = utool.VERBOSE
VERYVERBOSE = utool.VERYVERBOSE
QUIET = utool.QUIET or utool.get_argflag('--quiet-sql')
AUTODUMP = utool.get_argflag('--auto-dump')
COPY_TO_MEMORY = utool.get_argflag('--copy-db-to-memory')

""" If would be really great if we could get a certain set of setters, getters,
and deleters to be indexed into only with rowids. If we could do this than for
that subset of data, we could hook up a least recently used cache which is
populated whenever you get data from some table/colname using the rowid as the
key. The cache would then only have to be invalidated if we were going to set /
get data from that same rowid.  This would offer big speadups for both the
recognition algorithm and the GUI. """

from functools import wraps


def common_decor(func):
    @wraps(func)
    def closure_common(db, *args, **kwargs):
        return func(db, *args, **kwargs)
    return default_decorator(closure_common)


def getter_sql(func):
    @wraps(func)
    def closure_getter(db, *args, **kwargs):
        return func(db, *args, **kwargs)
    return common_decor(func)


def adder_sql(func):
    #return common_decor(func)
    return func


def setter_sql(func):
    #return common_decor(func)
    return func


def deleter_sql(func):
    #return common_decor(func)
    return func


def ider_sql(func):
    #return common_decor(func)
    return func


__STR__ = str if six.PY3 else unicode


class SQLAtomicContext(object):
    def __init__(context, db, verbose=PRINT_SQL):
        context.db = db  # Reference to sqldb
        context.cur = context.db.connection.cursor()  # Get new cursor
        context.verbose = verbose

    def __enter__(context):
        """ Sets the database into a state of an atomic transaction """
        context.cur.execute('BEGIN EXCLUSIVE TRANSACTION')
        return context

    def __exit__(context, type_, value, trace):
        """ Finalization of an SQLAtomicContext """
        if trace is not None:
            # An SQLError is a serious offence.
            print('[sql] FATAL ERROR IN ATOMIC CONTEXT')
            context.db.dump()  # Dump on error
            print('[sql] Error in atomic context manager!: ' + str(value))
            return False  # return a falsey value on error
        else:
            context.db.connection.commit()
            context.cur.close()


class SQLDatabaseController(object):
    """
    SQLDatabaseController an efficientish interface into SQL
    """

    def __init__(db, sqldb_dpath='.', sqldb_fname='database.sqlite3',
                 text_factory=__STR__):
        """ Creates db and opens connection """
        #with utool.Timer('New SQLDatabaseController'):
        #printDBG('[sql.__init__]')
        # TODO:
        db.stack = []
        db.cache = {}  # key \in [tblname][colnames][rowid]
        # Get SQL file path
        db.dir_  = sqldb_dpath
        db.fname = sqldb_fname
        assert exists(db.dir_), '[sql] db.dir_=%r does not exist!' % db.dir_
        db.fpath    = join(db.dir_, db.fname)
        db.text_factory = text_factory
        if not exists(db.fpath):
            print('[sql] Initializing new database')
        # Open the SQL database connection with support for custom types
        #lite.enable_callback_tracebacks(True)
        #db.fpath = ':memory:'
        db.connection = lite.connect2(db.fpath)
        db.connection.text_factory = db.text_factory
        #db.connection.isolation_level = None  # turns sqlite3 autocommit off
        #db.connection.isolation_level = lite.IMMEDIATE  # turns sqlite3 autocommit off
        if COPY_TO_MEMORY:
            db._copy_to_memory()
            db.connection.text_factory = text_factory
        # Get a cursor which will preform sql commands / queries / executions
        db.cur = db.connection.cursor()
        # Optimize the database (if anything is set)
        #db.optimize()
        db._ensure_metadata_table()

    def _ensure_metadata_table(db):
        # We need this to be done every time so that the update code works correctly.
        db.add_table(constants.METADATA_TABLE, (
            ('metadata_rowid',               'INTEGER PRIMARY KEY'),
            ('metadata_key',                 'TEXT'),
            ('metadata_value',               'TEXT'),
        ),
            superkey_colnames=['metadata_key'],
            docstr='''
            The table that stores permanently all of the metadata about the database (tables, etc)''')

    def _copy_to_memory(db):
        # http://stackoverflow.com/questions/3850022/python-sqlite3-load-existing-db-file-to-memory
        from six.moves import cStringIO
        print('[sql] Copying database into RAM')
        tempfile = cStringIO()
        for line in db.connection.iterdump():
            tempfile.write('%s\n' % line)
        db.connection.close()
        tempfile.seek(0)
        # Create a database in memory and import from tempfile
        db.connection = lite.connect2(":memory:")
        db.connection.cursor().executescript(tempfile.read())
        db.connection.commit()
        db.connection.row_factory = lite.Row

    #@utool.memprof
    def reboot(db):
        print('[sql] reboot')
        db.cur.close()
        del db.cur
        db.connection.close()
        del db.connection
        db.connection = lite.connect2(db.fpath)
        db.connection.text_factory = db.text_factory
        db.cur = db.connection.cursor()

    @default_decorator
    def optimize(db):
        # http://web.utk.edu/~jplyon/sqlite/SQLite_optimization_FAQ.html#pragma-cache_size
        # http://web.utk.edu/~jplyon/sqlite/SQLite_optimization_FAQ.html
        print('[sql] executing sql optimizions')
        #db.cur.execute('PRAGMA cache_size = 0;')
        #db.cur.execute('PRAGMA cache_size = 1024;')
        #db.cur.execute('PRAGMA page_size = 1024;')
        #db.cur.execute('PRAGMA synchronous = OFF;')
        #db.cur.execute('PRAGMA count_changes = OFF;')
        #db.cur.execute('PRAGMA journal_mode = OFF;')
        #db.cur.execute('PRAGMA max_page_count = 0;')
        #db.cur.execute('PRAGMA page_size = 512;')
        #db.cur.execute('PRAGMA parser_trace = OFF;')
        #db.cur.execute('PRAGMA busy_timeout = 1;')
        #db.cur.execute('PRAGMA default_cache_size = 0;')

    @default_decorator
    def shrink_memory(db):
        print('[sql] shrink_memory')
        db.connection.commit()
        db.cur.execute('PRAGMA shrink_memory;')
        db.connection.commit()

    @default_decorator
    def vacuum(db):
        print('[sql] vaccum')
        db.connection.commit()
        db.cur.execute('VACUUM;')
        db.connection.commit()

    @default_decorator
    def squeeze(db):
        print('[sql] squeeze')
        db.shrink_memory()
        db.vacuum()

    #==============
    # API INTERFACE
    #==============

    #@ider_sql
    def get_all_rowids(db, tblname):
        """ returns a list of all rowids from a table in ascending order """
        fmtdict = {'tblname': tblname, }
        operation_fmt = '''
        SELECT rowid
        FROM {tblname}
        ORDER BY rowid ASC
        '''
        return db._executeone_operation_fmt(operation_fmt, fmtdict)

    #@ider_sql
    def get_all_rowids_where(db, tblname, where_clause, params, **kwargs):
        """ returns a list of rowids from a table in ascending order satisfying
        a condition """
        fmtdict = {'tblname': tblname, 'where_clause': where_clause, }
        operation_fmt = '''
        SELECT rowid
        FROM {tblname}
        WHERE {where_clause}
        ORDER BY rowid ASC
        '''
        return db._executeone_operation_fmt(operation_fmt, fmtdict, params, **kwargs)

    def _add(db, tblname, colnames, params_iter, **kwargs):
        """ ADDER NOTE: use add_cleanly """
        fmtdict = {'tblname'  : tblname,
                    'erotemes' : ', '.join(['?'] * len(colnames)),
                    'params'   : ',\n'.join(colnames), }
        operation_fmt = '''
        INSERT INTO {tblname}(
        rowid,
        {params}
        ) VALUES (NULL, {erotemes})
        '''
        rowid_list = db._executemany_operation_fmt(operation_fmt, fmtdict,
                                                   params_iter=params_iter, **kwargs)
        return rowid_list

    #@adder_sql
    def add_cleanly(db, tblname, colnames, params_iter, get_rowid_from_superkey, superkey_paramx=(0,)):
        """ ADDER Extra input:
            the first item of params_iter must be a superkey (like a uuid), """
        # ADD_CLEANLY_1: PREPROCESS INPUT
        params_list = list(params_iter)  # eagerly evaluate for superkeys
        # Extract superkeys from the params list (requires eager eval)
        superkey_lists = [[None if params is None else params[x]
                           for params in params_list]
                          for x in superkey_paramx]
        # ADD_CLEANLY_2: PREFORM INPUT CHECKS
        # check which parameters are valid
        isvalid_list = [params is not None for params in params_list]
        # Check for duplicate inputs
        isunique_list = utool.flag_unique_items(list(zip(*superkey_lists)))
        # Check to see if this already exists in the database
        rowid_list_ = get_rowid_from_superkey(*superkey_lists)
        isnew_list  = [rowid is None for rowid in rowid_list_]
        if VERBOSE and not all(isunique_list):
            print('[WARNING]: duplicate inputs to db.add_cleanly')
        # Flag each item that needs to added to the database
        isdirty_list = list(map(all, zip(isvalid_list, isunique_list, isnew_list)))
        # ADD_CLEANLY_3.1: EXIT IF CLEAN
        if not any(isdirty_list):
            return rowid_list_  # There is nothing to add. Return the rowids
        # ADD_CLEANLY_3.2: PERFORM DIRTY ADDITIONS
        dirty_params = utool.filter_items(params_list, isdirty_list)
        if utool.VERBOSE:
            print('[sql] adding %r/%r new %s' % (len(dirty_params), len(params_list), tblname))
        # Add any unadded parameters to the database
        try:
            db._add(tblname, colnames, dirty_params)
        except Exception as ex:
            utool.printex(ex, key_list=[
                'dirty_params',
                'isdirty_list',
                'superkey_lists',
                'rowid_list_'])
            raise
        # TODO: We should only have to preform a subset of adds here
        # (at the positions where rowid_list was None in the getter check)
        rowid_list = get_rowid_from_superkey(*superkey_lists)

        # ADD_CLEANLY_4: SANITY CHECK AND RETURN
        assert len(rowid_list) == len(params_list), 'failed sanity check'
        return rowid_list

    def get_where2(db, tblname, colnames, params_iter, andwhere_colnames,
                   unpack_scalars=True, eager=True, **kwargs):
        """ hacked in function for nicer templates """
        andwhere_clauses = [colname + '=?' for colname in andwhere_colnames]
        where_clause = ' AND '.join(andwhere_clauses)
        return db.get_where(tblname, colnames, params_iter, where_clause,
                            unpack_scalars=unpack_scalars, eager=eager,
                            **kwargs)

    #@getter_sql
    def get_where(db, tblname, colnames, params_iter, where_clause,
                  unpack_scalars=True, eager=True,
                  **kwargs):

        assert isinstance(colnames, tuple)
        #if isinstance(colnames, six.string_types):
        #    colnames = (colnames,)
        if where_clause is None:
            fmtdict = {'tblname'     : tblname,
                       'colnames'    : ', '.join(colnames), }
            operation_fmt = '''
            SELECT {colnames}
            FROM {tblname}
            '''
            val_list = db._executeone_operation_fmt(operation_fmt, fmtdict, **kwargs)
        else:
            fmtdict = { 'tblname'     : tblname,
                        'colnames'    : ', '.join(colnames),
                        'where_clauses' :  where_clause, }
            operation_fmt = '''
            SELECT {colnames}
            FROM {tblname}
            WHERE {where_clauses}
            '''

            val_list = db._executemany_operation_fmt(operation_fmt, fmtdict,
                                                     params_iter=params_iter,
                                                     unpack_scalars=unpack_scalars,
                                                     eager=eager, **kwargs)
        return val_list

    #@getter_sql
    def get_rowid_from_superkey(db, tblname, params_iter=None, superkey_colnames=None, **kwargs):
        """ getter which uses the constrained superkeys instead of rowids """
        where_clause = ' AND '.join([colname + '=?' for colname in superkey_colnames])
        return db.get_where(tblname, ('rowid',), params_iter, where_clause, **kwargs)

    #@getter_sql
    def get(db, tblname, colnames, id_iter=None, id_colname='rowid', eager=True, **kwargs):
        """ getter
        Args:
            tblname (str): table name to get from
            colnames (tuple of str): column names to grab from
            id_iter (iterable): iterable of search keys
            id_colname (str): column to be used as the search key (default: rowid)
            eager (bool): use eager evaluation
        """
        assert isinstance(colnames, tuple), 'must specify column names to get from'
        #if isinstance(colnames, six.string_types):
        #    colnames = (colnames,)
        if id_iter is None:
            where_clause = None
            params_iter = []
        else:
            where_clause = (id_colname + '=?')
            params_iter = ((_rowid,) for _rowid in id_iter)

        return db.get_where(tblname, colnames, params_iter, where_clause, eager=eager, **kwargs)

    #@setter_sql
    def set(db, tblname, colnames, val_iter, id_iter, id_colname='rowid', **kwargs):
        """ setter """
        assert isinstance(colnames, tuple)
        #if isinstance(colnames, six.string_types):
        #    colnames = (colnames,)
        val_list = list(val_iter)  # eager evaluation
        id_list = list(id_iter)  # eager evaluation

        assert len(id_list) == len(set(id_list)), "Passing a not-unique list of ids"

        if not QUIET and VERBOSE:
            print('[sql] SETTER: ' + utool.get_caller_name())
            print('[sql] * tblname=%r' % (tblname,))
            print('[sql] * val_list=%r' % (val_list,))
            print('[sql] * id_list=%r' % (id_list,))
            print('[sql] * id_colname=%r' % (id_colname,))
        try:
            num_val = len(val_list)
            num_id = len(id_list)
            assert num_val == num_id, 'list inputs have different lengths'
        except AssertionError as ex:
            utool.printex(ex, key_list=['num_val', 'num_id'])
            raise
        fmtdict = {
            'tblname_str'  : tblname,
            'assign_str'   : ',\n'.join(['%s=?' % name for name in colnames]),
            'where_clause' : (id_colname + '=?'),
        }
        operation_fmt = '''
            UPDATE {tblname_str}
            SET {assign_str}
            WHERE {where_clause}
            '''

        # TODO: The flattenize can be removed if we pass in val_lists instead
        params_iter = utool.flattenize(list(zip(val_list, id_list)))
        #params_iter = list(zip(val_list, id_list))
        return db._executemany_operation_fmt(operation_fmt, fmtdict,
                                             params_iter=params_iter, **kwargs)

    #@deleter_sql
    def delete(db, tblname, id_list, id_colname='rowid', **kwargs):
        """ deleter. USE delete_rowids instead """
        fmtdict = {
            'tblname'   : tblname,
            'rowid_str' : (id_colname + '=?'),
        }
        operation_fmt = '''
            DELETE
            FROM {tblname}
            WHERE {rowid_str}
            '''
        params_iter = ((_rowid,) for _rowid in id_list)
        return db._executemany_operation_fmt(operation_fmt, fmtdict,
                                             params_iter=params_iter,
                                             **kwargs)

    #@deleter_sql
    def delete_rowids(db, tblname, rowid_list, **kwargs):
        """ deletes the the rows in rowid_list """
        fmtdict = {
            'tblname'   : tblname,
            'rowid_str' : ('rowid=?'),
        }
        operation_fmt = '''
            DELETE
            FROM {tblname}
            WHERE {rowid_str}
            '''
        params_iter = ((_rowid,) for _rowid in rowid_list)
        return db._executemany_operation_fmt(operation_fmt, fmtdict,
                                             params_iter=params_iter,
                                             **kwargs)

    #==============
    # CORE WRAPPERS
    #==============

    @default_decorator
    def _executeone_operation_fmt(db, operation_fmt, fmtdict, params=None, eager=True, **kwargs):
        if params is None:
            params = []
        operation = operation_fmt.format(**fmtdict)
        return db.executeone(operation, params, auto_commit=True, eager=eager, **kwargs)

    @default_decorator
    def _executemany_operation_fmt(db, operation_fmt, fmtdict, params_iter,
                                   unpack_scalars=True, eager=True, **kwargs):
        operation = operation_fmt.format(**fmtdict)
        return db.executemany(operation, params_iter, unpack_scalars=unpack_scalars,
                              auto_commit=True, eager=eager, **kwargs)

    #=========
    # SQLDB CORE
    #=========

    @default_decorator
    def add_table(db, tablename, coldef_list, table_constraints=None, docstr='', superkey_colnames=None):
        """
        add_table

        Args:
            tablename (str):
            coldef_list (list):
            table_constraints (list or None):
            docstr (str):
            superkey_colnames (list or None): list of column names which uniquely identifies a rowid
        """
        if utool.DEBUG2:
            print('[sql] schema ensuring tablename=%r' % tablename)
        if utool.VERBOSE:
            print('')
            print(utool.func_str(db.add_table, [tablename, coldef_list],
                                 dict(table_constraints=table_constraints, docstr=docstr,
                                      superkey_colnames=superkey_colnames)))
            print('')
        # Technically insecure call, but all entries are statically inputted by
        # the database's owner, who could delete or alter the entire database
        # anyway.
        if table_constraints is None:
            table_constraints = []

        if superkey_colnames is not None and len(superkey_colnames) > 0:
            _ = ','.join(superkey_colnames)
            ###
            #c = superkey_colnames
            #_ = (c if isinstance(c, six.string_types) else ','.join(c))
            unique_constraint = 'CONSTRAINT superkey UNIQUE ({_})'.format(_=_)
            assert len(table_constraints) == 0
            table_constraints.append(unique_constraint)

        body_list = ['%s %s' % (name, type_) for (name, type_) in coldef_list]

        fmtkw = {
            'table_body': ', '.join(body_list + table_constraints),
            'tablename': tablename,
        }
        op_fmtstr = 'CREATE TABLE IF NOT EXISTS {tablename} ({table_body})'
        operation = op_fmtstr.format(**fmtkw)
        db.executeone(operation, [], verbose=False)

        if docstr is not None:
            # Insert or replace docstr in metadata table
            fmtkw = {
                'tablename': constants.METADATA_TABLE,
                'columns': 'metadata_key, metadata_value'
            }
            op_fmtstr = 'INSERT OR REPLACE INTO {tablename} ({columns}) VALUES (?, ?)'
            operation = op_fmtstr.format(**fmtkw)
            params = [tablename + '_docstr', docstr]
            db.executeone(operation, params, verbose=False)

        if len(table_constraints) > 0:
            # Insert or replace constraint in metadata table
            fmtkw = {
                'tablename': constants.METADATA_TABLE,
                'columns': 'metadata_key, metadata_value'
            }
            op_fmtstr = 'INSERT OR REPLACE INTO {tablename} ({columns}) VALUES (?, ?)'
            operation = op_fmtstr.format(**fmtkw)
            params = [tablename + '_constraint', ';'.join(table_constraints)]
            db.executeone(operation, params, verbose=False)

        if superkey_colnames is not None:
            # Insert or replace superkeys in metadata table
            fmtkw = {
                'tablename': constants.METADATA_TABLE,
                'columns': 'metadata_key, metadata_value'
            }
            op_fmtstr = 'INSERT OR REPLACE INTO {tablename} ({columns}) VALUES (?, ?)'
            operation = op_fmtstr.format(**fmtkw)
            params = [tablename + '_superkeys', ';'.join(superkey_colnames)]
            db.executeone(operation, params, verbose=False)

    @default_decorator
    def add_column(db, tablename, colname, coltype):
        printDBG('[sql] add column=%r of type=%r to tablename=%r' % (colname, coltype, tablename))
        fmtkw = {
            'tablename': tablename,
            'colname': colname,
            'coltype': coltype,
        }
        op_fmtstr = 'ALTER TABLE {tablename} ADD COLUMN {colname} {coltype}'
        operation = op_fmtstr.format(**fmtkw)
        db.executeone(operation, [], verbose=False)

    @default_decorator
    def modify_table(db, tablename, colmap_list, table_constraints=None, docstr=None, superkey_colnames=None, tablename_new=None):
        """
        funciton to modify the schema - only columns that are being added, removed or changed need to be enumerated

        Example:
            >>> def contributor_location_zip_map(x):
            ...     return x
            >>> ibs = None
            >>> ibs.db.modify_table(constants.CONTRIBUTOR_TABLE, (
            ... #  Original Column Name,             New Column Name,                 New Column Type, Function to convert data from old to new
            ... #   [None to append, int for index]  ['' for same, None to delete]    ['' for same]    [None to use data unmodified]
            ...    ('contributor_rowid',             '',                              '',               None), # a non-needed, but correct mapping (identity function)
            ...    (None,                            'contributor__location_address', 'TEXT',           None), # for new columns, function is ignored (TYPE CANNOT BE EMPTY IF ADDING)
            ...    (4,                               'contributor__location_address', 'TEXT',           None), # adding a new column at index 4 (if index is invalid, None is used)
            ...    ('contributor__location_city',    None,                            '',               None), # for deleted columns, type and function are ignored
            ...    ('contributor__location_city',    'contributor__location_town',    '',               None), # for renamed columns, type and function are ignored
            ...    ('contributor_location_zip',      'contributor_location_zip',      'TEXT',           contributor_location_zip_map),
            ...    ('contributor__location_country', '',                              'TEXT NOT NULL',  None), # type not changing, only NOT NULL provision
            ...    ),
            ...    superkey_colnames=['contributor_rowid'],
            ...    docstr='Used to store the contributors to the project'
            ... )
        """
        printDBG('[sql] schema modifying tablename=%r' % tablename)

        colname_list = db.get_column_names(tablename)
        colname_original_list = colname_list[:]
        coltype_list = db.get_column_types(tablename)
        colname_dict = {}
        colmap_dict  = {}

        for colname in colname_list:
            colname_dict[colname] = colname

        insert = False
        for (src, dst, type_, map_) in colmap_list:
            if src is None or isinstance(src, int):
                # Add column
                assert dst is not None and len(dst) > 0, "New column's name must be valid"
                assert type_ is not None and len(type_) > 0, "New column's type must be specified"
                if isinstance(src, int) and (src < 0 or len(colname_list) <= src):
                    src = None
                if src is None:
                    colname_list.append(dst)
                    coltype_list.append(type_)
                else:
                    if insert:
                        print('[sql] WARNING: multiple index inserted add columns, may cause allignment issues')
                    colname_list.insert(src, dst)
                    coltype_list.insert(src, type_)
                    insert = True
            else:
                assert src in colname_list, 'Unkown source colname=%s in tablename=%s' % (src, tablename)
                index = colname_list.index(src)
                if dst is None:
                    # Drop column
                    assert src is not None and len(src) > 0, "Deleted column's name  must be valid"
                    del colname_list[index]
                    del coltype_list[index]
                    del colname_dict[src]
                elif (len(src) > 0 and len(dst) > 0 and src != dst and
                      (len(type_) == 0 or type_ == coltype_list[index])):
                    # Rename column
                    if len(type_) == 0:
                        type_ = coltype_list[index]
                    colname_list[index] = dst
                    coltype_list[index] = type_
                    colname_dict[src] = dst
                elif len(type_) > 0 and type_ != coltype_list[index]:
                    # Change column type
                    if len(dst) == 0:
                        dst = src
                    coltype_list[index] = type_
                elif map_ is not None:
                    # Simply map function across table's data
                    if len(dst) == 0:
                        dst = src
                    if len(type_) == 0:
                        type_ = coltype_list[index]
                else:
                    # Identity, this can be ommited as it is automatically done
                    if len(dst) == 0:
                        dst = src
                    if len(type_) == 0:
                        type_ = coltype_list[index]
            if map_ is not None:
                colmap_dict[src] = map_

        coldef_list = [ _ for _ in zip(colname_list, coltype_list) ]
        tablename_temp = tablename + '_temp' + utool.random_nonce(length=8)
        if docstr is None:
            docstr = db.get_table_docstr(tablename)
        if table_constraints is None:
            table_constraints = db.get_table_constraints(tablename)

        db.add_table(tablename_temp, coldef_list,
                     table_constraints=table_constraints,
                     docstr=docstr,
                     superkey_colnames=superkey_colnames)

        # Copy data
        src_list = []
        dst_list = []

        for name in colname_original_list:
            if name in colname_dict.keys():
                src_list.append(name)
                dst_list.append(colname_dict[name])

        data_list = db.get(tablename, tuple(src_list))
        # Run functions across all data for specified callums
        data_list = [
            tuple([
                colmap_dict[src_](d) if src_ in colmap_dict.keys() else d
                for d, src_ in zip(data, src_list)
            ])
            for data in data_list
        ]
        # Add the data to the database
        db.add_cleanly(tablename_temp, dst_list, data_list, (lambda x: [None] * len(x)))
        if tablename_new is None:
            # Drop original table
            db.drop_table(tablename)
            # Rename temp table to original table name
            db.rename_table(tablename_temp, tablename)
        else:
            # Rename new table to new name
            db.rename_table(tablename_temp, tablename_new)

    @default_decorator
    def reorder_columns(db, tablename, order_list):
        printDBG('[sql] schema column reordering for tablename=%r' % tablename)
        # Get current tables
        colname_list = db.get_column_names(tablename)
        coltype_list = db.get_column_types(tablename)
        assert len(colname_list) == len(coltype_list) and len(colname_list) == len(order_list)
        assert all([ i in order_list for i in range(len(colname_list)) ]), 'Order index list invalid'
        # Reorder column definitions
        combined = sorted(list(zip(order_list, colname_list, coltype_list)))
        coldef_list = [ (name, type_) for i, name, type_ in combined ]
        tablename_temp = tablename + '_temp' + utool.random_nonce(length=8)
        docstr = db.get_table_docstr(tablename)
        table_constraints = db.get_table_constraints(tablename)

        db.add_table(tablename_temp, coldef_list,
                     table_constraints=table_constraints,
                     docstr=docstr,)
        # Copy data
        data_list = db.get(tablename, tuple(colname_list))
        # Add the data to the database
        db.add_cleanly(tablename_temp, colname_list, data_list, (lambda x: [None] * len(x)))
        # Drop original table
        db.drop_table(tablename)
        # Rename temp table to original table name
        db.rename_table(tablename_temp, tablename)

    @default_decorator
    def duplicate_table(db, tablename, tablename_duplicate):
        printDBG('[sql] schema duplicating tablename=%r into tablename=%r' % (tablename, tablename_duplicate))
        db.modify_table(tablename, [], tablename_new=tablename_duplicate)

    @default_decorator
    def duplicate_column(db, tablename, colname, colname_duplicate):
        printDBG('[sql] schema duplicating tablename.colname=%r.%r into tablename.colname=%r.%r' % (tablename, colname, tablename, colname_duplicate))
        # Modify table to add a blank column with the appropriate tablename and NO data
        column_names = db.get_column_names(tablename)
        column_types = db.get_column_types(tablename)
        assert len(column_names) == len(column_types)
        try:
            index = column_names.index(colname)
        except Exception:
            printDBG('[!sql] could not find colname=%r to duplicate' % colname)
            return
        # Add column to the table
        # DATABASE TABLE CACHES ARE UPDATED WITH add_column
        db.add_column(tablename, colname_duplicate, column_types[index])
        # Copy the data from the original column to the new duplcate column
        fmtkw = {
            'tablename':           tablename,
            'colname_duplicate':   colname_duplicate,
            'colname':             colname,
        }
        op_fmtstr = 'UPDATE {tablename} SET {colname_duplicate} = {colname}'
        operation = op_fmtstr.format(**fmtkw)
        db.executeone(operation, [], verbose=False)

    @default_decorator
    def rename_table(db, tablename_old, tablename_new):
        printDBG('[sql] schema renaming tablename=%r -> %r' % (tablename_old, tablename_new))
        # Technically insecure call, but all entries are statically inputted by
        # the database's owner, who could delete or alter the entire database
        # anyway.
        fmtkw = {
            'tablename_old': tablename_old,
            'tablename_new': tablename_new,
        }
        op_fmtstr = 'ALTER TABLE {tablename_old} RENAME TO {tablename_new}'
        operation = op_fmtstr.format(**fmtkw)
        db.executeone(operation, [], verbose=False)

        # Rename table's metadata
        key_old_list = [
            tablename_old + '_constraint',
            tablename_old + '_docstr',
            tablename_old + '_superkeys',
        ]
        key_new_list = [
            tablename_new + '_constraint',
            tablename_new + '_docstr',
            tablename_new + '_superkeys',
        ]
        id_iter = ((key,) for key in key_old_list)
        val_iter = ((key,) for key in key_new_list)
        colnames = ('metadata_key',)
        db.set(constants.METADATA_TABLE, colnames, val_iter, id_iter, id_colname='metadata_key')

    @default_decorator
    def rename_column(db, tablename, colname_old, colname_new):
        # DATABASE TABLE CACHES ARE UPDATED WITH modify_table
        db.modify_table(tablename, (
            (colname_old, colname_new, '', None),
        ))

    @default_decorator
    def drop_table(db, tablename):
        printDBG('[sql] schema dropping tablename=%r' % tablename)
        # Technically insecure call, but all entries are statically inputted by
        # the database's owner, who could delete or alter the entire database
        # anyway.
        fmtkw = {
            'tablename': tablename,
        }
        op_fmtstr = 'DROP TABLE IF EXISTS {tablename}'
        operation = op_fmtstr.format(**fmtkw)
        db.executeone(operation, [], verbose=False)

        # Delete table's metadata
        key_list = [
            tablename + '_constraint',
            tablename + '_docstr',
            tablename + '_superkeys',
        ]
        db.delete(constants.METADATA_TABLE, key_list, id_colname='metadata_key')

    @default_decorator
    def drop_column(db, tablename, colname):
        # DATABASE TABLE CACHES ARE UPDATED WITH modify_table
        db.modify_table(tablename, (
            (colname, None, '', None),
        ))

    @default_decorator
    def executeone(db, operation, params=(), auto_commit=True, eager=True,
                   verbose=VERYVERBOSE):
        with SQLExecutionContext(db, operation, num_params=1) as context:
            try:
                result_iter = context.execute_and_generate_results(params)
                result_list = list(result_iter)
            except Exception as ex:
                utool.printex(ex, key_list=[(str, 'operation'), 'params'])
                # utool.sys.exit(1)
                raise
        return result_list

    @default_decorator
    #@utool.memprof
    def executemany(db, operation, params_iter, auto_commit=True,
                    verbose=VERYVERBOSE, unpack_scalars=True, num_params=None,
                    eager=True):
        # --- ARGS PREPROC ---
        # Aggresively compute iterator if the num_params is not given
        if num_params is None:
            if isinstance(params_iter, (list, tuple)):
                num_params = len(params_iter)
            else:
                if VERYVERBOSE:
                    print('[sql!] WARNING: aggressive eval of params_iter because num_params=None')
                params_iter = list(params_iter)
                num_params  = len(params_iter)
        else:
            if VERYVERBOSE:
                print('[sql] Taking params_iter as iterator')

        # Do not compute executemany without params
        if num_params == 0:
            if VERYVERBOSE:
                print('[sql!] WARNING: dont use executemany'
                      'with no params use executeone instead.')
            return []
        # --- SQL EXECUTION ---
        contextkw = {
            'num_params': num_params,
            'start_transaction': True,
            'verbose': verbose,
        }

        with SQLExecutionContext(db, operation, **contextkw) as context:
            #try:
            if eager:
                #if utool.DEBUG2:
                #    print('--------------')
                #    print('+++ eager eval')
                #    print(operation)
                #    print('+++ eager eval')
                #results_iter = list(
                    #map(
                    #    list,
                    #    (context.execute_and_generate_results(params) for params in params_iter)
                    #)
                #)  # list of iterators
                results_iter = [list(context.execute_and_generate_results(params)) for params in params_iter]
                if unpack_scalars:
                    results_iter = list(map(_unpacker, results_iter))  # list of iterators
                results_list = list(results_iter)  # Eager evaluation
            else:
                #if utool.DEBUG2:
                #    print('--------------')
                #    print(' +++ lazy eval')
                #    print(operation)
                #    print(' +++ lazy eval')
                def tmpgen(context):
                    # Temporary hack to turn off eager_evaluation
                    for params in params_iter:
                        # Eval results per query yeild per iter
                        results = list(context.execute_and_generate_results(params))
                        if unpack_scalars:
                            yield _unpacker(results)
                        else:
                            yield results
                results_list = tmpgen(context)
            #except Exception as ex:
            #    utool.printex(ex)
            #    raise
        return results_list

    #@default_decorator
    #def commit(db):
    #    db.connection.commit()

    @default_decorator
    def dump_to_file(db, file_, auto_commit=True, schema_only=False):
        if VERYVERBOSE:
            print('[sql.dump]')
        if auto_commit:
            db.connection.commit()
            #db.commit(verbose=False)
        for line in db.connection.iterdump():
            if schema_only and line.startswith('INSERT'):
                continue
            file_.write('%s\n' % line)

    @default_decorator
    def dump_to_string(db, auto_commit=True, schema_only=False):
        retStr = ''
        if VERYVERBOSE:
            print('[sql.dump]')
        if auto_commit:
            db.connection.commit()
            #db.commit(verbose=False)
        for line in db.connection.iterdump():
            if schema_only and line.startswith('INSERT'):
                continue
            retStr += '%s\n' % line
        return retStr

    #==============
    # CONVINENCE
    #==============

    @default_decorator
    def dump(db, file_=None, auto_commit=True, schema_only=False):
        if file_ is None or isinstance(file_, six.string_types):
            dump_fpath = file_
            if dump_fpath is None:
                dump_fpath = join(db.dir_, db.fname + '.dump.txt')
            with open(dump_fpath, 'w') as file_:
                db.dump_to_file(file_, auto_commit, schema_only)
        else:
            db.dump_to_file(file_, auto_commit, schema_only)

    @default_decorator
    def dump_tables_to_csv(db):
        """ Convenience: Dumps all csv database files to disk """
        dump_dir = join(db.dir_, 'CSV_DUMP')
        utool.ensuredir(dump_dir)
        for tablename in db.get_table_names():
            table_fname = tablename + '.csv'
            table_csv = db.get_table_csv(tablename)
            with open(join(dump_dir, table_fname), 'w') as file_:
                file_.write(table_csv)

    @default_decorator
    def dump_schema(db):
        """ Convenience: Dumps all csv database files to disk """
        controller_directory = dirname(realpath(__file__))
        dump_fpath = join(controller_directory, 'schema.txt')
        with open(dump_fpath, 'w') as file_:
            for tablename in sorted(db.get_table_names()):
                file_.write(tablename + '\n')
                column_list = db.get_columns(tablename)
                for column in column_list:
                    col_name = str(column[1]).ljust(30)
                    col_type = str(column[2]).ljust(10)
                    col_null = str(('ALLOW NULL' if column[3] == 1 else 'NOT NULL')).ljust(12)
                    col_default = str(column[4]).ljust(10)
                    col_key = str(('KEY' if column[5] == 1 else ''))
                    col = (col_name, col_type, col_null, col_default, col_key)
                    file_.write('\t%s%s%s%s%s\n' % col)

    @default_decorator
    def get_table_names(db):
        """ Conveinience: """
        db.cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablename_list = db.cur.fetchall()
        return [ str(tablename[0]) for tablename in tablename_list ]

    @default_decorator
    def get_table_constraints(db, tablename):
        where_clause = 'metadata_key=?'
        colnames = ('metadata_value',)
        data = [(tablename + '_constraint',)]
        constraint = db.get_where(constants.METADATA_TABLE, colnames, data, where_clause)
        constraint = constraint[0]
        if constraint is None:
            return None
        else:
            return constraint.split(';')

    @default_decorator
    def get_table_superkeys(db, tablename):
        """
        get_table_superkeys

        Args:
            tablename (str):

        Returns:
            list: superkey_colname_list
        """
        where_clause = 'metadata_key=?'
        colnames = ('metadata_value',)
        data = [(tablename + '_superkeys',)]
        superkeys = db.get_where(constants.METADATA_TABLE, colnames, data, where_clause)
        # These asserts might not be valid, but in that case this function needs
        # to be rewritten under a different name
        assert len(superkeys) == 1, 'INVALID DEVELOPER ASSUMPTION IN SQLCONTROLLER. MORE THAN 1 SUPERKEY'
        superkey_colnames_str = superkeys[0]
        if superkey_colnames_str is None:
            # Sometimes the metadata gets moved for some reason
            # Hack the information out of the constraints
            constraint_list = db.get_table_constraints(tablename)
            assert len(constraint_list) == 1, 'INVALID DEVELOPER ASSUMPTION IN SQLCONTROLLER. MORE THAN 1 CONSTRAINT'
            if constraint_list is not None:
                import parse
                for constraint in constraint_list:
                    parse_result = parse.parse('CONSTRAINT superkey UNIQUE ({colnames})', constraint)
                    if parse_result is not None:
                        superkey_colnames = list(map(lambda x: x.strip(), parse_result['colnames'].split(',')))
            else:
                superkey_colnames = None
        else:
            superkey_colnames = superkey_colnames_str.split(';')
        return superkey_colnames

    get_table_superkey_colnames = get_table_superkeys

    @default_decorator
    def get_table_primarykey_colnames(db, tablename):
        columns = db.get_columns(tablename)
        primarykey_colnames = [name
                               for (column_id, name, type_, notnull, dflt_value, pk,) in columns
                               if pk]
        return primarykey_colnames

    @default_decorator
    def get_table_otherkey_colnames(db, tablename):
        superkey_colnames = set((lambda x: x if x is not None else [])(db.get_table_superkeys(tablename)))
        columns = db.get_columns(tablename)
        otherkey_colnames = [name
                             for (column_id, name, type_, notnull, dflt_value, pk,) in columns
                             if not pk and name not in superkey_colnames]
        return otherkey_colnames

    @default_decorator
    def get_table_docstr(db, tablename):
        where_clause = 'metadata_key=?'
        colnames = ('metadata_value',)
        data = [(tablename + '_docstr',)]
        docstr = db.get_where(constants.METADATA_TABLE, colnames, data, where_clause)
        return docstr[0]

    @default_decorator
    def get_columns(db, tablename):
        """
        get_columns

        Args:
            tablename (str): table name

        Returns:
            column_list : list of tuples with format:
                (
                    column_id  : id of the column
                    name       : the name of the column
                    type_      : the type of the column
                    notnull    : 0 or 1 if the column can contains null values
                    dflt_value : the default value
                    pk         : 0 or 1 if the column partecipate to the primary key
                )

        References:
            http://stackoverflow.com/questions/17717829/how-to-get-column-names-from-a-table-in-sqlite-via-pragma-net-c

        Example:
            >>> from ibeis.control.SQLDatabaseControl import *  # NOQA
        """
        db.cur.execute("PRAGMA TABLE_INFO('" + tablename + "')")
        column_list = db.cur.fetchall()
        return column_list

    @default_decorator
    def get_column_names(db, tablename):
        """ Conveinience: Returns the sql tablename columns """
        column_list = db.get_columns(tablename)
        column_names = [ str(column[1]) for column in column_list]
        return column_names

    @default_decorator
    def get_column_types(db, tablename):
        """ Conveinience: Returns the sql tablename columns """
        def _format(type_, null, default, key):
            if key == 1:
                return type_ + " PRIMARY KEY"
            elif null == 1:
                return type_ + " NOT NULL"
            elif default is not None:
                return type_ + " DEFAULT " + default
            else:
                return type_

        column_list = db.get_columns(tablename)
        column_types   = [ column[2] for column in column_list]
        column_null    = [ column[3] for column in column_list]
        column_default = [ column[4] for column in column_list]
        column_key     = [ column[5] for column in column_list]
        column_types_  = [
            _format(type_, null, default, key)
            for type_, null, default, key
            in zip(column_types, column_null, column_default, column_key)
        ]
        return column_types_

    @default_decorator
    def get_column(db, tablename, name):
        """ Conveinience: """
        _table, (_column,) = sanatize_sql(db, tablename, (name,))
        column_vals = db.executeone(
            operation='''
            SELECT %s
            FROM %s
            ORDER BY rowid ASC
            ''' % (_column, _table))
        return column_vals

    @default_decorator
    def get_table_csv(db, tablename, exclude_columns=[]):
        """ Conveinience: Converts a tablename to csv format """
        column_names = db.get_column_names(tablename)
        column_list = []
        column_lbls = []
        for name in column_names:
            if name in exclude_columns:
                continue
            column_vals = db.get_column(tablename, name)
            column_list.append(column_vals)
            column_lbls.append(name.replace(tablename[:-1] + '_', ''))
        # remove column prefix for more compact csvs

        #=None, column_list=[], header='', column_type=None
        header = db.get_table_csv_header(tablename)
        csv_table = utool.make_csv_table(column_list, column_lbls, header)
        return csv_table

    @default_decorator
    def get_table_csv_header(db, tablename):
        column_nametypes = zip(db.get_column_names(tablename), db.get_column_types(tablename))
        header_constraints = '# CONSTRAINTS: %r' % db.get_table_constraints(tablename)
        header_name  = '# TABLENAME: %r' % tablename
        header_types = utool.indentjoin(column_nametypes, '\n# ')
        header_doc = utool.indentjoin(utool.unindent(db.get_table_docstr(tablename)).split('\n'), '\n# ')
        header = header_doc + '\n' + header_name + header_types + '\n' + header_constraints
        return header

    def print_schema(db):
        for tablename in db.get_table_names():
            print(db.get_table_csv_header(tablename) + '\n')

    @default_decorator
    def get_sql_version(db):
        """ Conveinience """
        db.cur.execute('SELECT sqlite_version()')
        sql_version = db.cur.fetchone()
        print('[sql] SELECT sqlite_version = %r' % (sql_version,))
        # The version number sqlite3 module. NOT the version of SQLite library.
        print('[sql] sqlite3.version = %r' % (lite.version,))
        # The version of the SQLite library
        print('[sql] sqlite3.sqlite_version = %r' % (lite.sqlite_version,))
        return sql_version


# LONG DOCSTRS
#SQLDatabaseController.add_cleanly.__docstr__ = """
#uuid_list - a non-rowid column which identifies a row
#get_rowid_from_superkey - function which does what it says
#e.g:
#    get_rowid_from_superkey = ibs.get_image_gids_from_uuid
#    params_list = [(uuid.uuid4(),) for _ in range(7)]
#    superkey_paramx = [0]

#            params_list = [(uuid.uuid4(), 42) for _ in range(7)]
#            superkey_paramx = [0, 1]
#"""

#SQLDatabaseController.__init__.__docstr__ = """
#            SQLite3 Documentation: http://www.sqlite.org/docs.html
#            -------------------------------------------------------
#            SQL INSERT: http://www.w3schools.com/sql/sql_insert.asp
#            SQL UPDATE: http://www.w3schools.com/sql/sql_update.asp
#            SQL DELETE: http://www.w3schools.com/sql/sql_delete.asp
#            SQL SELECT: http://www.w3schools.com/sql/sql_select.asp
#            -------------------------------------------------------
#            Init the SQLite3 database connection and the execution object.
#            If the database does not exist, it will be automatically created
#            upon this object's instantiation.
#            """
#""" Same output as shell command below
#    > sqlite3 database.sqlite3 .dump > database.dump.txt

#    If file_=sys.stdout dumps to standard out

#    This saves the current database schema structure and data into a
#    text dump. The entire database can be recovered from this dump
#    file. The default will store a dump parallel to the current
#    database file.
#"""
#""" Commits staged changes to the database and saves the binary
#    representation of the database to disk.  All staged changes can be
#    commited one at a time or after a batch - which allows for batch
#    error handling without comprimising the integrity of the database.
#"""
#"""
#TODO: SEPARATE
#Input:
#    operation - an sql command to be executed e.g.
#        operation = '''
#        SELECT colname
#        FROM tblname
#        WHERE
#        (colname_1=?, ..., colname_N=?)
#        '''
#    params_iter - a sequence of params e.g.
#        params_iter = [(col1, ..., colN), ..., (col1, ..., colN),]
#Output:
#    results_iter - a sequence of data results
#"""
#"""
#operation - parameterized SQL operation string.
#    Parameterized prevents SQL injection attacks by using an ordered
#    representation ( ? ) or by using an ordered, text representation
#    name ( :value )

#params - list of values or a dictionary of representations and
#                corresponding values
#    * Ordered Representation -
#        List of values in the order the question marks appear in the
#        sql operation string
#    * Unordered Representation -
#        Dictionary of (text representation name -> value) in an
#        arbirtary order that will be filled into the cooresponging
#        slots of the sql operation string
#"""
#""" Creates a table in the database with some schema and constraints
#    schema_list - list of tablename columns tuples
#        {
#            (column_1_name, column_1_type),
#            (column_2_name, column_2_type),
#            ...
#            (column_N_name, column_N_type),
#        }
#    ---------------------------------------------
#    column_n_name - string name of column heading
#    column_n_type - NULL | INTEGER | REAL | TEXT | BLOB | NUMPY
#        The column type can be appended with ' PRIMARY KEY' to indicate
#        the unique id for the tablename.  It can also specify a default
#        value for the column with ' DEFAULT [VALUE]'.  It can also
#        specify ' NOT NULL' to indicate the column cannot be empty.
#    ---------------------------------------------
#    The tablename will only be created if it does not exist.  Therefore,
#    this can be done on every tablename without fear of deleting old data.
#    ---------------------------------------------
#    TODO: Add handling for column addition between software versions.
#    Column deletions will not be removed from the database schema.
#"""
