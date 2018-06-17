# -*- coding: utf-8 -*-
"""
Dependencies: flask, tornado
"""
from __future__ import absolute_import, division, print_function
from flask import request, redirect, url_for, current_app
from ibeis.control import controller_inject
from ibeis.web import appfuncs as appf
from ibeis import constants as const
import utool as ut
import numpy as np
import uuid
import six


register_route = controller_inject.get_ibeis_flask_route(__name__)


@register_route('/submit/login/', methods=['POST'], __route_authenticate__=False)
def submit_login(name, organization, refer=None, *args, **kwargs):
    # Return HTML
    if refer is None:
        refer = url_for('root')
    else:
        refer = appf.decode_refer_url(refer)

    if name == '_new_':
        first = kwargs['new_name_first']
        last = kwargs['new_name_last']
        name = '%s.%s' % (first, last, )
        name = name.replace(' ', '')

    if organization == '_new_':
        organization = kwargs['new_organization']
        organization = organization.replace(' ', '')

    name = name.lower()
    organization = organization.lower()

    username = '%s@%s' % (name, organization, )
    controller_inject.authenticate(username=username, name=name,
                                   organization=organization)

    return redirect(refer)


@register_route('/submit/cameratrap/', methods=['POST'])
def submit_cameratrap(**kwargs):
    ibs = current_app.ibs
    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)

    gid = int(request.form['cameratrap-gid'])
    user_id = controller_inject.get_user().get('username', None)
    flag = request.form.get('cameratrap-toggle', 'off') == 'on'
    ibs.set_image_cameratrap([gid], [flag])
    print('[web] user_id: %s, gid: %d, flag: %r' % (user_id, gid, flag, ))

    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_cameratrap', imgsetid=imgsetid, previous=gid))


