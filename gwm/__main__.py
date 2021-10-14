"""Distribute GitHub Workflows to a whole workspace of repositories."""
import argparse
import pathlib
import shutil
import sys

import colorama

from . import gwm


def cmd_list_workflows(args):
    """List workflows from the given manifest file."""
    workflows, _ = gwm.load_workflows(args.workflows)
    print("Workflows:")
    gwm.print_table(
        [(wf.name, ",".join(wf.languages), ", ".join(wf.files)) for wf in workflows],
        header=["NAME", "LANGUAGES", "FILES"],
    )
    return 0


def cmd_list_repos(args):
    """List repositories in the given base directory."""
    print("Repositories in {}:\n".format(args.target_root))
    repos = gwm.find_repositories(args.target_root, args.ignore_repos)
    gwm.print_table(
        [(r.path.name, ", ".join(r.languages), ", ".join(r.workflows)) for r in repos],
        header=["NAME", "LANGUAGES", "EXISTING WORKFLOWS"],
    )
    return 0


def cmd_put(args):
    """Copy workflow files to all matching repositories."""
    workflows, workflows_per_language = gwm.load_workflows(args.workflows)
    repos = gwm.find_repositories(args.target_root, args.ignore_repos)
    ops = gwm.determine_operations(repos, workflows_per_language)

    if args.dry_run:
        print(colorama.Fore.YELLOW + "Dry run, not actually copying files.")
        for op in ops:
            print("Copy {} -> {}".format(*op))
    else:
        for src, dest in ops:
            # make sure the target directory exists
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            if args.verbose:
                print("Copy {} -> {}".format(src, dest))

    return 0


def main():
    colorama.init(autoreset=True)

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(title="commands", dest="command")
    subparsers.required = True

    # general arguments that are shared by all commands
    common_args = argparse.ArgumentParser(add_help=False)
    common_args.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output (only relevant for same commands).",
    )

    # arguments that are shared by commands loading the workflow manifest file
    workflow_args = argparse.ArgumentParser(add_help=False)
    workflow_args.add_argument(
        "--workflows",
        "-w",
        type=pathlib.Path,
        required=True,
        help="Path to the workflow manifest file.",
    )

    # arguments that are shared by commands loading the list of repositories
    repo_args = argparse.ArgumentParser(add_help=False)
    repo_args.add_argument(
        "--target-root",
        "-t",
        type=pathlib.Path,
        default=".",
        help="""Base directory that contains all the repositories.  Defaults to current
            working directory.
        """,
    )
    repo_args.add_argument(
        "--ignore-repos",
        type=str,
        nargs="+",
        default=[],
        help="Ignore the specified repositories.",
    )

    # add actual commands
    sub = subparsers.add_parser(
        "list_workflows",
        description="List workflows from the specified manifest",
        help="List workflows",
        parents=[common_args, workflow_args],
    )
    sub.set_defaults(func=cmd_list_workflows)

    sub = subparsers.add_parser(
        "list_repos",
        description="List repositories of the specified workspace.",
        help="List repositories",
        parents=[common_args, repo_args],
    )
    sub.set_defaults(func=cmd_list_repos)

    sub = subparsers.add_parser(
        "put",
        description="Copy workflows to the repositories",
        help="Copy workflows to the repositories",
        parents=[common_args, workflow_args, repo_args],
    )
    sub.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not actually copy files, only print what would be done.",
    )
    sub.set_defaults(func=cmd_put)

    # parse arguments and execute corresponding function
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
