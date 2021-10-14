"""Distribute GitHub Workflows to a whole workspace of repositories."""
import collections
import pathlib
import sys
import typing

import colorama
import tomli


DEFAULT_ACTIONS_TOML = "actions.toml"

LANGUAGES = {
    "python": [".py"],
    "c++": [".cpp", ".hpp", ".hxx"],
    "markdown": [".md", ".markdown"],
    "rst": [".rst"],
    "lua": [".lua"],
}


_WORKFLOW_PATH = ".github/workflows"

_MANIFEST_KEY_FILE = "file"
_MANIFEST_KEY_LANGUAGE = "language"


class Workflow(typing.NamedTuple):
    """Metadata of a workflow."""

    #: Name of the workflow.
    name: str
    #: Directory which contains the workflow files.
    parent_dir: pathlib.Path
    #: Files that belong to the workflow (relative to :attr:`parent_dir`).
    files: typing.List[str]
    #: Programming languages for which the workflow is relevant.
    languages: typing.List[str]

    def validate(self):
        """Validate if the workflow information is sane, raise error if not."""
        # check if all specified files do actually exist
        for file in self.files:
            if not (self.parent_dir / file).is_file():
                raise FileNotFoundError(file)


class Repository(typing.NamedTuple):
    """Metadata of a repository."""

    #: Path to the directory containing the repository.
    path: pathlib.Path
    #: Programming languages that were detected in the repository.
    languages: typing.List[str]
    #: Workflow files that already exist in the repository.
    workflows: typing.List[str]


def as_list(x: typing.Any):
    """If x is a list, return x, else return [x]."""
    if not isinstance(x, list):
        return [x]
    else:
        return x


def print_table(data: typing.List[typing.Sequence[str]], header=None):
    """Print tabular data in structured way.

    Args:
        data: The actual data of the table (one entry per row, all rows need to have
            same length)..
        header: Optional headers for the columns.  Needs to have same length as data
            rows.
    """
    if header:
        data = [header] + data

    max_lengths = [len(x) for x in data[0]]
    for row in data[1:]:
        lengths = [len(x) for x in row]
        max_lengths = [max(x, y) for x, y in zip(max_lengths, lengths)]

    fmt_str = " | ".join("{:<%ds}" % length for length in max_lengths)

    for row in data:
        print(fmt_str.format(*row))


def load_workflows(
    manifest_file: pathlib.Path,
) -> typing.Tuple[typing.List[Workflow], typing.Dict[str, typing.List[Workflow]]]:
    """Load workflow metadata from the specified manifest file."""
    with open(manifest_file, "rb") as f:
        manifest = tomli.load(f)

    workflows: typing.List[Workflow] = []
    workflows_per_language = collections.defaultdict(list)

    for name, info in manifest.items():
        # Set 'languages' to '*' if it is not specified
        if _MANIFEST_KEY_LANGUAGE not in info:
            info[_MANIFEST_KEY_LANGUAGE] = ["*"]

        # make sure 'languages' and 'files' are lists
        info[_MANIFEST_KEY_LANGUAGE] = as_list(info[_MANIFEST_KEY_LANGUAGE])
        info[_MANIFEST_KEY_FILE] = as_list(info[_MANIFEST_KEY_FILE])

        try:
            wf = Workflow(
                name,
                manifest_file.parent,
                info[_MANIFEST_KEY_FILE],
                info[_MANIFEST_KEY_LANGUAGE],
            )
            wf.validate()
        except Exception as e:
            print(
                colorama.Fore.YELLOW
                + "Ignore invalid workflow {}.  Reason: {}".format(name, e),
                file=sys.stderr,
            )
            continue

        workflows.append(wf)
        for lang in info[_MANIFEST_KEY_LANGUAGE]:
            workflows_per_language[lang].append(wf)

    return workflows, workflows_per_language


def determine_language(dir_path: pathlib.Path):
    """Determine programming languages used in the specified directory.

    Scans the given directory recursively for files and tries to detect programming
    languages based on file extensions.  See LANGUAGES.
    """
    check_langs = LANGUAGES.copy()
    detected_languages: typing.List[str] = []

    for file in (x for x in dir_path.rglob("*") if x.is_file()):
        # stop if there are no more languages to be checked
        if not check_langs:
            break

        for lang in list(check_langs.keys()):
            if file.suffix in check_langs[lang]:
                detected_languages.append(lang)
                # once a language is detected, remove it from the list (no need
                # to check for this language again)
                del check_langs[lang]

    return detected_languages


def find_existing_workflows(repo_dir: pathlib.Path) -> typing.List[str]:
    """Find existing workflows in the given repository.

    Args:
        repo_dir: Path to the root directory of the repository.

    Returns:
        List of workflow files that are found in the repository.
    """
    workflow_dir = repo_dir / _WORKFLOW_PATH
    if workflow_dir.is_dir():
        workflows = [
            f.name for f in workflow_dir.iterdir() if f.is_file() and f.suffix == ".yml"
        ]
    else:
        workflows = []

    return workflows


def find_repositories(
    base_dir: pathlib.Path, ignore: typing.Sequence[str] = []
) -> typing.List[Repository]:
    """Get list of repositories in the given base directory.

    Args:
        base_dir: Directory that contains the repositories.
        ignore: Optional list of repository names that are ignored.

    Returns:
        List of repositories.
    """
    repos = []
    for dir in (x for x in base_dir.iterdir() if x.is_dir()):
        if dir.name in ignore:
            # skip repo if it is on the ignore list
            continue

        langs = determine_language(dir)
        existing_workflows = find_existing_workflows(dir)

        repos.append(Repository(dir, languages=langs, workflows=existing_workflows))

    return repos


def determine_operations(
    repositories: typing.Sequence[Repository],
    workflows_per_language: typing.Dict[str, typing.List[Workflow]],
) -> typing.List[typing.Tuple[pathlib.Path, pathlib.Path]]:
    """Determine list of copy operations based on found repositories and workflows.

    Determines which files need to be copied to which repositories based on the detected
    programming languages in the repositories and the workflow metadata.

    Args:
        repositories: List of repositories to which workflows shall be copied.
        workflows_per_language: Dictionary mapping programming language names to lists
            of workflows.

    Returns:
        List of "copy operation tuples" where the first element is the source file and
        the second the destination.
    """
    operations = []
    for repo in repositories:
        for lang in (
            lang for lang in workflows_per_language if lang in repo.languages + ["*"]
        ):
            for wf in workflows_per_language[lang]:
                for wf_file in wf.files:
                    op = (wf.parent_dir / wf_file, repo.path / _WORKFLOW_PATH / wf_file)
                    operations.append(op)

    return operations
