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



def main():
    parser = argparse.ArgumentParser(
        description="Generate plots for logs of your INCEpTION project."
    )
    parser.add_argument("filename", help="The name of the file to process")
    parser.add_argument(
        "--role",
        help="Your role in the project (project manager, project lead)",
        choices=["manager", "lead"],
        required=True,
    )
    args = parser.parse_args()
    filename = args.filename
    user_role = args.role

    if user_role == "manager":
        sys.argv = [
            "streamlit",
            "run",
            f"{os.path.dirname(os.path.realpath(__file__))}/generate_reports_manager.py",
            f"{filename}"
        ]
    elif user_role == "lead":
        sys.argv = [
            "streamlit",
            "run",
            f"{os.path.dirname(os.path.realpath(__file__))}/generate_reports_lead.py",
            f"{filename}"
        ]
    sys.exit(cli.main())