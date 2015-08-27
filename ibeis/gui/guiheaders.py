"""
This model provides the declarative interface to all of the api_*_models in
guitool. Each different type of model/view has to register its iders, getters,
and potentially setters (hopefully if guitool ever gets off the ground the
delters as well)

Different columns can be hidden / shown by modifying this file

TODO: need to cache the total number of annotations or something about
encounters on disk to help startuptime.
"""
from __future__ import absolute_import, division, print_function
from six.moves import zip, map, range
from ibeis import constants as const
import utool as ut
from functools import partial
#from ibeis.control import
(print, rrr, profile) = ut.inject2(__name__, '[headers]')

ENCOUNTER_TABLE  = const.ENCOUNTER_TABLE
IMAGE_TABLE      = const.IMAGE_TABLE
ANNOTATION_TABLE = const.ANNOTATION_TABLE
IMAGE_GRID       = 'image_grid'
NAME_TABLE       = 'names'
NAMES_TREE       = 'names_tree'
QRES_TABLE       = 'qres'
THUMB_TABLE      = 'thumbs'

#-----------------
# Define the tables
#-----------------


def make_table_declarations(ibs):
    """
    these used to be global variables, hopefully we can make them a little more configurable
    """
    # available tables
    TABLENAME_LIST = [
        IMAGE_TABLE,
        ANNOTATION_TABLE,
        #NAME_TABLE,
        ENCOUNTER_TABLE,
        IMAGE_GRID,
        THUMB_TABLE,
        NAMES_TREE
    ]

    # table nice names
    TABLE_NICE = {
        IMAGE_TABLE      : 'Image Table',
        ANNOTATION_TABLE : 'Annotations Table',
        NAME_TABLE       : 'Name Table',
        QRES_TABLE       : 'Query Results Table',
        ENCOUNTER_TABLE  : 'Encounter Table',
        IMAGE_GRID       : 'Thumbnail Grid',
        THUMB_TABLE      : 'Thumbnail Table',
        NAMES_TREE       : 'Tree of Names',
    }

    # COLUMN DEFINITIONS
    # the columns each ibeis table has,
    TABLE_COLNAMES = {
        IMAGE_TABLE     : [
            'gid',
            'thumb',
            #'nAids',
            'img_gname',
            #'ext',
            'reviewed',  # detection reviewed flag is not fullyused
            'datetime',
            'gps',
            'party_tag',
            'contributor_tag',
            #'gdconf',
            'imgnotes',
            'image_uuid',
        ],

        # debug with
        # --noannottbl
        # --nonametree
        # even just aid seems to be very slow
        ANNOTATION_TABLE       : [
            #'annotation_uuid',
            'aid',
            'thumb',
            'annot_gname',
            'name',
            'exemplar',
            'species',  # <put back in
            'yaw_text',
            'quality_text',
            #'rdconf',
            #'nGt',  # ## <put back in
            'annotnotes',  # ## <put back in
            #'annot_visual_uuid',
            #'annot_semantic_uuid',
            #'nFeats',
            #'bbox',
            #'theta',
            #'verts',
            #'num_verts',
        ],

        NAME_TABLE      : [
            'nid',
            'name',
            'nAids',
            'namenotes'
        ],

        QRES_TABLE      : [
            'rank',
            'score',
            'name',
            'aid'
        ],

        ENCOUNTER_TABLE : [
            #'eid',
            'enctext',
            'nImgs',
            #'num_imgs_reviewed',
            #'num_annotmatch_reviewed',
            #'encounter_end_datetime',
            # 'encounter_processed_flag',
            # 'encounter_shipped_flag',
        ],

        NAMES_TREE      : [
            'name',
            'nAids',
            'thumb',
            'nid',
            'exemplar',
            'nExAids',
            'aid',
            #'annot_gname',
            'yaw_text',
            'quality_text',
            'datetime',
            'max_hourdiff',
            'max_speed',
            'namenotes',
        ],

        IMAGE_GRID     : [
            'thumb',
        ],

        # TEST TABLE
        THUMB_TABLE     : [
            'img_gname',
            'thumb',
        ],


    }

    # dynamicly defined headers
    if not const.SIMPLIFY_INTERFACE:
        TABLE_COLNAMES[ENCOUNTER_TABLE].extend([
            'percent_annotmatch_reviewed_str',
            'percent_names_with_exemplar_str',
            #'percent_imgs_reviewed_str',
            'encounter_start_datetime',
        ])

    if ibs.cfg.other_cfg.show_shipped_encounters:
        TABLE_COLNAMES[ENCOUNTER_TABLE].extend([
            'encounter_processed_flag',
            'encounter_shipped_flag',
        ])

    #THUMB_TABLE     : ['thumb' 'thumb' 'thumb' 'thumb'],
    #NAMES_TREE      : {('name' 'nid' 'nAids') : ['aid' 'bbox' 'thumb']}

    TABLE_TREE_LEVELS = {
        NAMES_TREE :
        {
            'name': 0,
            'namenotes': 0,
            'nid': 0,
            'nAids': 0,
            'nExAids': 0,
            'exemplar': 1,
            'thumb': 1,
            'annot_gname': 1,
            'yaw_text': 1,
            'quality_text': 1,
            'aid': 1,
            'datetime': 1,
            'max_hourdiff': 0,
            'max_speed': 0,
        },
    }

    # the columns which are editable
    TABLE_EDITSET = {
        IMAGE_TABLE      : set(['reviewed', 'imgnotes']),
        ANNOTATION_TABLE : set(['name', 'species', 'annotnotes', 'exemplar', 'yaw', 'yaw_text', 'quality_text']),
        NAME_TABLE       : set(['name', 'namenotes']),
        QRES_TABLE       : set(['name']),
        ENCOUNTER_TABLE  : set(['enctext', 'encounter_shipped_flag', 'encounter_processed_flag']),
        IMAGE_GRID       : set([]),
        THUMB_TABLE      : set([]),
        NAMES_TREE       : set(['exemplar', 'name', 'namenotes', 'yaw', 'yaw_text', 'quality_text']),
    }

    if const.SIMPLIFY_INTERFACE:
        TABLE_EDITSET[NAMES_TREE].remove('name')

    TABLE_HIDDEN_LIST = {
        #IMAGE_TABLE      : [False, True, False, False, False, True, False, False, False, False, False],
        #ANNOTATION_TABLE : [False, False, False, False, False, False, False, True, True, True, True, True, True],
        #NAMES_TREE       : [False, False, False, False, False, False],
        #NAME_TABLE       : [False, False, False, False],
    }

    TABLE_STRIPE_LIST = {
        IMAGE_GRID : 9,
    }

    # Define the valid columns a table could have
    COL_DEF = dict([
        ('annot_semantic_uuid',  (str,      'Annot Semantic UUID')),
        ('annot_visual_uuid',    (str,      'Annot Visual UUID')),
        ('image_uuid',  (str,      'Image UUID')),
        ('gid',         (int,      'Image ID')),
        ('aid',         (int,      'Annotation ID')),
        ('nid',         (int,      'Name ID')),
        ('eid',         (int,      'Encounter ID')),
        ('nAids',       (int,      '#Annots')),
        ('nExAids',     (int,      '#Exemplars')),
        ('nGt',         (int,      '#GT')),
        ('nImgs',       (int,      '#Imgs')),
        ('nFeats',      (int,      '#Features')),
        ('quality_text',  (str,      'Quality')),
        ('rank',        (str,      'Rank')),  # needs to be a string for !Query
        ('unixtime',    (float,    'unixtime')),
        ('species',     (str,      'Species')),
        ('yaw',         (str,      'Yaws')),
        ('yaw_text',    (str,      'Viewpoint')),
        ('img_gname',   (str,      'Image Name')),
        ('annot_gname', (str,     'Source Image')),
        ('gdconf',      (str,      'Detection Confidence')),
        ('rdconf',      (float,    'Detection Confidence')),
        ('name',        (str,      'Name')),
        ('annotnotes',  (str,      'Annot Notes')),
        ('namenotes',   (str,      'Name Notes')),
        ('imgnotes',    (str,      'Image Notes')),
        ('match_name',  (str,      'Matching Name')),
        ('bbox',        (str,      'BBOX (x, y, w, h))')),  # Non editables are safe as strs
        ('num_verts',   (int,      'NumVerts')),
        ('verts',       (str,      'Verts')),
        ('score',       (str,      'Confidence')),
        ('theta',       (str,      'Theta')),
        ('reviewed',    (bool,     'Detection Reviewed')),
        ('exemplar',    (bool,     'Is Exemplar')),
        ('enctext',     (str,      'Encounter Text')),
        ('datetime',    (str,      'Date / Time')),
        ('ext',         (str,      'EXT')),
        ('thumb',       ('PIXMAP', 'Thumb')),
        ('gps',         (str,      'GPS')),
        ('encounter_processed_flag',       (bool,      'Processed')),
        ('encounter_shipped_flag',         (bool,      'Commited')),
        ('encounter_start_datetime',     (str,      'Start Time')),
        ('encounter_end_datetime',       (str,      'End Time')),
        ('party_tag', (str, 'Party')),
        ('contributor_tag', (str, 'Contributor')),
        ('percent_imgs_reviewed_str', (str, '%Imgs Reviewed')),
        ('percent_annotmatch_reviewed_str', (str, '%Queried')),
        ('num_imgs_reviewed', (str, '#Imgs Reviewed')),
        ('num_annotmatch_reviewed', (str, '#Matches Reviewed')),
        ('percent_names_with_exemplar_str', (str, '%Names with Exemplar')),
        ('max_speed', (float, 'Max Speed km/h')),
        ('max_hourdiff', (float, 'Max Hour Diff')),
    ])

    declare_tup = TABLENAME_LIST, TABLE_NICE, TABLE_COLNAMES, TABLE_TREE_LEVELS, TABLE_EDITSET, TABLE_HIDDEN_LIST, TABLE_STRIPE_LIST, COL_DEF
    return declare_tup

