import pandas as pd
import ubelt as ub

names = pd.read_csv('/home/joncrall/Downloads/name_table_bak-ymd_hms-2022-02-17_10-03-53.csv', skiprows=2)
chips = pd.read_csv('/home/joncrall/Downloads/chip_table_bak-ymd_hms-2022-02-17_10-03-53.csv', skiprows=2)
images = pd.read_csv('/home/joncrall/Downloads/image_table_bak-ymd_hms-2022-02-17_10-03-53.csv', skiprows=2)

images = images.rename({'#    gid': 'gid'}, axis=1)
chips = chips.rename({'#   ChipID': 'ChipID'}, axis=1)
names = names.rename({'#   nid': 'nid'}, axis=1)

names = names.rename({c: c.strip() for c in names.columns}, axis=1)
chips = chips.rename({c: c.strip() for c in chips.columns}, axis=1)
images = images.rename({c: c.strip() for c in images.columns}, axis=1)

nid_to_cids = ub.group_items(chips['ChipID'], chips['NameID'])

unused_names = []
used_names = []
for idx, name_row in names.iterrows():
    nid = name_row['nid']
    if nid not in nid_to_cids:
        unused_names.append(name_row)
    else:
        used_names.append(name_row)

known_gids = set(images['gid'])
known_nids = set(names['nid'])

set(chips['ImgID']) - known_gids
set(chips['NameID']) - known_nids

import kwimage
import numpy as np

xywh_list = []
for row in chips['roi[tl_x  tl_y  w  h]']:
    parts = row.strip().replace('[', '').replace(']', '').split(' ')
    xywh = [float(p.strip()) for p in parts if p.strip()]
    assert len(xywh) == 4
    xywh_list.append(xywh)

chips['roi[tl_x  tl_y  w  h]'] = xywh_list

xywh = np.array(xywh_list)
boxes = kwimage.Boxes(xywh, 'xywh')

x, y, w, h = boxes.components

idxs = np.where((x < 0) | (y < 0))[0]
chips.iloc[idxs]
