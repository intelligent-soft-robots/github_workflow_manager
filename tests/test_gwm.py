"""Unit tests for github_workflow_manager (gwm)."""
import collections
import pathlib

import pytest

from gwm import gwm
from gwm.__main__ import cmd_put


# location of the test workflows (relative to this file)
workflows_dir = pathlib.Path(__file__).parent / "workflows"
workflows_manifest = workflows_dir / "workflows.toml"


@pytest.fixture
def workspace(tmp_path: pathlib.Path):
    """Setup some dummy packages in a temporary directory."""
    empty_pkg = tmp_path / "empty_pkg"
    py_pkg = tmp_path / "py_pkg"
    cpp_pkg = tmp_path / "cpp_pkg"
    py_cpp_pkg = tmp_path / "py_cpp_pkg"

    # create package directories
    empty_pkg.mkdir()
    py_pkg.mkdir()
    cpp_pkg.mkdir()
    py_cpp_pkg.mkdir()

    # create some files for language detection
    (py_pkg / "file.py").touch()
    (cpp_pkg / "main.cpp").touch()
    (py_cpp_pkg / "file.py").touch()
    (py_cpp_pkg / "main.cpp").touch()

    # add an existing workflow
    wf_dir = py_pkg / ".github/workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "exists1.yml").touch()
    (wf_dir / "exists2.yml").touch()
    (wf_dir / "some_problem_matcher.json").touch()

    return tmp_path


def test_as_list():
    assert gwm.as_list(42) == [42]
    assert gwm.as_list([42]) == [42]


def test_load_workflows():
    workflows, wf_per_lang = gwm.load_workflows(workflows_manifest)

    assert len(workflows) == 2

    assert workflows[0].name == "python_flake8"
    assert workflows[0].parent_dir == workflows_dir
    assert workflows[0].files == ["flake8.yml", "flake8-problem-matcher.json"]
    assert workflows[0].languages == ["python"]

    assert workflows[1].name == "git_fixup"
    assert workflows[1].parent_dir == workflows_dir
    assert workflows[1].files == ["git.yml"]
    assert workflows[1].languages == ["*"]

    # the "doesnotexit" workflow should not be included as the corresponding
    # file does not exist

    assert wf_per_lang["python"][0].name == "python_flake8"
    assert wf_per_lang["*"][0].name == "git_fixup"


def test_determine_language(workspace):
    assert gwm.determine_language(workspace / "empty_pkg") == []
    assert gwm.determine_language(workspace / "py_pkg") == ["python"]
    assert gwm.determine_language(workspace / "cpp_pkg") == ["c++"]
    assert sorted(gwm.determine_language(workspace / "py_cpp_pkg")) == ["c++", "python"]


def test_find_existing_workflows(workspace):
    assert gwm.find_existing_workflows(workspace / "empty_pkg") == []
    assert sorted(gwm.find_existing_workflows(workspace / "py_pkg")) == [
        "exists1.yml",
        "exists2.yml",
    ]


def test_find_repositories_all(workspace):
    repos = gwm.find_repositories(workspace)

    assert len(repos) == 4

    # need to sort them by name, so we can check more easily
    repos = sorted(repos, key=lambda r: r.path.name)

    assert repos[0].path == workspace / "cpp_pkg"
    assert repos[0].languages == ["c++"]
    assert repos[0].workflows == []

    assert repos[1].path == workspace / "empty_pkg"
    assert repos[1].languages == []
    assert repos[1].workflows == []

    assert repos[2].path == workspace / "py_cpp_pkg"
    assert sorted(repos[2].languages) == ["c++", "python"]
    assert repos[2].workflows == []

    assert repos[3].path == workspace / "py_pkg"
    assert repos[3].languages == ["python"]
    assert sorted(repos[3].workflows) == ["exists1.yml", "exists2.yml"]


def test_find_repositories_ignore_some(workspace):
    repos = gwm.find_repositories(workspace, ignore=["py_cpp_pkg", "py_pkg"])

    assert len(repos) == 2

    # need to sort them by name, so we can check more easily
    repos = sorted(repos, key=lambda r: r.path.name)

    assert repos[0].path == workspace / "cpp_pkg"
    assert repos[0].languages == ["c++"]
    assert repos[0].workflows == []

    assert repos[1].path == workspace / "empty_pkg"
    assert repos[1].languages == []
    assert repos[1].workflows == []


def test_determine_operations(workspace):
    repos = gwm.find_repositories(workspace, ignore=["py_cpp_pkg"])
    _, wf_per_lang = gwm.load_workflows(workflows_manifest)
    ops = gwm.determine_operations(repos, wf_per_lang)

    assert len(ops) == 5

    assert (
        (workflows_dir / "flake8.yml"),
        workspace / "py_pkg/.github/workflows/flake8.yml",
    ) in ops
    assert (
        (workflows_dir / "flake8-problem-matcher.json"),
        workspace / "py_pkg/.github/workflows/flake8-problem-matcher.json",
    ) in ops
    assert (
        (workflows_dir / "git.yml"),
        workspace / "py_pkg/.github/workflows/git.yml",
    ) in ops
    assert (
        (workflows_dir / "git.yml"),
        workspace / "cpp_pkg/.github/workflows/git.yml",
    ) in ops
    assert (
        (workflows_dir / "git.yml"),
        workspace / "empty_pkg/.github/workflows/git.yml",
    ) in ops


def _run_cmd_put(workspace, dry_run):
    Args = collections.namedtuple(
        "Args", ("workflows", "target_root", "ignore_repos", "dry_run", "verbose")
    )
    args = Args(
        workflows=workflows_manifest,
        target_root=workspace,
        ignore_repos=["py_cpp_pkg"],
        dry_run=dry_run,
        verbose=False,
    )
    cmd_put(args)


def test_cmd_put_dry(workspace):
    _run_cmd_put(workspace, dry_run=True)

    # it was a dry run, so nothing should be added
    for pkg in workspace.iterdir():
        assert not (pkg / ".github/workflows" / "flake8.yml").exists()
        assert not (pkg / ".github/workflows" / "flake8-problem-matcher.json").exists()
        assert not (pkg / ".github/workflows" / "git.yml").exists()


def test_cmd_put(workspace):
    _run_cmd_put(workspace, dry_run=False)

    empty_pkg = workspace / "empty_pkg" / ".github/workflows"
    py_pkg = workspace / "py_pkg" / ".github/workflows"
    cpp_pkg = workspace / "cpp_pkg" / ".github/workflows"
    py_cpp_pkg = workspace / "py_cpp_pkg" / ".github/workflows"

    assert not (empty_pkg / "flake8.yml").exists()
    assert not (empty_pkg / "flake8-problem-matcher.json").exists()
    assert (empty_pkg / "git.yml").exists()

    assert (py_pkg / "flake8.yml").exists()
    assert (py_pkg / "flake8-problem-matcher.json").exists()
    assert (py_pkg / "git.yml").exists()

    assert not (cpp_pkg / "flake8.yml").exists()
    assert not (cpp_pkg / "flake8-problem-matcher.json").exists()
    assert (cpp_pkg / "git.yml").exists()

    # this package was ignored, so nothing should be added
    assert not (py_cpp_pkg / "flake8.yml").exists()
    assert not (py_cpp_pkg / "flake8-problem-matcher.json").exists()
    assert not (py_cpp_pkg / "git.yml").exists()