@register_route('/submit/detection/', methods=['POST'])
def submit_detection(**kwargs):
    is_staged = kwargs.get('staged', False)

    ibs = current_app.ibs
    method = request.form.get('detection-submit', '')
    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)
    gid = int(request.form['detection-gid'])
    user_id = controller_inject.get_user().get('username', None)

    poor_boxes = method.lower() == 'poor boxes'
    if poor_boxes:
        imgsetid_ = ibs.get_imageset_imgsetids_from_text('POOR BOXES')
        ibs.set_image_imgsetids([gid], [imgsetid_])
        method = 'accept'

    if method.lower() == 'delete':
        # ibs.delete_images(gid)
        # print('[web] (DELETED) user_id: %s, gid: %d' % (user_id, gid, ))
        pass
    elif method.lower() == 'clear':
        aid_list = ibs.get_image_aids(gid)
        ibs.delete_annots(aid_list)
        print('[web] (CLEAERED) user_id: %s, gid: %d' % (user_id, gid, ))
        redirection = request.referrer
        if 'gid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&gid=%d' % (redirection, gid, )
            else:
                redirection = '%s?gid=%d' % (redirection, gid, )
        return redirect(redirection)
    elif method.lower() == 'rotate left':
        ibs.update_image_rotate_left_90([gid])
        print('[web] (ROTATED LEFT) user_id: %s, gid: %d' % (user_id, gid, ))
        redirection = request.referrer
        if 'gid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&gid=%d' % (redirection, gid, )
            else:
                redirection = '%s?gid=%d' % (redirection, gid, )
        return redirect(redirection)
    elif method.lower() == 'rotate right':
        ibs.update_image_rotate_right_90([gid])
        print('[web] (ROTATED RIGHT) user_id: %s, aid: %d' % (user_id, gid, ))
        redirection = request.referrer
        if 'gid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&gid=%d' % (redirection, gid, )
            else:
                redirection = '%s?gid=%d' % (redirection, gid, )
        return redirect(redirection)
    else:
        current_aid_list = ibs.get_image_aids(gid, is_staged=is_staged)
        current_part_rowid_list = ut.flatten(ibs.get_annot_part_rowids(current_aid_list, is_staged=is_staged))

        if is_staged:
            staged_uuid = uuid.uuid4()
            staged_user = controller_inject.get_user()
            staged_user_id = staged_user.get('username', None)

            # Filter aids for current user
            current_annot_user_id_list = ibs.get_annot_staged_user_ids(current_aid_list)
            current_aid_list = [
                current_aid
                for current_aid, current_annot_user_id in zip(current_aid_list, current_annot_user_id_list)
                if current_annot_user_id == staged_user_id
            ]

            # Filter part_rowids for current user
            current_part_user_id_list = ibs.get_part_staged_user_ids(current_part_rowid_list)
            current_part_rowid_list = [
                current_part_rowid
                for current_part_rowid, current_part_user_id in zip(current_part_rowid_list, current_part_user_id_list)
                if current_part_user_id == staged_user_id
            ]
        else:
            staged_uuid = None
            staged_user = None
            staged_user_id = None

        # Make new annotations
        width, height = ibs.get_image_sizes(gid)

        # Separate out annotations vs parts
        data_list = ut.from_json(request.form['ia-detection-data'])
        print(request.form['ia-detection-manifest'])
        raw_manifest = request.form['ia-detection-manifest'].strip()
        try:
            manifest_list = ut.from_json(raw_manifest)
        except ValueError:
            manifest_list = []
        test_truth = len(manifest_list) > 0
        test_challenge_list = [{
            'gid'           : gid,
            'manifest_list' : manifest_list,
        }]
        test_response_list = [{
            'poor_boxes'    : poor_boxes,
        }]
        test_result_list = [test_truth == poor_boxes]
        test_user_id_list = [None]
        ibs.add_test(test_challenge_list, test_response_list,
                     test_result_list=test_result_list,
                     test_user_identity_list=test_user_id_list)

        if not test_truth:
            annotation_list = []
            part_list = []
            mapping_dict = {}
            for outer_index, data in enumerate(data_list):
                # Check for invalid NaN boxes, filter them out
                try:
                    assert data['percent']['left']   is not None
                    assert data['percent']['top']    is not None
                    assert data['percent']['width']  is not None
                    assert data['percent']['height'] is not None
                except:
                    continue

                parent_index = data['parent']
                if parent_index is None:
                    inner_index = len(annotation_list)
                    annotation_list.append(data)
                    mapping_dict[outer_index] = inner_index
                else:
                    assert parent_index in mapping_dict
                    part_list.append(data)

            ##################################################################################
            # Get primatives
            bbox_list = [
                (
                    int(np.round(width  * (annot['percent']['left']   / 100.0) )),
                    int(np.round(height * (annot['percent']['top']    / 100.0) )),
                    int(np.round(width  * (annot['percent']['width']  / 100.0) )),
                    int(np.round(height * (annot['percent']['height'] / 100.0) )),
                )
                for annot in annotation_list
            ]
            theta_list = [
                float(annot['angles']['theta'])
                for annot in annotation_list
            ]

            # Get metadata
            viewpoint1_list = [
                int(annot['metadata'].get('viewpoint1', -1))
                for annot in annotation_list
            ]
            viewpoint2_list = [
                int(annot['metadata'].get('viewpoint2', -1))
                for annot in annotation_list
            ]
            viewpoint3_list = [
                int(annot['metadata'].get('viewpoint3', -1))
                for annot in annotation_list
            ]
            zipped = zip(viewpoint1_list, viewpoint2_list, viewpoint3_list)
            viewpoint_list = [ appf.convert_tuple_to_viewpoint(tup) for tup in zipped ]

            quality_list = [
                int(annot['metadata'].get('quality', 0))
                for annot in annotation_list
            ]
            # Fix qualities
            for index, quality in enumerate(quality_list):
                if quality == 0:
                    quality_list[index] = None
                elif quality == 1:
                    quality_list[index] = 2
                elif quality == 2:
                    quality_list[index] = 4
                else:
                    raise ValueError('quality must be 0, 1 or 2')

            multiple_list =  [
                annot['metadata'].get('multiple', False)
                for annot in annotation_list
            ]
            interest_list =  [
                annot['highlighted']
                for annot in annotation_list
            ]
            species_list = [
                annot['metadata'].get('species', const.UNKNOWN)
                for annot in annotation_list
            ]

            # Process annotations
            survived_aid_list = [
                None if annot['label'] in [None, 'None'] else int(annot['label'])
                for annot in annotation_list
            ]

            # Delete annotations that didn't survive
            kill_aid_list = list(set(current_aid_list) - set(survived_aid_list))
            ibs.delete_annots(kill_aid_list)

            staged_uuid_list = [staged_uuid] * len(survived_aid_list)
            staged_user_id_list = [staged_user_id] * len(survived_aid_list)

            aid_list = []
            zipped = zip(survived_aid_list, bbox_list, staged_uuid_list, staged_user_id_list)
            for aid, bbox, staged_uuid, staged_user_id in zipped:
                staged_uuid_list_ = None if staged_uuid is None else [staged_uuid]
                staged_user_id_list_ = None if staged_user_id is None else [staged_user_id]

                if aid is None:
                    aid_ = ibs.add_annots([gid], [bbox],
                                          staged_uuid_list=staged_uuid_list_,
                                          staged_user_id_list=staged_user_id_list_)
                    aid_ = aid_[0]
                else:
                    ibs.set_annot_bboxes([aid], [bbox])
                    if staged_uuid_list_ is not None:
                        ibs.set_annot_staged_uuids([aid], staged_uuid_list_)
                    if staged_user_id_list_ is not None:
                        ibs.set_annot_staged_user_ids([aid], staged_user_id_list_)
                    aid_ = aid
                aid_list.append(aid_)

            print('aid_list = %r' % (aid_list, ))
            # Set annotation metadata
            ibs.set_annot_thetas(aid_list, theta_list)
            ibs.set_annot_viewpoints(aid_list, viewpoint_list)
            # TODO ibs.set_annot_viewpoint_code(aid_list, viewpoint_list)
            ibs.set_annot_qualities(aid_list, quality_list)
            ibs.set_annot_multiple(aid_list, multiple_list)
            ibs.set_annot_interest(aid_list, interest_list)
            ibs.set_annot_species(aid_list, species_list)

            # Set the mapping dict to use aids now
            mapping_dict = { key: aid_list[index] for key, index in mapping_dict.items() }

            ##################################################################################
            # Process parts
            survived_part_rowid_list = [
                None if part['label'] is None else int(part['label'])
                for part in part_list
            ]

            # Get primatives
            aid_list = [
                mapping_dict[part['parent']]
                for part in part_list
            ]
            bbox_list = [
                (
                    int(np.round(width  * (part['percent']['left']   / 100.0) )),
                    int(np.round(height * (part['percent']['top']    / 100.0) )),
                    int(np.round(width  * (part['percent']['width']  / 100.0) )),
                    int(np.round(height * (part['percent']['height'] / 100.0) )),
                )
                for part in part_list
            ]
            theta_list = [
                float(part['angles']['theta'])
                for part in part_list
            ]

            # Get metadata
            viewpoint1_list = [
                int(part['metadata'].get('viewpoint1', -1))
                for part in part_list
            ]
            viewpoint2_list = [-1] * len(part_list)
            viewpoint3_list = [-1] * len(part_list)
            zipped = zip(viewpoint1_list, viewpoint2_list, viewpoint3_list)
            viewpoint_list = [ appf.convert_tuple_to_viewpoint(tup) for tup in zipped ]

            quality_list = [
                int(part['metadata'].get('quality', 0))
                for part in part_list
            ]
            # Fix qualities
            for index, quality in enumerate(quality_list):
                if quality == 0:
                    quality_list[index] = None
                elif quality == 1:
                    quality_list[index] = 2
                elif quality == 2:
                    quality_list[index] = 4
                else:
                    raise ValueError('quality must be 0, 1 or 2')

            type_list = [
                part['metadata'].get('type', const.UNKNOWN)
                for part in part_list
            ]

            # Delete annotations that didn't survive
            kill_part_rowid_list = list(set(current_part_rowid_list) - set(survived_part_rowid_list))
            ibs.delete_parts(kill_part_rowid_list)

            staged_uuid_list = [staged_uuid] * len(survived_part_rowid_list)
            staged_user_id_list = [staged_user_id] * len(survived_part_rowid_list)

            part_rowid_list = []
            zipped = zip(survived_part_rowid_list, aid_list, bbox_list, staged_uuid_list, staged_user_id_list)
            for part_rowid, aid, bbox, staged_uuid, staged_user_id in zipped:
                staged_uuid_list_ = None if staged_uuid is None else [staged_uuid]
                staged_user_id_list_ = None if staged_user_id is None else [staged_user_id]

                if part_rowid is None:
                    part_rowid_ = ibs.add_parts([aid], [bbox],
                                                staged_uuid_list=staged_uuid_list_,
                                                staged_user_id_list=staged_user_id_list_)
                    part_rowid_ = part_rowid_[0]
                else:
                    ibs._set_part_aid([part_rowid], [aid])
                    ibs.set_part_bboxes([part_rowid], [bbox])
                    if staged_uuid_list_ is not None:
                        ibs.set_part_staged_uuids([part_rowid], staged_uuid_list_)
                    if staged_user_id_list_ is not None:
                        ibs.set_part_staged_user_ids([part_rowid], staged_user_id_list_)

                    part_rowid_ = part_rowid
                part_rowid_list.append(part_rowid_)

            # Set part metadata
            print('part_rowid_list = %r' % (part_rowid_list, ))
            ibs.set_part_thetas(part_rowid_list, theta_list)
            ibs.set_part_viewpoints(part_rowid_list, viewpoint_list)
            ibs.set_part_qualities(part_rowid_list, quality_list)
            ibs.set_part_types(part_rowid_list, type_list)

            # Set image reviewed flag
            if is_staged:
                metadata_dict = ibs.get_image_metadata(gid)
                if 'staged' not in metadata_dict:
                    metadata_dict['staged'] = {
                        'sessions': {
                            'uuids': [],
                            'user_ids': [],
                        }
                    }
                metadata_dict['staged']['sessions']['uuids'].append(str(staged_uuid))
                metadata_dict['staged']['sessions']['user_ids'].append(staged_user_id)
                ibs.set_image_metadata([gid], [metadata_dict])
            else:
                ibs.set_image_reviewed([gid], [1])

            print('[web] user_id: %s, gid: %d, annots: %d, parts: %d' % (user_id, gid, len(annotation_list), len(part_list), ))

    default_list = [
        'autointerest',
        'interest_bypass',
        'metadata',
        'metadata_viewpoint',
        'metadata_quality',
        'metadata_flags',
        'metadata_flags_aoi',
        'metadata_flags_multiple',
        'metadata_species',
        'metadata_label',
        'metadata_quickhelp',
        'parts',
        'modes_rectangle',
        'modes_diagonal',
        'modes_diagonal2',
        'staged',
    ]
    config = {
        default: kwargs[default]
        for default in default_list
        if default in kwargs
    }

    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_detection', imgsetid=imgsetid, previous=gid, **config))