#----
# Define the special metadata for annotation


#def expand_special_colnames(annot_metadata):
#    global COL_DEF
#    for name, nice, valid in annot_metadata:
#        #TABLE_COLNAMES[ANNOTATION_TABLE]
#        if isinstance(valid, list):
#            type_ = str
#        else:
#            type_ = valid
#        COL_DEF[name] = (type_, nice)
#expand_special_colnames(const.ROSEMARY_ANNOT_METADATA)

#-----


#def get_redirects(ibs):
#    """
#        Allows one to specify a column in a particular table to redirect the view
#        to a different view (like a link in HTML to a different page)
#    """
#    redirects = {}
#    # Annotation redirects
#    # redirects[ANNOTATION_TABLE] = {
#    #     'annot_gname' : (IMAGE_TABLE, ibs.get_annot_gids),
#    # }
#    # Return the redirects dictionary
#    return redirects


def make_ibeis_headers_dict(ibs):
    declare_tup = make_table_declarations(ibs)
    TABLENAME_LIST, TABLE_NICE, TABLE_COLNAMES, TABLE_TREE_LEVELS, TABLE_EDITSET, TABLE_HIDDEN_LIST, TABLE_STRIPE_LIST, COL_DEF = declare_tup

    partial_imap_1to1 = ut.partial_imap_1to1
    #
    # Table Iders/Setters/Getters
    iders = {}
    setters = {}
    getters = {}
    widths = {}
    def infer_unspecified_getters(tablename, shortname):
        for colname in TABLE_COLNAMES[tablename]:
            if colname not in getters[tablename]:
                getters[tablename][colname] = getattr(ibs, 'get_' + shortname + '_' + colname)
                if ut.VERBOSE:
                    print('[guiheaders] infering %r' % (getters[tablename][colname],))
    # +--------------------------
    # Encounter Iders/Setters/Getters
    #ibs.cfg.other_cfg.ensure_attr(show_shipped_encounters, ut.is_developer())
    SHOW_SHIPPED_ENCOUNTERS = ibs.cfg.other_cfg.show_shipped_encounters
    #SHOW_SHIPPED_ENCOUNTERS = True
    if SHOW_SHIPPED_ENCOUNTERS:
        iders[ENCOUNTER_TABLE]   = [ibs.get_valid_eids]
    else:
        iders[ENCOUNTER_TABLE]   = [ partial(ibs.get_valid_eids, shipped=False)]

    getters[ENCOUNTER_TABLE] = {
        'eid'        : lambda eids: eids,
        'nImgs'      : ibs.get_encounter_num_gids,
        'enctext'    : ibs.get_encounter_text,
        'encounter_shipped_flag'     : ibs.get_encounter_shipped_flags,
        'encounter_processed_flag'   : ibs.get_encounter_processed_flags,
        #
        'encounter_start_datetime'   : partial_imap_1to1(ut.unixtime_to_datetimestr, ibs.get_encounter_start_time_posix),
        'encounter_end_datetime'     : partial_imap_1to1(ut.unixtime_to_datetimestr, ibs.get_encounter_end_time_posix),
        #
        'encounter_start_time_posix' : ibs.get_encounter_start_time_posix,
        'encounter_end_time_posix'   : ibs.get_encounter_end_time_posix,
    }
    infer_unspecified_getters(ENCOUNTER_TABLE, 'encounter')
    setters[ENCOUNTER_TABLE] = {
        'enctext'    : ibs.set_encounter_text,
        'encounter_shipped_flag'    : ibs.set_encounter_shipped_flags,
        'encounter_processed_flag'  : ibs.set_encounter_processed_flags,
    }
    widths[ENCOUNTER_TABLE] = {
        'nImgs': 55,
    }
    # +--------------------------
    # Image Iders/Setters/Getters
    iders[IMAGE_TABLE]   = [ibs.get_valid_gids]
    getters[IMAGE_TABLE] = {
        'gid'        : lambda gids: gids,
        'eid'        : ibs.get_image_eids,
        'enctext'    : partial_imap_1to1(ut.tupstr, ibs.get_image_enctext),
        'reviewed'   : ibs.get_image_reviewed,
        'img_gname'  : ibs.get_image_gnames,
        'nAids'      : ibs.get_image_num_annotations,
        'unixtime'   : ibs.get_image_unixtime,
        'datetime'   : ibs.get_image_datetime,
        'gdconf'     : ibs.get_image_detect_confidence,
        'imgnotes'   : ibs.get_image_notes,
        'image_uuid' : ibs.get_image_uuids,
        'ext'        : ibs.get_image_exts,
        'thumb'      : ibs.get_image_thumbtup,
        'gps'        : partial_imap_1to1(ut.tupstr, ibs.get_image_gps),
    }
    infer_unspecified_getters(IMAGE_TABLE, 'image')
    setters[IMAGE_TABLE] = {
        'reviewed'      : ibs.set_image_reviewed,
        'imgnotes'      : ibs.set_image_notes,
    }
    # +--------------------------
    # IMAGE GRID
    iders[IMAGE_GRID]   = [ibs.get_valid_gids]
    getters[IMAGE_GRID] = {
        'thumb'      : ibs.get_image_thumbtup,
        'img_gname'  : ibs.get_image_gnames,
        'aid'        : ibs.get_image_aids,
    }
    setters[IMAGE_GRID] = {
    }
    # +--------------------------
    # ANNOTATION Iders/Setters/Getters
    iders[ANNOTATION_TABLE]   = [ibs.get_valid_aids]
    getters[ANNOTATION_TABLE] = {
        'aid'                 : lambda aids: aids,
        'name'                : ibs.get_annot_names,
        'species'             : ibs.get_annot_species_texts,
        'yaw'                 : ibs.get_annot_yaws,
        'yaw_text'            : ibs.get_annot_yaw_texts,
        'quality_text'        : ibs.get_annot_quality_texts,
        'annot_gname'         : ibs.get_annot_image_names,
        'nGt'                 : ibs.get_annot_num_groundtruth,
        'theta'               : partial_imap_1to1(ut.theta_str, ibs.get_annot_thetas),
        'bbox'                : partial_imap_1to1(ut.bbox_str,  ibs.get_annot_bboxes),
        'num_verts'           : ibs.get_annot_num_verts,
        'verts'               : partial_imap_1to1(ut.verts_str, ibs.get_annot_verts),
        'nFeats'              : ibs.get_annot_num_feats,
        'rdconf'              : ibs.get_annot_detect_confidence,
        'annotnotes'          : ibs.get_annot_notes,
        'thumb'               : ibs.get_annot_chip_thumbtup,
        'exemplar'            : ibs.get_annot_exemplar_flags,
        'annot_visual_uuid'   : ibs.get_annot_visual_uuids,
        'annot_semantic_uuid' : ibs.get_annot_semantic_uuids,
        'datetime'            : ibs.get_annot_image_datetime,
    }
    setters[ANNOTATION_TABLE] = {
        'name'       : ibs.set_annot_names,
        'species'    : ibs.set_annot_species,
        'yaw'        : ibs.set_annot_yaws,
        'yaw_text'    : ibs.set_annot_yaw_texts,
        'annotnotes' : ibs.set_annot_notes,
        'exemplar'   : ibs.set_annot_exemplar_flags,
        'quality_text'    : ibs.set_annot_quality_texts,
    }
    # +--------------------------
    # Name Iders/Setters/Getters
    iders[NAME_TABLE]   = [ibs.get_valid_nids]
    getters[NAME_TABLE] = {
        'nid'        : lambda nids: nids,
        'name'       : ibs.get_name_texts,
        'nAids'      : ibs.get_name_num_annotations,
        'namenotes'  : ibs.get_name_notes,
    }
    setters[NAME_TABLE] = {
        'name'       : ibs.set_name_texts,
        'namenotes'  : ibs.set_name_notes,
    }
    # +--------------------------
    # NAMES TREE
    iders[NAMES_TREE]   = [ibs.get_valid_nids, ibs.get_name_aids]
    getters[NAMES_TREE] = {
        'nid'          : lambda nids: nids,
        'name'         : ibs.get_name_texts,
        'nAids'        : ibs.get_name_num_annotations,
        'nExAids'      : ibs.get_name_num_exemplar_annotations,
        'namenotes'    : ibs.get_name_notes,
        'aid'          : lambda aids: aids,
        'exemplar'     : ibs.get_annot_exemplar_flags,
        'thumb'        : ibs.get_annot_chip_thumbtup,
        'annot_gname'  : ibs.get_annot_image_names,
        'yaw_text'     : getters[ANNOTATION_TABLE]['yaw_text'],
        'quality_text' : getters[ANNOTATION_TABLE]['quality_text'],
        'datetime'     : getters[ANNOTATION_TABLE]['datetime'],
    }
    setters[NAMES_TREE] = {
        'name'       : ibs.set_name_texts,
        'namenotes'  : ibs.set_name_notes,
        'exemplar'     : setters[ANNOTATION_TABLE]['exemplar'],
        'yaw_text'     : setters[ANNOTATION_TABLE]['yaw_text'],
        'quality_text' : setters[ANNOTATION_TABLE]['quality_text'],
    }
    widths[NAMES_TREE] = {
        'thumb' : lambda: ibs.cfg.other_cfg.thumb_size,
        'nAids': 65,
        'nid': 50,
    }
    infer_unspecified_getters(NAMES_TREE, 'name')
    # +--------------------------
    # THUMB TABLE
    iders[THUMB_TABLE]   = [ibs.get_valid_gids]
    getters[THUMB_TABLE] = {
        'thumb'      : ibs.get_image_thumbtup,
        'img_gname'  : ibs.get_image_gnames,
        'aid'        : ibs.get_image_aids,
    }
    setters[THUMB_TABLE] = {
    }
    # L________________________

    def make_header(tblname):
        """
        Args:
            table_name - the internal table name
        """
        tblnice    = TABLE_NICE[tblname]
        colnames   = TABLE_COLNAMES[tblname]
        editset    = TABLE_EDITSET[tblname]
        tblgetters = getters[tblname]
        tblsetters = setters[tblname]
        #if levels aren't found, we're not dealing with a tree, so everything is at level 0
        collevel_dict = TABLE_TREE_LEVELS.get(tblname, ut.ddict(lambda: 0))
        collevels  = [collevel_dict[colname] for colname in colnames]
        hiddencols = TABLE_HIDDEN_LIST.get(tblname, [False for _ in range(len(colnames))])
        numstripes = TABLE_STRIPE_LIST.get(tblname, 1)

        colwidths_dict = widths.get(tblname, {})
        colwidths = [colwidths_dict.get(colname, 100) for colname in colnames]

        def get_column_data(colname):
            try:
                coldef_tup = COL_DEF[colname]
                coltype, colnice = coldef_tup
            except KeyError as ex:
                strict = False
                ut.printex(ex, 'Need to add type info for colname=%r to COL_DEF'
                           % colname, iswarning=not strict)
                if strict:
                    raise
                else:
                    # default coldef to give a string type and nice=colname
                    coltype, colnice = (str, colname)
            coledit   = colname in editset
            colgetter = tblgetters[colname]
            colsetter = None if not coledit else tblsetters.get(colname, None)
            return (coltype, colnice, coledit, colgetter, colsetter)
        try:
            _tuplist = list(zip(*list(map(get_column_data, colnames))))
            (coltypes, colnices, coledits, colgetters, colsetters) = _tuplist
        except KeyError as ex:
            ut.printex(ex,  key_list=['tblname', 'colnames'])
            raise
        header = {
            'name'            : tblname,
            'nice'            : tblnice,
            'iders'           : iders[tblname],
            'col_name_list'   : colnames,
            'col_type_list'   : coltypes,
            'col_nice_list'   : colnices,
            'col_edit_list'   : coledits,
            'col_getter_list' : colgetters,
            'col_setter_list' : colsetters,
            'col_level_list'  : collevels,
            'col_hidden_list' : hiddencols,
            'num_duplicates'  : numstripes,
            'get_thumb_size'  : lambda: ibs.cfg.other_cfg.thumb_size,
            'col_width_list'  : colwidths,  # TODO
        }
        return header

    header_dict = {tblname: make_header(tblname) for tblname in TABLENAME_LIST}
    return header_dict, declare_tup
