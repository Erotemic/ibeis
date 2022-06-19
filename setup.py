import sys
from os.path import exists
from setuptools import find_packages
from setuptools import setup


def parse_version(fpath):
    """
    Statically parse the version number from a python file
    """
    value = static_parse("__version__", fpath)
    return value


def static_parse(varname, fpath):
    """
    Statically parse the a constant variable from a python file
    """
    import ast

    if not exists(fpath):
        raise ValueError("fpath={!r} does not exist".format(fpath))
    with open(fpath, "r") as file_:
        sourcecode = file_.read()
    pt = ast.parse(sourcecode)

    class StaticVisitor(ast.NodeVisitor):
        def visit_Assign(self, node):
            for target in node.targets:
                if getattr(target, "id", None) == varname:
                    self.static_value = node.value.s

    visitor = StaticVisitor()
    visitor.visit(pt)
    try:
        value = visitor.static_value
    except AttributeError:
        import warnings

        value = "Unknown {}".format(varname)
        warnings.warn(value)
    return value


def parse_description():
    """
    Parse the description in the README file

    CommandLine:
        pandoc --from=markdown --to=rst --output=README.rst README.md
        python -c "import setup; print(setup.parse_description())"
    """
    from os.path import dirname, join, exists

    readme_fpath = join(dirname(__file__), "README.rst")
    # This breaks on pip install, so check that it exists.
    if exists(readme_fpath):
        with open(readme_fpath, "r") as f:
            text = f.read()
        return text
    return ""


def parse_requirements(fname="requirements.txt", versions=False):
    """
    Parse the package dependencies listed in a requirements file but strips
    specific versioning information.

    Args:
        fname (str): path to requirements file
        versions (bool | str, default=False):
            If true include version specs.
            If strict, then pin to the minimum version.

    Returns:
        List[str]: list of requirements items
    """
    from os.path import exists, dirname, join
    import re

    require_fpath = fname

    def parse_line(line, dpath=""):
        """
        Parse information from a line in a requirements text file

        line = 'git+https://a.com/somedep@sometag#egg=SomeDep'
        line = '-e git+https://a.com/somedep@sometag#egg=SomeDep'
        """
        # Remove inline comments
        comment_pos = line.find(" #")
        if comment_pos > -1:
            line = line[:comment_pos]

        if line.startswith("-r "):
            # Allow specifying requirements in other files
            target = join(dpath, line.split(" ")[1])
            for info in parse_require_file(target):
                yield info
        else:
            # See: https://www.python.org/dev/peps/pep-0508/
            info = {"line": line}
            if line.startswith("-e "):
                info["package"] = line.split("#egg=")[1]
            else:
                if ";" in line:
                    pkgpart, platpart = line.split(";")
                    # Handle platform specific dependencies
                    # setuptools.readthedocs.io/en/latest/setuptools.html
                    # #declaring-platform-specific-dependencies
                    plat_deps = platpart.strip()
                    info["platform_deps"] = plat_deps
                else:
                    pkgpart = line
                    platpart = None

                # Remove versioning from the package
                pat = "(" + "|".join([">=", "==", ">"]) + ")"
                parts = re.split(pat, pkgpart, maxsplit=1)
                parts = [p.strip() for p in parts]

                info["package"] = parts[0]
                if len(parts) > 1:
                    op, rest = parts[1:]
                    version = rest  # NOQA
                    info["version"] = (op, version)
            yield info

    def parse_require_file(fpath):
        dpath = dirname(fpath)
        with open(fpath, "r") as f:
            for line in f.readlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    for info in parse_line(line, dpath=dpath):
                        yield info

    def gen_packages_items():
        if exists(require_fpath):
            for info in parse_require_file(require_fpath):
                parts = [info["package"]]
                if versions and "version" in info:
                    if versions == "strict":
                        # In strict mode, we pin to the minimum version
                        if info["version"]:
                            # Only replace the first >= instance
                            verstr = "".join(info["version"]).replace(">=", "==", 1)
                            parts.append(verstr)
                    else:
                        parts.extend(info["version"])
                if not sys.version.startswith("3.4"):
                    # apparently package_deps are broken in 3.4
                    plat_deps = info.get("platform_deps")
                    if plat_deps is not None:
                        parts.append(";" + plat_deps)
                item = "".join(parts)
                yield item

    packages = list(gen_packages_items())
    return packages


def native_mb_python_tag(plat_impl=None, version_info=None):
    """
    Get the correct manylinux python version tag for this interpreter

    Example:
        >>> print(native_mb_python_tag())
        >>> print(native_mb_python_tag('PyPy', (2, 7)))
        >>> print(native_mb_python_tag('CPython', (3, 8)))
    """
    if plat_impl is None:
        import platform

        plat_impl = platform.python_implementation()

    if version_info is None:
        import sys

        version_info = sys.version_info

    major, minor = version_info[0:2]
    ver = "{}{}".format(major, minor)

    if plat_impl == "CPython":
        # TODO: get if cp27m or cp27mu
        impl = "cp"
        if ver == "27":
            IS_27_BUILT_WITH_UNICODE = True  # how to determine this?
            if IS_27_BUILT_WITH_UNICODE:
                abi = "mu"
            else:
                abi = "m"
        else:
            if sys.version_info[:2] >= (3, 8):
                # bpo-36707: 3.8 dropped the m flag
                abi = ""
            else:
                abi = "m"
        mb_tag = "{impl}{ver}-{impl}{ver}{abi}".format(**locals())
    elif plat_impl == "PyPy":
        abi = ""
        impl = "pypy"
        ver = "{}{}".format(major, minor)
        mb_tag = "{impl}-{ver}".format(**locals())
    else:
        raise NotImplementedError(plat_impl)
    return mb_tag


NAME = "ibeis"
INIT_PATH = "ibeis/__init__.py"
VERSION = parse_version("ibeis/__init__.py")

if __name__ == "__main__":
    setupkw = {}

    if 1:
        setupkw["entry_points"] = {
            # the console_scripts entry point creates the package CLI
            "console_scripts": ["ibeis=ibeis.__main__:run_ibeis"]
        }
    setupkw["install_requires"] = parse_requirements("requirements/runtime.txt")
    setupkw["extras_require"] = {
        "all": parse_requirements("requirements.txt"),
        "tests": parse_requirements("requirements/tests.txt"),
        "optional": parse_requirements("requirements/optional.txt"),
        "headless": parse_requirements("requirements/headless.txt"),
        "graphics": parse_requirements("requirements/graphics.txt"),
        # Strict versions
        "headless-strict": parse_requirements(
            "requirements/headless.txt", versions="strict"
        ),
        "graphics-strict": parse_requirements(
            "requirements/graphics.txt", versions="strict"
        ),
        "all-strict": parse_requirements("requirements.txt", versions="strict"),
        "runtime-strict": parse_requirements(
            "requirements/runtime.txt", versions="strict"
        ),
        "tests-strict": parse_requirements("requirements/tests.txt", versions="strict"),
        "optional-strict": parse_requirements(
            "requirements/optional.txt", versions="strict"
        ),
    }

    setup(
        name=NAME,
        version=VERSION,
        author=["Jon Crall", "Jason Parham"],
        author_email="erotemic@gmail.com",
        url="https://github.com/Erotemic/ibeis",
        description="IBEIS - Image Based Ecological Information System",
        long_description=parse_description(),
        long_description_content_type="text/x-rst",
        license="Apache 2",
        packages=find_packages("."),
        python_requires=">=3.7",
        classifiers=[
            "Development Status :: 4 - Beta",
            "License :: OSI Approved :: Apache Software License",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
        ],
        **setupkw,
    )
