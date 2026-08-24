import ibeis
from ibeis import constants as const
from ibeis.tests.fixtures import IBEISControllerFixture


def test_wildbook_signal_tracks_legacy_web_plugin():
    assert ibeis.ENABLE_WILDBOOK_SIGNAL == const.ENABLE_LEGACY_WEB


def test_positive_match_does_not_require_wildbook_in_normal_mode():
    if const.ENABLE_LEGACY_WEB:
        return

    with IBEISControllerFixture() as ibs:
        aid1, aid2 = ibs.get_valid_aids()[0:2]
        ibs.set_annot_name_rowids(
            [aid1, aid2],
            [const.UNKNOWN_NAME_ROWID, const.UNKNOWN_NAME_ROWID],
            notify_wildbook=False,
        )

        assert not hasattr(ibs, 'wildbook_signal_annot_name_changes')
        status = ibs.set_annot_pair_as_positive_match(aid1, aid2)

        nid1, nid2 = ibs.get_annot_name_rowids([aid1, aid2])
        assert nid1 == nid2
        assert nid1 != const.UNKNOWN_NAME_ROWID
        assert status is not None
