# AGENT Instructions

## Development Environment Setup
- **Python**: Project targets Python 3.9–3.13 (see `pyproject.toml`).
- **System packages**: The GUI and scientific stack rely on Qt, OpenCV, and native deps for packages like `pyqt5`, `numpy`, `scipy`, `scikit-image`, `scikit-learn`, and `pyflann_ibeis`/`pyhesaff`.
- **Install dependencies**:
  - For development, run `run_developer_setup.sh` (installs `requirements.txt` then `python setup.py develop`).
  - `requirements/runtime.txt` lists core deps; `requirements/tests.txt` adds `pytest`, `pytest-cov`, and `xdoctest`; `requirements/optional.txt` covers extras.
  - OpenCV is not auto-installed; install one of `opencv-python-headless` (recommended) or `opencv-python` after base install. Import errors from `cv2` will block startup.
- **Virtual environment**: Use your preferred venv tool (`python -m venv .venv` then activate) before running setup scripts.
- **Entrypoints**: Console script `ibeis` -> `ibeis.__main__:run_ibeis` (GUI/front-end entry); package import assumes `cv2` and IBEIS sibling libs are present.

## Repository Structure Overview
- `ibeis/`: Primary package.
  - `__init__.py`: Version, import-side dependency checks, and core API exports (`IBEISController`, `QueryRequest`, etc.).
  - `__main__.py`: CLI/GUI launcher and dev/test helpers.
  - `control/`: Database + controller logic (`IBEISControl` and helpers).
  - `dbio/`: Database I/O.
  - `algo/`: Algorithms (e.g., `hots` identification pipeline, graph inference, detection, etc.).
  - `viz/`: Visualization helpers.
  - `gui/`: PyQt5 GUI components.
  - `web/`: Experimental web frontend pieces.
  - `scripts/`: Utility/maintenance scripts (e.g., rsync helpers).
  - `tests/`: Package-level tests used by `run_tests.py`.
  - Additional modules: `constants.py`, `params.py`, `demodata.py`, `templates/`, and dev helpers `_devcmds_ibeis.py`, `_devscript.py`.
- Root scripts: `run_tests.py`, `run_doctests.sh`, `run_linter.sh`, `run_developer_setup.sh`, `super_setup.py` (legacy setup helper), `run_developer_setup.sh`.
- `docs/`: Sphinx config (`docs/source/index.rst` uses API autodoc of `ibeis`).
- `dev/`: Installer, Docker, and maintenance utilities (not normally needed for day-to-day coding).

## Important Components
- **Controller API**: `ibeis.control.IBEISControl.IBEISController` is the main interface to database operations and algorithms; high-level helpers in `ibeis.main_module` (`main`, `main_loop`, `opendb*`).
- **Algorithms**: Under `ibeis.algo`, especially `hots` for identification (`query_request`, `chip_match`, etc.) and `graph` for inference.
- **Initialization/System resources**: `ibeis.init.sysres` manages local database/workdir paths (`get_workdir`, `ensure_*` datasets).
- **Configuration**: `constants.py`, `params.py`, and `filter_configs.py` define tags/defaults; GUI/web settings live in corresponding subpackages.
- **Visualization/GUI**: `viz` handles plotting/matplotlib; `gui` uses PyQt5 (`guitool_ibeis`, `plottool_ibeis`).
- **Data access helpers**: `core_annots.py`, `core_images.py`, `annotmatch_funcs.py`, etc., encapsulate frequently used database tables/relationships.

## Testing Guide
- **Unit/coverage run**: `python run_tests.py` (runs `pytest` with coverage + xdoctest for package modules and `tests/`).
- **Direct pytest**: `pytest --cov-config pyproject.toml --cov=ibeis --xdoctest ibeis tests` (mirrors `run_tests.py`).
- **Doctests**: `run_doctests.sh` (`xdoctest ibeis --style=google all`). You can also target a module via `python -m ibeis --tmod <module>.<func>:<case>`.
- **Linting**: `run_linter.sh` executes `flake8` with error-only checks (E9,F63,F7,F82).
- **Test data**: Certain tests/tools expect demo databases; `ibeis.tests.reset_testdbs.reset_ci_testdbs()` (triggered via `python -m ibeis --reset-ci-dbs`) downloads/sets them up.
- **Adding tests**: Place new tests under `tests/` or alongside modules for `xdoctest`; follow pytest style and keep long-running GUI/web tests optional or skipped.

## Extending or Modifying the System
- Prefer working through `IBEISController` APIs rather than manipulating SQLite directly; consult existing `core_*` modules for patterns.
- Maintain separation of concerns: algorithms in `algo`, persistence in `control/dbio`, visualization in `viz/gui`.
- When adding CLI options or behaviors, check `ibeis.__main__` and `ibeis.main_module`; keep backward compatibility with existing flags (`--resetdbs`, `--tmod`, etc.).
- GUI changes should respect PyQt5 dependencies; avoid importing heavy GUI modules at top-level unless necessary to keep headless contexts working.
- Follow existing naming conventions (e.g., `*funcs.py` for grouped utilities, `core_*` for table-level logic). Avoid wrapping imports in try/except unless mirroring existing `cv2` workaround.
- Update docs (`docs/source/index.rst` or inline docstrings) when exposing new public APIs; ensure doctests remain valid.
- For binary/library dependencies, prefer headless OpenCV; note that `plottool_ibeis` must initialize before certain GUI imports (see comments in `ibeis/__init__.py`).

## Documentation Overview
- High-level README (`README.rst`) covers installation, GUI usage, and program description.
- Sphinx docs in `docs/` rely on autodoc of `ibeis` package; `make html` from `docs/` (with dependencies installed) builds API docs.
- Changelog maintained in `CHANGELOG.md`.

## Task-Specific Knowledge
- The ecosystem depends on sibling packages (`utool`, `ubelt`, `vtool_ibeis`, `dtool_ibeis`, `plottool_ibeis`, `guitool_ibeis`, `pyhesaff`, etc.); many algorithms assume these APIs.
- The application can run in GUI mode (`ibeis` CLI) or via library calls; ensure database paths/workdirs are set (use `ibeis.init.sysres` helpers) before operations.
- `pyproject.toml` configures pytest ignores and coverage exclusions; `setup.py` retains legacy build logic for editable installs.
- Some CLI flags trigger experimental behaviors (e.g., `--devcmd` interactive shell); keep them intact for developer workflows.
