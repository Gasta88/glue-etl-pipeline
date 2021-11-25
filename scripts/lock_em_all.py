"""
This scripts launch "poetry lock" for each subproject in shape_dvaults_etl so that you don't need to do that manually for each one
"""

import logging
import os
import subprocess
import sys
from logging import getLogger
from multiprocessing.pool import Pool
from pathlib import Path
from subprocess import CompletedProcess, CalledProcessError
from time import time
from typing import Tuple, Union, Optional, IO

logger = getLogger(__name__)

# this is an utility script, so we don't need a dedicated config file
logging.basicConfig(level=logging.INFO)


def report_process_output(process: Union[CompletedProcess, CalledProcessError]):
    """
    Report captured output from the subprocess to the current one if available.

    :param process: Returned subprocess result or process error object
    """

    def report(process_buffer: Optional[bytes], target_buffer: IO):
        if isinstance(process_buffer, bytes) and len(process_buffer) > 0:
            captured_output: str = process_buffer.decode()
            target_buffer.write(captured_output)
            target_buffer.flush()

    report(process.stdout, sys.stdout)
    report(process.stderr, sys.stderr)


def execute_lock(lambda_dir: Path):
    logger.info("Generating lock for %s", lambda_dir)

    os.chdir(lambda_dir)

    try:
        subprocess.run("poetry lock", check=True, capture_output=True, shell=True)
    except CalledProcessError as e:
        logger.exception("Unable to generate lock for: %s", lambda_dir)
        report_process_output(e)
        return False

    logger.info("Lock generated for: %s", lambda_dir)
    return True


def main():
    start_time: float = time()
    src_path: Path = (
        Path(__file__).parent.parent.joinpath("shape_dvaults_etl").resolve()
    )
    components: Tuple = "extraction"

    def filter_dirs(path: Path) -> list[Path]:
        """
        Filter directories containing toml files.

        :param path: target directory to filter
        :return: filtered directories
        """
        path_dirs: list[Path] = [
            d for d in path.iterdir() if d.is_dir() and not d.name.startswith(".")
        ]
        return [
            d
            for d in path_dirs
            if "pyproject.toml" in [path.name for path in d.iterdir()]
        ]

    dir_for_locks: list[Path] = []

    logger.info("Collecting paths for locks...")

    for component in src_path.iterdir():
        if component.name in components:
            for lambda_dir in filter_dirs(component):
                dir_for_locks.append(lambda_dir)

    with Pool() as pool:
        pool.map(execute_lock, dir_for_locks)

    end_time: float = time()
    logger.info("All locks have been generated (took %ss)", int(end_time - start_time))


if __name__ == "__main__":
    main()
