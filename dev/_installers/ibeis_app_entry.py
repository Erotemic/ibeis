# ibeis_app_entry.py
import multiprocessing
"""
pip install pyinstaller

pyinstaller --clean -y --onedir ^
  --name IBEIS ^
  --console ^
  --collect-all PyQt5 ^
  --collect-all numpy ^
  --collect-all scipy ^
  --collect-all matplotlib ^
  --collect-all cv2 ^
  --collect-all ibeis ^
  --collect-all vtool_ibeis ^
  --collect-all dtool_ibeis ^
  --collect-all plottool_ibeis ^
  --collect-all guitool_ibeis ^
  --collect-all pyhesaff ^
  --collect-all pyflann_ibeis ^
  --collect-all vtool_ibeis_ext ^
  ibeis_app_entry.py

"""

def main():
    multiprocessing.freeze_support()  # needed on Windows when frozen

    # Help PyInstaller “see” dynamic imports / compiled submodules
    try:
        from ibeis.__main__ import dependencies_for_myprogram
        dependencies_for_myprogram()
    except Exception:
        pass

    # Run the actual app
    from ibeis.__main__ import run_ibeis
    run_ibeis()

if __name__ == "__main__":
    main()
