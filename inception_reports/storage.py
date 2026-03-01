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
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any

from inception_reports.models import ExportedProjectData


def normalize_project_name(project_name: str) -> str:
    normalized_name = Path(project_name).name
    if normalized_name.lower().endswith(".zip"):
        return normalized_name[:-4]
    return normalized_name


def _serialize_project_data(
    project_data: ExportedProjectData | dict[str, Any],
) -> dict[str, Any]:
    if isinstance(project_data, ExportedProjectData):
        return project_data.as_dict()
    if is_dataclass(project_data):
        return asdict(project_data)
    return dict(project_data)


def get_output_directory(output_directory: str | None = None) -> Path:
    if output_directory:
        return Path(output_directory)

    configured_output_directory = os.getenv("INCEPTION_OUTPUT_DIR")
    if configured_output_directory:
        return Path(configured_output_directory)

    return Path.cwd() / "exported_project_data"


def export_project_data(
    project_data: ExportedProjectData | dict[str, Any],
    output_directory: str | None = None,
    current_date: date | None = None,
) -> Path:
    serialized_project_data = _serialize_project_data(project_data)
    export_date = (current_date or date.today()).strftime("%Y_%m_%d")
    destination = get_output_directory(output_directory)
    destination.mkdir(parents=True, exist_ok=True)

    project_name = normalize_project_name(serialized_project_data["project_name"])
    output_path = destination / f"{project_name}_{export_date}.json"
    output_path.write_text(
        json.dumps(serialized_project_data, indent=4), encoding="utf-8"
    )
    return output_path


def build_reports_archive(
    reports: list[ExportedProjectData | dict[str, Any]]
) -> bytes | None:
    if not reports:
        return None

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        for report in reports:
            serialized_report = _serialize_project_data(report)
            report_name = normalize_project_name(serialized_report["project_name"])
            file_name = f"{report_name}_{serialized_report['created']}.json"
            archive.writestr(file_name, json.dumps(serialized_report, indent=4))

    return zip_buffer.getvalue()
