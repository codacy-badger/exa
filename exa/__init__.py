# -*- coding: utf-8 -*-
# Copyright (c) 2015-2017, Exa Analytics Development Team
# Distributed under the terms of the Apache License 2.0
"""
The package is organized into sub-packages and modules. They are outlined
below. Low level functionality is found in the root (this) directory in
module files. Higher level functionalities are organized into sub-
packages.

- :mod:`exa.__main__`: Application launchers
- :mod:`exa._config`: Application configuration
- :mod:`exa._version`: Version information
- :mod:`exa.errors`: Error handling
- :mod:`exa.mpl`: Matplotlib wrappers
- :mod:`exa.tester`: Support for unit and doc tests
- :mod:`exa.tex`: Text manipulation utilities
- :mod:`exa.typed`: Strongly typed abstract base class

- :mod:`exa.app.__init__`: Jupyter notebook frontend
- :mod:`exa.cms.__init__`: Content management system
- :mod:`exa.compute.__init__`: Data computation
- :mod:`exa.core.__init__`: Data objects
"""
# For notebook widgets
def _jupyter_nbextension_paths():
    """
    Automatically generated by the `cookiecutter`_.

    .. _cookiecutter: https://github.com/jupyter/widget-cookiecutter
    """
    return [{
        'section': "notebook",
        'src': "../build/widgets",
        'dest': "jupyter-exa",
        'require': "jupyter-exa/extension"
    }]


# Import base modules
from exa import _version, _config, tester, errors, typed, mimic, mpl, tex, units

# Import sub-packages
from exa import cms, compute, core, app, tests

# Import user/dev API
from exa._version import __version__
from exa._config import info
from exa.cms import File, Job, Project, Isotope
from exa.core import Editor, Sections, Section