@register_route('/submit/viewpoint/', methods=['POST'])
def submit_viewpoint(**kwargs):
    ibs = current_app.ibs
    method = request.form.get('viewpoint-submit', '')
    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)

    src_ag = request.args.get('src_ag', '')
    src_ag = None if src_ag == 'None' or src_ag == '' else int(src_ag)
    dst_ag = request.args.get('dst_ag', '')
    dst_ag = None if dst_ag == 'None' or dst_ag == '' else int(dst_ag)

    aid = int(request.form['viewpoint-aid'])
    user_id = controller_inject.get_user().get('username', None)
    if method.lower() == 'delete':
        ibs.delete_annots(aid)
        print('[web] (DELETED) user_id: %s, aid: %d' % (user_id, aid, ))
        aid = None  # Reset AID to prevent previous
    if method.lower() == 'make junk':
        ibs.set_annot_quality_texts([aid], [const.QUAL_JUNK])
        print('[web] (SET AS JUNK) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    if method.lower() == 'rotate left':
        ibs.update_annot_rotate_left_90([aid])
        print('[web] (ROTATED LEFT) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    if method.lower() == 'rotate right':
        ibs.update_annot_rotate_right_90([aid])
        print('[web] (ROTATED RIGHT) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    else:
        if src_ag is not None and dst_ag is not None:
            appf.movegroup_aid(ibs, aid, src_ag, dst_ag)
        viewpoint = int(request.form['viewpoint-value'])
        viewpoint_text = appf.VIEWPOINT_MAPPING.get(viewpoint, None)
        species_text = request.form['viewpoint-species']
        ibs.set_annot_viewpoints([aid], [viewpoint_text])
        # TODO ibs.set_annot_viewpoint_code([aid], [viewpoint_text])
        ibs.set_annot_species([aid], [species_text])
        print('[web] user_id: %s, aid: %d, viewpoint_text: %s' % (user_id, aid, viewpoint_text))
    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_viewpoint', imgsetid=imgsetid, src_ag=src_ag,
                                dst_ag=dst_ag, previous=aid))


@register_route('/submit/viewpoint2/', methods=['POST'])
def submit_viewpoint2(**kwargs):
    ibs = current_app.ibs
    method = request.form.get('viewpoint-submit', '')
    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)

    src_ag = request.args.get('src_ag', '')
    src_ag = None if src_ag == 'None' or src_ag == '' else int(src_ag)
    dst_ag = request.args.get('dst_ag', '')
    dst_ag = None if dst_ag == 'None' or dst_ag == '' else int(dst_ag)

    aid = int(request.form['viewpoint-aid'])
    user_id = controller_inject.get_user().get('username', None)
    if method.lower() == 'delete':
        ibs.delete_annots(aid)
        print('[web] (DELETED) user_id: %s, aid: %d' % (user_id, aid, ))
        aid = None  # Reset AID to prevent previous
    if method.lower() == 'make junk':
        ibs.set_annot_quality_texts([aid], [const.QUAL_JUNK])
        print('[web] (SET AS JUNK) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    if method.lower() == 'rotate left':
        ibs.update_annot_rotate_left_90([aid])
        print('[web] (ROTATED LEFT) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    if method.lower() == 'rotate right':
        ibs.update_annot_rotate_right_90([aid])
        print('[web] (ROTATED RIGHT) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    else:
        if src_ag is not None and dst_ag is not None:
            appf.movegroup_aid(ibs, aid, src_ag, dst_ag)
        if method.lower() == 'ignore':
            viewpoint = 'unknown'
        else:
            # Get metadata
            viewpoint1 = int(kwargs.get('ia-viewpoint-value-1', None))
            viewpoint2 = int(kwargs.get('ia-viewpoint-value-2', None))
            viewpoint3 = int(kwargs.get('ia-viewpoint-value-3', None))
            viewpoint_tup = (viewpoint1, viewpoint2, viewpoint3, )
            viewpoint = appf.convert_tuple_to_viewpoint(viewpoint_tup)
        ibs.set_annot_viewpoints([aid], [viewpoint])
        species_text = request.form['viewpoint-species']
        # TODO ibs.set_annot_viewpoint_code([aid], [viewpoint_text])
        ibs.set_annot_species([aid], [species_text])
        print('[web] user_id: %s, aid: %d, viewpoint_text: %s' % (user_id, aid, viewpoint))
    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_viewpoint2', imgsetid=imgsetid, src_ag=src_ag,
                                dst_ag=dst_ag, previous=aid))


@register_route('/submit/viewpoint3/', methods=['POST'])
def submit_viewpoint3(**kwargs):
    with ut.Timer('[submit_viewpoint3]'):
        ibs = current_app.ibs
        method = request.form.get('viewpoint-submit', '')
        imgsetid = request.args.get('imgsetid', '')
        imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)

        src_ag = request.args.get('src_ag', '')
        src_ag = None if src_ag == 'None' or src_ag == '' else int(src_ag)
        dst_ag = request.args.get('dst_ag', '')
        dst_ag = None if dst_ag == 'None' or dst_ag == '' else int(dst_ag)

        aid = int(request.form['viewpoint-aid'])
        user_id = controller_inject.get_user().get('username', None)

        if method.lower() == 'delete':
            ibs.delete_annots(aid)
            print('[web] (DELETED) user_id: %s, aid: %d' % (user_id, aid, ))
            aid = None  # Reset AID to prevent previous
        if method.lower() == 'make junk':
            ibs.set_annot_quality_texts([aid], [const.QUAL_JUNK])
            print('[web] (SET AS JUNK) user_id: %s, aid: %d' % (user_id, aid, ))
            redirection = request.referrer
            if 'aid' not in redirection:
                # Prevent multiple clears
                if '?' in redirection:
                    redirection = '%s&aid=%d' % (redirection, aid, )
                else:
                    redirection = '%s?aid=%d' % (redirection, aid, )
            return redirect(redirection)
        if method.lower() == 'rotate left':
            ibs.update_annot_rotate_left_90([aid])
            print('[web] (ROTATED LEFT) user_id: %s, aid: %d' % (user_id, aid, ))
            redirection = request.referrer
            if 'aid' not in redirection:
                # Prevent multiple clears
                if '?' in redirection:
                    redirection = '%s&aid=%d' % (redirection, aid, )
                else:
                    redirection = '%s?aid=%d' % (redirection, aid, )
            return redirect(redirection)
        if method.lower() == 'rotate right':
            ibs.update_annot_rotate_right_90([aid])
            print('[web] (ROTATED RIGHT) user_id: %s, aid: %d' % (user_id, aid, ))
            redirection = request.referrer
            if 'aid' not in redirection:
                # Prevent multiple clears
                if '?' in redirection:
                    redirection = '%s&aid=%d' % (redirection, aid, )
                else:
                    redirection = '%s?aid=%d' % (redirection, aid, )
            return redirect(redirection)
        else:
            if src_ag is not None and dst_ag is not None:
                appf.movegroup_aid(ibs, aid, src_ag, dst_ag)

            if method.lower() == 'ignore':
                ibs.set_annot_viewpoints([aid], ['ignore'], only_allow_known=False, _code_update=False)
                viewpoint = 'ignore'
            else:
                # Get metadata
                viewpoint_str = kwargs.get('viewpoint-text-code', '')
                if not isinstance(viewpoint_str, six.string_types) or len(viewpoint_str) == 0:
                    viewpoint_str = None

                if viewpoint_str is None:
                    viewpoint = const.VIEW.UNKNOWN
                else:
                    viewpoint = getattr(const.VIEW, viewpoint_str, const.VIEW.UNKNOWN)
                ibs.set_annot_viewpoint_int([aid], [viewpoint])

            species_text = request.form['viewpoint-species']
            ibs.set_annot_species([aid], [species_text])
            ibs.set_annot_reviewed([aid], [1])
            print('[web] user_id: %s, aid: %d, viewpoint: %s' % (user_id, aid, viewpoint))

        # Return HTML
        refer = request.args.get('refer', '')
        if len(refer) > 0:
            retval = redirect(appf.decode_refer_url(refer))
        else:
            retval = redirect(url_for('turk_viewpoint3', imgsetid=imgsetid, src_ag=src_ag,
                                      dst_ag=dst_ag, previous=aid))

    return retval


