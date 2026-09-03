pip - The Python Package Installer
==================================

.. |pypi-version| image:: https://img.shields.io/pypi/v/pip.svg
   :target: https://pypi.org/project/pip/
   :alt: PyPI

.. |python-versions| image:: https://img.shields.io/pypi/pyversions/pip
   :target: https://pypi.org/project/pip
   :alt: PyPI - Python Version

.. |docs-badge| image:: https://readthedocs.org/projects/pip/badge/?version=latest
   :target: https://pip.pypa.io/en/latest
   :alt: Documentation

|pypi-version| |python-versions| |docs-badge|

Historical package store prototype
----------------------------------

.. warning::

   This branch is an experimental proof of concept. It extends pip with
   historical-store commands but is not an official pip release or a complete
   replacement for environments, virtual environments, or package managers.

This prototype keeps installed distribution releases side-by-side in a
permanent, user-scoped store::

    ~/.python/packages/<distribution>/<version>/

The purpose is to avoid replacing a release that an older application still
needs. A later installation is additive: storing ``requests 2.32.5`` does not
modify a stored ``requests 2.31.0`` or an ordinary installation in
``site-packages``.

Store commands
^^^^^^^^^^^^^^

The experimental ``store`` command manages that store explicitly::

    python -m pip store list
    python -m pip store show <distribution>
    python -m pip store install "<distribution>==<version>"
    python -m pip store remove "<distribution>==<version>"

``store list`` displays every valid stored distribution and version. ``store
show`` lists the stored versions for one distribution. ``store install`` uses
pip's normal indexes, caches, resolution, and build process when a matching
release is not already present, then installs the result under the historical
store path. It also stores resolved transitive dependencies. If a compatible
release is already in the store, it is reused without downloading it.

``store remove`` requires one exact ``<distribution>==<version>`` requirement
and removes only that versioned directory. It can remove either a regular
stored installation or a symlink used to expose an existing compatible
installation.

Project metadata integration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``pip install`` is run with package requirements from a directory
containing ``pylock.toml`` or ``pyproject.toml``, this branch can use the
project's declared versions to decide where the requirement belongs:

1. A compatible ordinary distribution is preferred and remains in its normal
   environment.
2. Otherwise, a compatible version already in the historical store is reused.
3. If neither is available, pip resolves and installs the requirement and its
   dependencies into the historical store.

``pylock.toml`` with ``lock-version = "1.0"`` takes priority when it is
compatible with the current interpreter and environment. If it is unavailable
or incompatible, the resolver falls back to ``[project].dependencies`` in
``pyproject.toml``. Project discovery walks upward from the current directory;
an embedded host or another launcher can select a project explicitly with the
``PYTHONHISTORICALPROJECT`` environment variable.

For example, a project can declare::

    [project]
    name = "historical-store-example"
    version = "0.1"
    dependencies = ["requests==2.32.5"]

Running the modified pip from its source checkout can then use::

    PYTHONPATH=/path/to/pip/src \
    /path/to/python -m pip install requests

The command is project-aware only when the requirement names supplied on the
command line match the project's metadata. Invocations with no project
metadata, or ordinary pip targets outside this prototype path, retain normal
pip installation behavior. The historical store is not added to
``sys.path`` by pip; the companion experimental CPython importer selects stored
content at application runtime.

Why this exists
^^^^^^^^^^^^^^^

Traditional pip installation updates one environment's selected distribution.
That is convenient for a single application, but an upgrade can silently
change what another application imports. Separate environments avoid that
collision at the cost of duplication and additional environment management.

The historical store provides a small alternative for embedded applications:
pip performs the familiar download, build, and dependency work once, while the
runtime can later select the versions recorded by the application's metadata.
This is the model tested by the FreeCAD integration and the companion CPython
historical-store branch.

Prototype boundaries
^^^^^^^^^^^^^^^^^^^^

This branch does not remove ``site-packages``, replace ordinary pip commands,
download packages during import, or provide a new dependency solver. Version
ranges select the highest compatible stored release; they are not stronger
runtime guarantees. The branch also does not support simultaneous releases of
one import name in a single process, native-extension ABI compatibility, or
package publishing. The store root and ``PYTHONHISTORICALPROJECT`` interface
are prototype choices and may change.

The current metadata reader uses the package names and versions from a
compatible lock file; it does not yet verify lock-file artifact hashes while
selecting or importing stored content. Use the focused functional tests in
``tests/functional/test_store.py`` when changing this prototype.

pip is the `package installer`_ for Python. You can use pip to install packages from the `Python Package Index`_ and other indexes.

Please take a look at our documentation for how to install and use pip:

* `Installation`_
* `Usage`_

We release updates regularly, with a new version every 3 months. Find more details in our documentation:

* `Release notes`_
* `Release process`_

If you find bugs, need help, or want to talk to the developers, please use our mailing lists or chat rooms:

* `Issue tracking`_
* `Discourse channel`_
* `User IRC`_

If you want to get involved, head over to GitHub to get the source code, look at our development documentation and feel free to jump on the developer mailing lists and chat rooms:

* `GitHub page`_
* `Development documentation`_
* `Development IRC`_

Code of Conduct
---------------

Everyone interacting in the pip project's codebases, issue trackers, chat
rooms, and mailing lists is expected to follow the `PSF Code of Conduct`_.

.. _package installer: https://packaging.python.org/guides/tool-recommendations/
.. _Python Package Index: https://pypi.org
.. _Installation: https://pip.pypa.io/en/stable/installation/
.. _Usage: https://pip.pypa.io/en/stable/
.. _Release notes: https://pip.pypa.io/en/stable/news.html
.. _Release process: https://pip.pypa.io/en/latest/development/release-process/
.. _GitHub page: https://github.com/pypa/pip
.. _Development documentation: https://pip.pypa.io/en/latest/development
.. _Issue tracking: https://github.com/pypa/pip/issues
.. _Discourse channel: https://discuss.python.org/c/packaging
.. _User IRC: https://kiwiirc.com/nextclient/#ircs://irc.libera.chat:+6697/pypa
.. _Development IRC: https://kiwiirc.com/nextclient/#ircs://irc.libera.chat:+6697/pypa-dev
.. _PSF Code of Conduct: https://github.com/pypa/.github/blob/main/CODE_OF_CONDUCT.md
