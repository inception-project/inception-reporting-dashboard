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


import json
import zipfile
from datetime import datetime
from unittest.mock import Mock, patch

from inception_reports.generate_reports_manager import (
    find_element_by_name,
    read_dir,
)


def test_find_element_by_name():
    e1 = Mock()
    e1.name = "type.A"
    e1.uiName = "A-Type"

    e2 = Mock()
    e2.name = "type.B"
    e2.uiName = "B-Type"

    assert find_element_by_name([e1, e2], "type.B") == "B-Type"
    assert find_element_by_name([e1, e2], "type.X") == "X"
    assert find_element_by_name([], "type.Y") == "Y"


@patch("inception_reports.generate_reports_manager.compute_cas_stats")
@patch("cassis.load_cas_from_json")
@patch("zipfile.is_zipfile", return_value=True)
def test_read_dir_parses_zip_and_computes_stats(
    mock_is_zip, mock_load_cas, mock_compute_stats, tmp_path
):
    mock_compute_stats.return_value = (
        {"MockType": {"total": 2, "features": {"x": 1}}},
        {"SNOMED:123"},
    )
    mock_load_cas.return_value = object()  # don't break .get()

    with patch("os.listdir", return_value=["project1.zip"]):
        zip_path = tmp_path / "project1.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            meta = {
                "description": "#tagA #tagB",
                "source_documents": [
                    {"name": "doc1.txt", "state": "ANNOTATION_IN_PROGRESS"},
                    {"name": "doc2.txt", "state": "CURATION_FINISHED"},
                ],
            }
            z.writestr("exportedproject.json", json.dumps(meta))
            z.writestr("annotation/doc1.txt/annotator1.json", "{}")
            z.writestr("annotation/doc1.txt/INITIAL_CAS.json", "{}")
            z.writestr("curation/doc2.txt/INITIAL_CAS.json", "{}")

        selected = {"project1": -1}

        projects = read_dir(
            str(tmp_path), selected_projects_data=selected, mode="manual"
        )

    project = projects[0]
    annotations = project["annotations"]

    assert set(annotations["doc1.txt"].keys()) == {"annotator1"}
    assert set(annotations["doc2.txt"].keys()) == {"INITIAL_CAS"}
    assert mock_compute_stats.call_count == 2


def test_export_data(tmp_path, monkeypatch):
    """
    Ensures:
      - export_data() writes a JSON file into INCEPTION_OUTPUT_DIR
      - Filename includes today's date
    """

    # Mock version info (should no longer be used by export_data)
    from inception_reports import generate_reports_manager as gm

    # dashboard_version should be provided upstream
    project_data = {
        "project_name": "projX",
        "project_tags": ["tag1"],
        "doc_categories": {"NEW": 1},
        "dashboard_version": "9.9.9",
        "created": "2024-01-01",
    }

    outdir = tmp_path / "out"
    outdir.mkdir()
    monkeypatch.setenv("INCEPTION_OUTPUT_DIR", str(outdir))

    gm.export_data(project_data)

    today = datetime.now().strftime("%Y_%m_%d")
    outfile = outdir / f"projX_{today}.json"
    assert outfile.exists(), "Output file should exist"

    with open(outfile) as f:
        exported = json.load(f)

    # dashboard_version MUST remain whatever was passed in
    assert exported["dashboard_version"] == "9.9.9"

    # Check all fields preserved
    for key, value in project_data.items():
        assert exported[key] == value