@register_route('/submit/annotation/', methods=['POST'])
def submit_annotation(**kwargs):
    ibs = current_app.ibs
    method = request.form.get('ia-annotation-submit', '')
    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)

    src_ag = request.args.get('src_ag', '')
    src_ag = None if src_ag == 'None' or src_ag == '' else int(src_ag)
    dst_ag = request.args.get('dst_ag', '')
    dst_ag = None if dst_ag == 'None' or dst_ag == '' else int(dst_ag)

    aid = int(request.form['ia-annotation-aid'])
    user_id = controller_inject.get_user().get('username', None)
    if method.lower() == 'delete':
        ibs.delete_annots(aid)
        print('[web] (DELETED) user_id: %s, aid: %d' % (user_id, aid, ))
        aid = None  # Reset AID to prevent previous
    elif method.lower() == 'make junk':
        ibs.set_annot_quality_texts([aid], [const.QUAL_JUNK])
        print('[web] (SET AS JUNK) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    elif method.lower() == u'rotate left':
        ibs.update_annot_rotate_left_90([aid])
        print('[web] (ROTATED LEFT) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    elif method.lower() == u'rotate right':
        ibs.update_annot_rotate_right_90([aid])
        print('[web] (ROTATED RIGHT) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    else:
        if src_ag is not None and dst_ag is not None:
            appf.movegroup_aid(ibs, aid, src_ag, dst_ag)
        try:
            viewpoint = int(request.form['ia-annotation-viewpoint-value'])
        except ValueError:
            viewpoint = int(float(request.form['ia-annotation-viewpoint-value']))
        viewpoint_text = appf.VIEWPOINT_MAPPING.get(viewpoint, None)
        species_text = request.form['ia-annotation-species']
        try:
            quality = int(request.form['ia-quality-value'])
        except ValueError:
            quality = int(float(request.form['ia-quality-value']))
        if quality in [-1, None]:
            quality = None
        elif quality == 0:
            quality = 2
        elif quality == 1:
            quality = 4
        else:
            raise ValueError('quality must be -1, 0 or 1')
        ibs.set_annot_viewpoints([aid], [viewpoint_text])
        # TODO ibs.set_annot_viewpoint_code([aid], [viewpoint_text])
        ibs.set_annot_species([aid], [species_text])
        ibs.set_annot_qualities([aid], [quality])
        multiple = 1 if 'ia-multiple-value' in request.form else 0
        ibs.set_annot_multiple([aid], [multiple])
        ibs.set_annot_reviewed([aid], [1])
        print('[web] user_id: %s, aid: %d, viewpoint: %r, quality: %r, multiple: %r' % (user_id, aid, viewpoint_text, quality, multiple))
    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_annotation', imgsetid=imgsetid, src_ag=src_ag,
                                dst_ag=dst_ag, previous=aid))


@register_route('/submit/annotation/grid/', methods=['POST'])
def submit_annotation_grid(samples=200, species='zebra_grevys', version=1, **kwargs):
    ibs = current_app.ibs

    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)

    assert version in [1, 2, 3]

    aid_list = kwargs['annotation-grid-aids']
    highlight_list = kwargs['annotation-grid-highlighted']
    assert len(aid_list) == len(highlight_list)

    metadata_list = ibs.get_annot_metadata(aid_list)
    metadata_list_ = []
    for metadata, highlight in zip(metadata_list, highlight_list):
        if 'turk' not in metadata:
            metadata['turk'] = {}

        if version == 1:
            value = highlight
        elif version == 2:
            value = not highlight
        elif version == 3:
            value = highlight

        metadata['turk']['grid'] = value
        metadata_list_.append(metadata)

    ibs.set_annot_metadata(aid_list, metadata_list_)

    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_annotation_grid',
                                imgsetid=imgsetid,
                                samples=samples, species=species,
                                version=version))


