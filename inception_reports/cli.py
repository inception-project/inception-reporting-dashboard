# Licensed to the Technische Universitaet Darmstadt under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The Technische Universitaet Darmstadt
# licenses this file to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import argparse
import logging
import logging.config
import os
import sys
from importlib.resources import as_file, files
from pathlib import Path

import yaml
from streamlit.web import cli as streamlit_cli

DEFAULT_LOG_DIR = "inception_reports_logs"


def setup_logging(log_level: str | None = None, log_dir: str | None = None) -> None:
    log_level = log_level or os.getenv("INCEPTION_LOG_LEVEL")
    log_dir = Path(log_dir or os.getenv("INCEPTION_LOG_DIR", DEFAULT_LOG_DIR))
    log_dir.mkdir(parents=True, exist_ok=True)

    config_resource = files("inception_reports.config").joinpath("logging_config.yaml")
    with as_file(config_resource) as config_path:
        with open(config_path, "r", encoding="utf-8") as handle:
            logging_config = yaml.safe_load(handle)

    logging_config["handlers"]["file"]["filename"] = str(log_dir / "app.log")
    logging.config.dictConfig(logging_config)

    if log_level:
        logging.getLogger().setLevel(log_level.upper())


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch the INCEpTION reporting dashboard."
    )
    parser.add_argument(
        "-m",
        "--manager",
        action="store_true",
        help="Launch the manager dashboard. This is the default behavior.",
    )
    parser.add_argument(
        "-o", "--output", help="Output directory for generated reports.", required=False
    )
    parser.add_argument(
        "--logger",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level.",
    )
    parser.add_argument(
        "--ca-bundle",
        help="Path to a custom CA certificate file to trust.",
        required=False,
    )
    parser.add_argument(
        "--verify-ssl",
        choices=["true", "false"],
        default="true",
        help="Enable or disable SSL verification.",
    )
    return parser


def resolve_dashboard_script() -> str:
    return str(Path(__file__).with_name("generate_reports_manager.py"))


def apply_environment_overrides(args: argparse.Namespace) -> None:
    if args.output:
        os.environ["INCEPTION_OUTPUT_DIR"] = args.output

    if args.ca_bundle:
        os.environ["INCEPTION_CA_BUNDLE"] = args.ca_bundle

    os.environ["INCEPTION_VERIFY_SSL"] = args.verify_ssl


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)

    setup_logging(args.logger)
    apply_environment_overrides(args)

    logger = logging.getLogger(__name__)
    if args.output:
        logger.info("Output directory set to: %s", args.output)
    if args.ca_bundle:
        logger.info("CA bundle path set to: %s", args.ca_bundle)
    if args.verify_ssl == "false":
        logger.warning("SSL verification is disabled")

    logger.info("STARTING INCEpTION Reporting Dashboard - Manager")
    sys.argv = ["streamlit", "run", resolve_dashboard_script()]
    return streamlit_cli.main()
