import subprocess
import sys


def test_pytest_quiet_flag_is_not_consumed_by_ibeis_parser():
    code = r'''
import sys
sys.argv = ['pytest', '-q', 'tests/test_gui_database_state.py']
from ibeis import params
assert params.args.qindex is None
assert '-q' in params.unknown
assert 'tests/test_gui_database_state.py' in params.unknown
'''
    subprocess.run([sys.executable, '-c', code], check=True)


def test_no_database_flag_is_parsed():
    code = r'''
import sys
sys.argv = ['ibeis', '--no-database']
from ibeis import params
assert params.args.no_database is True
'''
    subprocess.run([sys.executable, '-c', code], check=True)


def test_legacy_multi_short_index_flags_are_exact():
    code = r'''
import sys
sys.argv = ['ibeis', '-qx', '3', '-dx', '4']
from ibeis import params
assert params.args.qindex == [3]
assert params.args.dindex == [4]
assert params.unknown == []
'''
    subprocess.run([sys.executable, '-c', code], check=True)
