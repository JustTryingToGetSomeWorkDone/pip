from pathlib import Path

from tests.lib import PipTestEnvironment, create_basic_wheel_for_package


def configure_store_home(script: PipTestEnvironment) -> Path:
    home = script.scratch_path / "home"
    home.mkdir()
    script.environ["HOME"] = str(home)
    script.environ["USERPROFILE"] = str(home)
    return home / ".python" / "packages"


def write_project(script: PipTestEnvironment, dependency: str) -> None:
    (script.scratch_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "historical-store-test"\n'
        'version = "0.1"\n'
        f'dependencies = ["{dependency}"]\n',
        encoding="utf-8",
    )


def write_lock(script: PipTestEnvironment, version: str) -> None:
    (script.scratch_path / "pylock.toml").write_text(
        f'lock-version = "1.0"\n[[packages]]\nname = "foo"\nversion = "{version}"\n',
        encoding="utf-8",
    )


def test_store_commands_list_show_and_remove(script: PipTestEnvironment) -> None:
    store = configure_store_home(script)
    wheel = create_basic_wheel_for_package(script, "foo", "2.0")

    install_result = script.pip(
        "store",
        "install",
        "foo==2.0",
        "--no-index",
        "--find-links",
        wheel.parent,
    )

    destination = store / "foo" / "2.0"
    assert (destination / "foo" / "__init__.py").is_file()
    assert not (script.site_packages_path / "foo").exists()
    assert (
        "Installing collected packages into historical store: foo"
        in install_result.stdout
    )
    assert (
        "Successfully installed into historical store: foo-2.0"
        in install_result.stdout
    )
    listed = script.pip("store", "list").stdout
    assert listed.splitlines() == [
        "Package Version",
        "------- -------",
        "foo     2.0",
    ]
    shown = script.pip("store", "show", "foo").stdout
    assert shown.splitlines() == ["foo", "  2.0"]

    script.pip("store", "remove", "foo==2.0")
    assert not destination.exists()


def test_project_reuses_compatible_store_version(
    script: PipTestEnvironment,
) -> None:
    store = configure_store_home(script)
    wheel_1 = create_basic_wheel_for_package(script, "foo", "1.0")
    wheel_2 = create_basic_wheel_for_package(script, "foo", "2.0")
    script.pip_install_local("foo==1.0", find_links=[wheel_1.parent])
    script.pip(
        "store",
        "install",
        "foo==2.0",
        "--no-index",
        "--find-links",
        wheel_2.parent,
    )
    write_project(script, "foo==2.0")

    result = script.pip("install", "foo", "--no-index")

    assert "Requirement already satisfied by historical store" in result.stdout
    assert str(store / "foo" / "2.0") in result.stdout
    assert "Version: 1.0" in script.pip("show", "foo").stdout


def test_project_reuses_compatible_ordinary_version(
    script: PipTestEnvironment,
) -> None:
    store = configure_store_home(script)
    wheel = create_basic_wheel_for_package(script, "foo", "2.5")
    script.pip_install_local("foo==2.5", find_links=[wheel.parent])
    write_project(script, "foo>=2,<3")

    result = script.pip("install", "foo", "--no-index")

    assert "Requirement already satisfied" in result.stdout
    assert not store.exists()


def test_ordinary_version_precedes_compatible_store_version(
    script: PipTestEnvironment,
) -> None:
    configure_store_home(script)
    wheel_2_4 = create_basic_wheel_for_package(script, "foo", "2.4")
    wheel_2_5 = create_basic_wheel_for_package(script, "foo", "2.5")
    script.pip(
        "store",
        "install",
        "foo==2.4",
        "--no-index",
        "--find-links",
        wheel_2_4.parent,
    )
    script.pip_install_local("foo==2.5", find_links=[wheel_2_5.parent])
    write_project(script, "foo>=2,<3")

    result = script.pip("install", "foo", "--no-index")

    assert "Requirement already satisfied" in result.stdout
    assert "historical store" not in result.stdout


def test_compatible_lock_has_exact_priority_over_project_requirement(
    script: PipTestEnvironment,
) -> None:
    store = configure_store_home(script)
    (store / "foo" / "1.0" / "foo").mkdir(parents=True)
    (store / "foo" / "2.0" / "foo").mkdir(parents=True)
    write_project(script, "foo==1.0")
    write_lock(script, "2.0")

    result = script.pip("install", "foo", "--no-index")

    assert str(store / "foo" / "2.0") in result.stdout
    assert str(store / "foo" / "1.0") not in result.stdout


def test_project_installs_fallback_without_replacing_ordinary_version(
    script: PipTestEnvironment,
) -> None:
    store = configure_store_home(script)
    wheel_1 = create_basic_wheel_for_package(script, "foo", "1.0")
    wheel_2 = create_basic_wheel_for_package(script, "foo", "2.0")
    script.pip_install_local("foo==1.0", find_links=[wheel_1.parent])
    write_project(script, "foo==2.0")

    script.pip(
        "install",
        "foo",
        "--no-index",
        "--find-links",
        wheel_2.parent,
    )

    assert (store / "foo" / "2.0" / "foo" / "__init__.py").is_file()
    assert "Version: 1.0" in script.pip("show", "foo").stdout


def test_project_reuses_stored_transitive_dependency(
    script: PipTestEnvironment,
) -> None:
    store = configure_store_home(script)
    dependency_wheel = create_basic_wheel_for_package(script, "dependency", "2.0")
    script.pip(
        "store",
        "install",
        "dependency==2.0",
        "--no-index",
        "--find-links",
        dependency_wheel.parent,
    )
    dependency_wheel.unlink()
    root_wheel = create_basic_wheel_for_package(
        script,
        "root",
        "1.0",
        depends=["dependency==2.0"],
    )
    write_project(script, "root==1.0")

    result = script.pip(
        "install",
        "root",
        "--no-index",
        "--find-links",
        root_wheel.parent,
    )

    assert "dependency==2.0" in result.stdout
    assert (store / "root" / "1.0" / "root" / "__init__.py").is_file()
    assert (store / "dependency" / "2.0" / "dependency" / "__init__.py").is_file()


def test_project_selects_highest_compatible_store_version(
    script: PipTestEnvironment,
) -> None:
    store = configure_store_home(script)
    for version in ("1.0", "1.5", "2.4", "3.0"):
        (store / "foo" / version / "foo").mkdir(parents=True)
    write_project(script, "foo>=1,<3")

    result = script.pip("install", "foo", "--no-index")

    assert str(store / "foo" / "2.4") in result.stdout


def test_no_metadata_preserves_ordinary_install(script: PipTestEnvironment) -> None:
    store = configure_store_home(script)
    wheel = create_basic_wheel_for_package(script, "foo", "2.0")

    script.pip_install_local("foo==2.0", find_links=[wheel.parent])

    assert (script.site_packages_path / "foo" / "__init__.py").is_file()
    assert not store.exists()
