"""
This script invokes build_lambda_package.sh for each submodule in shape_dvaults_etl
in order to build each zip package in a single shot
"""

import logging
import subprocess
import sys
from logging import getLogger
from pathlib import Path
from subprocess import CompletedProcess, CalledProcessError
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


def main():
    src_path: Path = Path(__file__).parent.parent.joinpath("shape").resolve()
    build_script_path: Path = (
        Path(__file__).parent.joinpath("build_lambda_package.sh").resolve()
    )
    components: Tuple = "extraction"
    lambdas: Tuple = ("firehose_kinesis", "profiler")

    logger.info("Building lambdas (src path: %s)", src_path)

    for component in src_path.iterdir():
        if component.name in components:
            logger.info('Building component "%s"', component.name)

            for lambda_dir in component.iterdir():
                if lambda_dir.name in lambdas:

                    logger.info(
                        'Building lambda "%s.%s" (%s)',
                        component.name,
                        lambda_dir.name,
                        lambda_dir,
                    )

                    try:
                        script_path: str = str(build_script_path)
                        lambda_path: str = str(lambda_dir)
                        lambda_package_path: str = (
                            component.name + "/" + lambda_dir.name
                        )
                        process_args: list[str] = [
                            script_path,
                            component.name,
                            lambda_path,
                            lambda_package_path,
                        ]
                        process: CompletedProcess = subprocess.run(
                            process_args, check=True, capture_output=True
                        )
                        report_process_output(process)
                    except CalledProcessError as e:
                        report_process_output(e)
                        raise e

    logger.info("All lambdas have been built successfully")


if __name__ == "__main__":
    main()
