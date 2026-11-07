"""
A Toolbox of small shared utilities.
"""
import sys
import os
import logging
import pyarrow as pa
import pyarrow.parquet as parquet

from typing import TextIO, Any


def configure_logging(
        verbosity: int,
        format: str = '%(asctime)s %(levelname)s: %(message)s',
        stream: TextIO = sys.stderr
) -> None:
    """Configure the root logger for the application.

    :param: verbosity: Verbosity level (0-3), where 0=ERROR, 1=WARNING, 2=INFO, 3=DEBUG.
    :param: format: Logging format string. Defaults to '%(asctime)s %(levelname)s: %(message)s'.
    :param: stream: Output stream for log messages. Defaults to sys.stderr.
    :return: None
    """
    levels = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
    logging.basicConfig(
        level=levels[min(verbosity, len(levels) - 1)],
        format=format,
        stream=stream
    )


def _gather_parquet_files(table_dir: str) -> list[str]:
    """Gather all parquet files from the given directory."""
    return [
        os.path.join(table_dir, f)
        for f in os.listdir(table_dir)
        if f.endswith('.parquet')
    ]


def read_data_from(table_dir: str, filters=None) -> list[dict[str, Any]]:
    """
    Read Parquet tables as a python list
    :param: table_dir: a directory where to find partial parquet files for the table.
    :param: filters: Filters passed straight to pyarrow.parquet.read_table().
    :return: a list of dictionaries representing the job records as defined in schema.py.
    """
    parquet_files, result = _gather_parquet_files(table_dir), []
    if parquet_files:
        result = (
            pa.concat_tables(parquet.read_table(file, filters=filters) for file in parquet_files)
        ).to_pylist()

    return result
