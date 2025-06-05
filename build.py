#!/usr/bin/env python3
"""
Build script for speechmatics packages.
"""

from argparse import ArgumentParser
import shutil
import subprocess
import tempfile
from pathlib import Path
import tomli
import tomli_w


def _load_pyproject_toml(pyproject_path):
    with open(pyproject_path, 'rb') as f:
        return tomli.load(f)


def _dump_pyproject_toml(pyproject_path, data):
    with open(pyproject_path, 'wb') as f:
        tomli_w.dump(data, f)


def _build_package(package, output_dir="dist"):
    package_name = f"speechmatics-{package}"
    print(f"Building {package_name}...")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create pyproject.toml
        pyproject_content = _load_pyproject_toml(f"speechmatics/{package}/pyproject.toml")
        _dump_pyproject_toml(temp_path / "pyproject.toml", pyproject_content)

        # Copy source files
        shutil.copytree("speechmatics", temp_path / "speechmatics")

        # Build the package
        result = subprocess.run(
            ["python", "-m", "build", "--installer", "uv", "--outdir", str(Path.cwd() / output_dir)],
            cwd=temp_path,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"Successfully built {package_name}")
        else:
            raise Exception(f"Error building {package_name}: {result.stdout}")


def main(package: str):
    output_dir = Path("dist")
    output_dir.mkdir(exist_ok=True)

    try:
        _build_package(package)
        built_files = list(output_dir.glob("*"))
        if built_files:
            print("\nBuilt files:")
            for file in sorted(built_files):
                print(f"  {file}")
    except Exception as e:
        print(e)


if __name__ == "__main__":
    parser = ArgumentParser(description="Build Speechmatics Python SDK packages")
    parser.add_argument(
        "package",
        help="Package name to build",
        choices=["rt", "batch"],
    )
    args = parser.parse_args()

    main(args.package)
