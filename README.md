# GitHub Workflow Manager

Command line utility to manage a bunch of GitHub workflow files that are used
in many repositories.


## Basic Idea

All workflows are defined in one central directory (could be a git repository)
together with a "manifest file" that specifies for each workflow which files
belong to it and for which programming languages it is relevant.

The `gwm` utility provided by this package is then used to copy those workflows
to all repositories within a specified workspace.  It detects which programming
languages are used inside each repository and only adds the workflows that
match (i.e. no Python style checker in a pure C++ package).

If at some point one of the workflows is changed, you can simply run `gwm`
again to update it in all repositories.


## Usage

Collect all your workflow files in one place and add a manifest file in TOML
format.  For each workflow add a section with a `file` attribute and optionally
a `language` attribute.  Example:

```toml
[python_black]
file = "python_black.yml"
language = "python"

[python_flake8]
file = ["python_flake8.yml", "flake8-problem-matcher.json"]
language = "python"

[git_fixup]
file = "git.yml"
```

The value of both attributes can either be a single string or a list of
strings.  File paths are resolved relative to the manifest file.
If no language attribute is specified, the workflow is used for all
repositories.


You can list the information of the manifest file using

    gwm list_workflows -w path/to/manifest.toml

To show which information `gwm` detects about repositories in a given
workspace, you can run

    gwm list_repos -t path/to/workspace

To copy the workflow files to the repositories run

    gwm put -w path/to/manifest.toml -t path/to/workspace --verbose

Add `--dry-run` to only print which files would be copied without actually
copying them.

If you want to exclude some repositories from the workspace, specify them with
`--ignore-repos` (this also works for `list_repos`).


## Limitations

This utility is in early alpha phase and there are a bunch of limitations:

- Every directory in the given workspace is considered to be a repository.  If
  there are directories in the workspace to which no workflows should be
  copied, they need to be excluded using the `--ignore-repo` argument.
- Files are only copied, no git commit or similar is done.  However, `treep`
  may help to to commit on all repositories at once.
