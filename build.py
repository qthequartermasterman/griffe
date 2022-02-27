import os
from pathlib import Path
from mypyc.build import mypycify

# excluded = {"src/griffe/docstrings/dataclasses.py"}
# modules = list(str(path) for path in Path("src").rglob("*.py") if str(path) not in excluded)
modules = [
    "src/griffe/__init__.py",
    "src/griffe/__main__.py",
    "src/griffe/agents/__init__.py",
    "src/griffe/agents/base.py",
    "src/griffe/agents/extensions/__init__.py",
    "src/griffe/agents/extensions/base.py",
    "src/griffe/agents/extensions/hybrid.py",
    "src/griffe/agents/inspector.py",
    # "src/griffe/agents/nodes.py",
    "src/griffe/agents/visitor.py",
    "src/griffe/cli.py",
    # "src/griffe/collections.py",
    # "src/griffe/dataclasses.py",
    "src/griffe/docstrings/__init__.py",
    # "src/griffe/docstrings/dataclasses.py",
    "src/griffe/docstrings/google.py",
    "src/griffe/docstrings/markdown.py",
    # "src/griffe/docstrings/numpy.py",
    "src/griffe/docstrings/parsers.py",
    "src/griffe/docstrings/sphinx.py",
    "src/griffe/docstrings/utils.py",
    "src/griffe/encoders.py",
    "src/griffe/exceptions.py",
    # "src/griffe/expressions.py",
    "src/griffe/finder.py",
    "src/griffe/importer.py",
    # "src/griffe/loader.py",
    # "src/griffe/logger.py",
    "src/griffe/mixins.py",
    # "src/griffe/py.typed",
    "src/griffe/stats.py",
]
os.environ["MYPYPATH"] = ".mypy"
ext_modules = mypycify(["--config-file", ".mypy/mypy.ini", *modules])

def build(setup_kwargs):
    setup_kwargs.update(ext_modules=ext_modules)