@register_route('/submit/splits/', methods=['POST'])
def submit_splits(**kwargs):
    ibs = current_app.ibs

    aid_list = kwargs['annotation-splits-aids']
    highlight_list = kwargs['annotation-splits-highlighted']
    assert len(aid_list) == len(highlight_list)

    ut.embed()

    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_splits', aid=None))


@register_route('/submit/species/', methods=['POST'])
def submit_species(**kwargs):
    ibs = current_app.ibs

    method = request.form.get('ia-species-submit', '')
    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)

    previous_species_rowids = request.form.get('ia-species-rowids', None)
    print('Using previous_species_rowids = %r' % (previous_species_rowids, ))

    src_ag = request.args.get('src_ag', '')
    src_ag = None if src_ag == 'None' or src_ag == '' else int(src_ag)
    dst_ag = request.args.get('dst_ag', '')
    dst_ag = None if dst_ag == 'None' or dst_ag == '' else int(dst_ag)

    aid = int(request.form['ia-species-aid'])
    user_id = controller_inject.get_user().get('username', None)
    if method.lower() == 'delete':
        ibs.delete_annots(aid)
        print('[web] (DELETED) user_id: %s, aid: %d' % (user_id, aid, ))
        aid = None  # Reset AID to prevent previous
    elif method.lower() == u'skip':
        print('[web] (SKIP) user_id: %s' % (user_id, ))
        return redirect(url_for('turk_species', imgsetid=imgsetid, src_ag=src_ag,
                                dst_ag=dst_ag, previous=aid,
                                previous_species_rowids=previous_species_rowids))
    elif method.lower() in u'refresh':
        print('[web] (REFRESH) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        if '?' in redirection:
            redirection = '%s&refresh=true' % (redirection, )
        else:
            redirection = '%s?refresh=true' % (redirection, )
        return redirect(redirection)
    elif method.lower() == u'rotate left':
        ibs.update_annot_rotate_left_90([aid])
        print('[web] (ROTATED LEFT) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    elif method.lower() == u'rotate right':
        ibs.update_annot_rotate_right_90([aid])
        print('[web] (ROTATED RIGHT) user_id: %s, aid: %d' % (user_id, aid, ))
        redirection = request.referrer
        if 'aid' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&aid=%d' % (redirection, aid, )
            else:
                redirection = '%s?aid=%d' % (redirection, aid, )
        return redirect(redirection)
    else:
        if src_ag is not None and dst_ag is not None:
            appf.movegroup_aid(ibs, aid, src_ag, dst_ag)
        # species_text = request.form['ia-species-species']
        species_text = kwargs.get('ia-species-value', '')
        if len(species_text) == 0:
            species_text = const.UNKNOWN
        ibs.set_annot_species([aid], [species_text])
        ibs.set_annot_reviewed([aid], [1])

        metadata_dict = ibs.get_annot_metadata(aid)
        if 'turk' not in metadata_dict:
            metadata_dict['turk'] = {}
        metadata_dict['turk']['species'] = user_id
        ibs.set_annot_metadata([aid], [metadata_dict])

        print('[web] user_id: %s, aid: %d, species: %r (%r)'  % (user_id, aid, species_text, metadata_dict, ))
    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_species', imgsetid=imgsetid, src_ag=src_ag,
                                dst_ag=dst_ag, previous=aid,
                                previous_species_rowids=previous_species_rowids))


