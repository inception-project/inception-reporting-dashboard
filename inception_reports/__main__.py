# Licensed to the Technische Universität Darmstadt under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The Technische Universität Darmstadt
# licenses this file to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import argparse
from streamlit.web import cli
import logging
import logging.config
import yaml
import importlib


def setup_logging(log_level: str = None, log_dir: str = None):
    """
    Sets up logging configuration.

    Args:
        log_level: The desired log level (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
        log_dir: The directory where log files will be stored.
    """
    # Use importlib.resources to access logging_config.yaml
    with importlib.resources.path(
        "inception_reports.config", "logging_config.yaml"
    ) as config_path:
        # Read logging configuration from YAML file
        with open(config_path, "r") as file:
            logging_config = yaml.safe_load(file)

        # Override log level and directory if provided
        log_level = log_level or os.getenv("INCEPTION_LOG_LEVEL", None)
        log_dir = log_dir or os.getenv("INCEPTION_LOG_DIR", "inception_reports_logs")

        # Override log file path
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        logging_config["handlers"]["file"]["filename"] = os.path.join(
            log_dir, "app.log"
        )

        # Apply logging configuration
        logging.config.dictConfig(logging_config)

        # Set log level dynamically if provided
        if log_level:
            logger = logging.getLogger()  # Root logger
            logger.setLevel(log_level.upper())


def main():
    parser = argparse.ArgumentParser(
        description="Generate plots for your INCEpTION project."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-m",
        "--manager",
        help="You are managing a single project, or a single location.",
        action="store_true",
    )
    group.add_argument(
        "-l",
        "--lead",
        help="You are leading multiple projects, or multiple locations.",
        action="store_true",
    )

    parser.add_argument(
        "-o", "--output", help="Output directory for the generated plots.", required=False
    )

    parser.add_argument(
        "--logger",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )
    args = parser.parse_args()

    setup_logging(args.logger)
    log = logging.getLogger(__name__)

    if args.output:
        os.environ["INCEPTION_OUTPUT_DIR"] = args.output
        print(f"Output directory set to: {args.output}")

    if args.manager:
        log.info("STARTING INCEpTION Reporting Dashboard - Manager")
        sys.argv = [
            "streamlit",
            "run",
            f"{os.path.dirname(os.path.realpath(__file__))}/generate_reports_manager.py",
        ]
    elif args.lead:
        log.info("STARTING INCEpTION Reporting Dashboard - Lead")
        sys.argv = [
            "streamlit",
            "run",
            f"{os.path.dirname(os.path.realpath(__file__))}/generate_reports_lead.py",
        ]
    sys.exit(cli.main())
