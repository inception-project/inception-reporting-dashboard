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

import io
import json
import os
import zipfile
from datetime import date
from pathlib import Path
from typing import Any


def normalize_project_name(project_name: str) -> str:
    normalized_name = Path(project_name).name
    if normalized_name.lower().endswith(".zip"):
        return normalized_name[:-4]
    return normalized_name


def get_output_directory(output_directory: str | None = None) -> Path:
    if output_directory:
        return Path(output_directory)

    configured_output_directory = os.getenv("INCEPTION_OUTPUT_DIR")
    if configured_output_directory:
        return Path(configured_output_directory)

    return Path.cwd() / "exported_project_data"


def export_project_data(
    project_data: dict[str, Any],
    output_directory: str | None = None,
    current_date: date | None = None,
) -> Path:
    export_date = (current_date or date.today()).strftime("%Y_%m_%d")
    destination = get_output_directory(output_directory)
    destination.mkdir(parents=True, exist_ok=True)

    project_name = normalize_project_name(project_data["project_name"])
    output_path = destination / f"{project_name}_{export_date}.json"
    output_path.write_text(json.dumps(project_data, indent=4), encoding="utf-8")
    return output_path


def build_reports_archive(reports: list[dict[str, Any]]) -> bytes | None:
    if not reports:
        return None

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        for report in reports:
            report_name = normalize_project_name(report["project_name"])
            file_name = f"{report_name}_{report['created']}.json"
            archive.writestr(file_name, json.dumps(report, indent=4))

    return zip_buffer.getvalue()