@register_route('/submit/quality/', methods=['POST'])
def submit_quality(**kwargs):
    ibs = current_app.ibs
    method = request.form.get('quality-submit', '')
    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)
    aid = int(request.form['quality-aid'])
    user_id = controller_inject.get_user().get('username', None)

    src_ag = request.args.get('src_ag', '')
    src_ag = None if src_ag == 'None' or src_ag == '' else int(src_ag)
    dst_ag = request.args.get('dst_ag', '')
    dst_ag = None if dst_ag == 'None' or dst_ag == '' else int(dst_ag)

    if method.lower() == 'delete':
        ibs.delete_annots(aid)
        print('[web] (DELETED) user_id: %s, aid: %d' % (user_id, aid, ))
        aid = None  # Reset AID to prevent previous
    else:
        if src_ag is not None and dst_ag is not None:
            appf.movegroup_aid(ibs, aid, src_ag, dst_ag)
        quality = int(request.form['quality-value'])
        ibs.set_annot_qualities([aid], [quality])
        print('[web] user_id: %s, aid: %d, quality: %d' % (user_id, aid, quality))
    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_quality', imgsetid=imgsetid, src_ag=src_ag,
                                dst_ag=dst_ag, previous=aid))


@register_route('/submit/demographics/', methods=['POST'])
def submit_demographics(species='zebra_grevys', **kwargs):
    ibs = current_app.ibs

    DAN_SPECIAL_WRITE_AGE_TO_ALL_ANOTATIONS = True

    method = request.form.get('demographics-submit', '')
    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)
    aid = int(request.form['demographics-aid'])
    user_id = controller_inject.get_user().get('username', None)

    if method.lower() == 'delete':
        ibs.delete_annots(aid)
        print('[web] (DELETED) user_id: %s, aid: %d' % (user_id, aid, ))
        aid = None  # Reset AID to prevent previous
    else:
        sex = int(request.form['demographics-sex-value'])
        age = int(request.form['demographics-age-value'])
        age_min = None
        age_max = None
        # Sex
        if sex >= 2:
            sex -= 2
        else:
            sex = -1

        if age == 1:
            age_min = None
            age_max = None
        elif age == 2:
            age_min = None
            age_max = 2
        elif age == 3:
            age_min = 3
            age_max = 5
        elif age == 4:
            age_min = 6
            age_max = 11
        elif age == 5:
            age_min = 12
            age_max = 23
        elif age == 6:
            age_min = 24
            age_max = 35
        elif age == 7:
            age_min = 36
            age_max = None

        ibs.set_annot_sex([aid], [sex])
        nid = ibs.get_annot_name_rowids(aid)
        if nid is not None and DAN_SPECIAL_WRITE_AGE_TO_ALL_ANOTATIONS:
            aid_list = ibs.get_name_aids(nid)
        else:
            aid_list = [aid]

        ibs.set_annot_age_months_est_min(aid_list, [age_min] * len(aid_list))
        ibs.set_annot_age_months_est_max(aid_list, [age_max] * len(aid_list))
        print('[web] Updating %d demographics with user_id: %s\n\taid_list : %r\n\tsex: %r\n\tage_min: %r\n\tage_max: %r' % (len(aid_list), user_id, aid_list, sex, age_min, age_max,))
    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_demographics', imgsetid=imgsetid, previous=aid, species=species))


