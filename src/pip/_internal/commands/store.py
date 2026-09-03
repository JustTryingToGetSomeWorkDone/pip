from __future__ import annotations

import shutil
from optparse import Values
from typing import Callable

from pip._vendor.packaging.requirements import InvalidRequirement, Requirement

from pip._internal.cli.status_codes import ERROR, SUCCESS
from pip._internal.commands.install import InstallCommand
from pip._internal.exceptions import CommandError, PipError
from pip._internal.historical_store import (
    find_stored,
    iter_stored_distributions,
)
from pip._internal.utils.logging import getLogger
from pip._internal.utils.misc import tabulate, write_output

logger = getLogger(__name__)


class StoreCommand(InstallCommand):
    """Inspect and manage pip's experimental historical package store."""

    ignore_require_venv = True
    usage = """
        %prog list
        %prog show <distribution>
        %prog install <requirement> [package-index-options] ...
        %prog remove <distribution>==<version>
    """

    def handler_map(  # type: ignore[override]
        self,
    ) -> dict[str, Callable[[Values, list[str]], int]]:
        return {
            "list": self.list_store,
            "show": self.show_store,
            "install": self.install_store,
            "remove": self.remove_store,
        }

    def run(self, options: Values, args: list[str]) -> int:
        handlers = self.handler_map()
        if not args or args[0] not in handlers:
            logger.error(
                "Need an action (%s) to perform.",
                ", ".join(sorted(handlers)),
            )
            return ERROR
        try:
            return handlers[args[0]](options, args[1:])
        except PipError as error:
            logger.error(error.args[0])
            return ERROR

    def list_store(self, options: Values, args: list[str]) -> int:
        if args:
            raise CommandError("Too many arguments")
        distributions = iter_stored_distributions()
        if not distributions:
            return SUCCESS
        rows = [["Package", "Version"]]
        rows.extend(
            [distribution.name, str(distribution.version)]
            for distribution in distributions
        )
        output, sizes = tabulate(rows)
        output.insert(1, " ".join("-" * size for size in sizes))
        for line in output:
            write_output(line)
        return SUCCESS

    def show_store(self, options: Values, args: list[str]) -> int:
        if len(args) != 1:
            raise CommandError("Please provide exactly one distribution name")
        distributions = iter_stored_distributions(args[0])
        if not distributions:
            raise CommandError(f"No stored versions found for {args[0]}")
        logger.info(distributions[0].name)
        for distribution in distributions:
            logger.info("  %s", distribution.version)
        return SUCCESS

    def install_store(self, options: Values, args: list[str]) -> int:
        if not args:
            raise CommandError("Please provide at least one requirement")

        remaining = []
        for text in args:
            try:
                requirement = Requirement(text)
            except InvalidRequirement:
                remaining.append(text)
                continue
            stored = find_stored(requirement)
            if stored is None:
                remaining.append(text)
                continue
            logger.info(
                "Requirement already satisfied by historical store: %s in %s",
                requirement,
                stored.path,
            )
        if not remaining:
            return SUCCESS

        options.historical_store = True
        options.ignore_installed = True
        return super().run(options, remaining)

    def remove_store(self, options: Values, args: list[str]) -> int:
        if len(args) != 1:
            raise CommandError("Please provide exactly one name==version requirement")
        try:
            requirement = Requirement(args[0])
        except InvalidRequirement as error:
            raise CommandError(f"Invalid requirement: {args[0]}") from error
        specifiers = list(requirement.specifier)
        if (
            len(specifiers) != 1
            or specifiers[0].operator != "=="
            or specifiers[0].version.endswith(".*")
        ):
            raise CommandError("store remove requires an exact name==version")
        stored = find_stored(requirement)
        if stored is None or str(stored.version) != specifiers[0].version:
            raise CommandError(f"No stored version matches {requirement}")
        if stored.path.is_symlink():
            stored.path.unlink()
        else:
            shutil.rmtree(stored.path)
        try:
            stored.path.parent.rmdir()
        except OSError:
            pass
        logger.info("Removed %s %s", stored.name, stored.version)
        return SUCCESS