@register_route('/submit/identification/', methods=['POST'])
def submit_identification(**kwargs):
    from ibeis.web.apis_query import process_graph_match_html
    ibs = current_app.ibs

    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)
    aid1 = int(request.form['identification-aid1'])
    aid2 = int(request.form['identification-aid2'])
    replace_review_rowid = int(request.form.get('identification-replace-review-rowid', -1))

    # Process form data
    annot_uuid_1, annot_uuid_2, state, tag_list = process_graph_match_html(ibs)

    # Add state to staging database
    # FIXME:
    # photobomb and scenerymatch tags should be disjoint from match-state
    if state == 'matched':
        decision = const.EVIDENCE_DECISION.POSITIVE
    elif state == 'notmatched':
        decision = const.EVIDENCE_DECISION.NEGATIVE
    elif state == 'notcomparable':
        decision = const.EVIDENCE_DECISION.INCOMPARABLE
    elif state == 'photobomb':
        decision = const.EVIDENCE_DECISION.NEGATIVE
        tag_list = ['photobomb']
    elif state == 'scenerymatch':
        decision = const.EVIDENCE_DECISION.NEGATIVE
        tag_list = ['scenerymatch']
    else:
        raise ValueError()

    # Replace a previous decision
    if replace_review_rowid > 0:
        print('REPLACING OLD EVIDENCE_DECISION ID = %r' % (replace_review_rowid, ))
        ibs.delete_review([replace_review_rowid])

    # Add a new review row for the new decision (possibly replacing the old one)
    print('ADDING EVIDENCE_DECISION: %r %r %r %r' % (aid1, aid2, decision, tag_list, ))
    tags_list = None if tag_list is None else [tag_list]
    review_rowid = ibs.add_review([aid1], [aid2], [decision], tags_list=tags_list)
    review_rowid = review_rowid[0]
    previous = '%s;%s;%s' % (aid1, aid2, review_rowid, )

    # Notify any attached web QUERY_OBJECT
    try:
        state = const.EVIDENCE_DECISION.INT_TO_CODE[decision]
        feedback = (aid1, aid2, state, tags_list)
        print('Adding %r to QUERY_OBJECT_FEEDBACK_BUFFER' % (feedback, ))
        current_app.QUERY_OBJECT_FEEDBACK_BUFFER.append(feedback)
    except ValueError:
        pass

    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_identification', imgsetid=imgsetid, previous=previous))


@register_route('/submit/identification/v2/', methods=['POST'])
def submit_identification_v2(graph_uuid, **kwargs):
    ibs = current_app.ibs

    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)

    # Process form data
    annot_uuid_1, annot_uuid_2 = ibs.process_graph_match_html_v2(graph_uuid, **kwargs)
    aid1 = ibs.get_annot_aids_from_uuid(annot_uuid_1)
    aid2 = ibs.get_annot_aids_from_uuid(annot_uuid_2)

    hogwild = kwargs.get('identification-hogwild', False)
    hogwild_species = kwargs.get('identification-hogwild-species', None)
    hogwild_species = None if hogwild_species == 'None' or hogwild_species == '' else hogwild_species
    print('Using hogwild: %r' % (hogwild, ))

    previous = '%s;%s;-1' % (aid1, aid2, )

    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        base = url_for('turk_identification_graph')
        sep = '&' if '?' in base else '?'
        args = (base, sep, ut.to_json(graph_uuid), previous, hogwild, hogwild_species, )
        url = '%s%sgraph_uuid=%s&previous=%s&hogwild=%s&hogwild_species=%s' % args
        url = url.replace(': ', ':')
        return redirect(url)


@register_route('/submit/group_review/', methods=['POST'])
def group_review_submit(**kwargs):
    """
    CommandLine:
        python -m ibeis.web.app --exec-group_review_submit

    Example:
        >>> # UNSTABLE_DOCTEST
        >>> from ibeis.web.app import *  # NOQA
        >>> import ibeis
        >>> import ibeis.web
        >>> ibs = ibeis.opendb('testdb1')
        >>> aid_list = ibs.get_valid_aids()[::2]
        >>> ibs.start_web_annot_groupreview(aid_list)
    """
    ibs = current_app.ibs
    method = request.form.get('group-review-submit', '')
    if method.lower() == 'populate':
        redirection = request.referrer
        if 'prefill' not in redirection:
            # Prevent multiple clears
            if '?' in redirection:
                redirection = '%s&prefill=true' % (redirection, )
            else:
                redirection = '%s?prefill=true' % (redirection, )
        return redirect(redirection)
    aid_list = request.form.get('aid_list', '')
    if len(aid_list) > 0:
        aid_list = aid_list.replace('[', '')
        aid_list = aid_list.replace(']', '')
        aid_list = aid_list.strip().split(',')
        aid_list = [ int(aid_.strip()) for aid_ in aid_list ]
    else:
        aid_list = []
    src_ag, dst_ag = ibs.prepare_annotgroup_review(aid_list)
    valid_modes = ut.get_list_column(appf.VALID_TURK_MODES, 0)
    mode = request.form.get('group-review-mode', None)
    assert mode in valid_modes
    return redirect(url_for(mode, src_ag=src_ag, dst_ag=dst_ag))


@register_route('/submit/contour/', methods=['POST'])
def submit_contour(**kwargs):
    ibs = current_app.ibs
    method = request.form.get('contour-submit', '')
    imgsetid = request.args.get('imgsetid', '')
    imgsetid = None if imgsetid == 'None' or imgsetid == '' else int(imgsetid)

    part_rowid = int(request.form['contour-part-rowid'])

    if method.lower() == 'accept':
        data_dict = ut.from_json(request.form['ia-contour-data'])

        if data_dict is None:
            data_dict = {}

        contour_dict = ibs.get_part_contour(part_rowid)
        contour_dict['contour'] = data_dict
        ibs.set_part_contour([part_rowid], [contour_dict])

        segment = data_dict.get('segment', [])
        num_contours = 1
        num_points = len(segment)
        ibs.set_part_reviewed([part_rowid], [1])

        print('[web] part_rowid: %d, contours: %d, points: %d' % (part_rowid, num_contours, num_points, ))

    default_list = [
        'temp'
    ]
    config = {
        default: kwargs[default]
        for default in default_list
        if default in kwargs
    }

    # Return HTML
    refer = request.args.get('refer', '')
    if len(refer) > 0:
        return redirect(appf.decode_refer_url(refer))
    else:
        return redirect(url_for('turk_contour', imgsetid=imgsetid, previous=part_rowid, **config))


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.web.app
        python -m ibeis.web.app --allexamples
        python -m ibeis.web.app --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
