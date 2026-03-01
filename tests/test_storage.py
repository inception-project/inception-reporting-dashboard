import io
import json
import zipfile
from datetime import date

from inception_reports.storage import build_reports_archive, export_project_data


def test_export_project_data_preserves_multi_dot_project_names(tmp_path):
    project_data = {
        "project_name": "alpha.v2",
        "created": "2024-01-01",
        "dashboard_version": "0.9.7",
    }

    output_path = export_project_data(
        project_data,
        output_directory=str(tmp_path),
        current_date=date(2024, 1, 2),
    )

    assert output_path.name == "alpha.v2_2024_01_02.json"
    exported = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported["project_name"] == "alpha.v2"


def test_build_reports_archive_preserves_multi_dot_project_names():
    reports = [
        {"project_name": "alpha.v2", "created": "2024-01-01"},
        {"project_name": "beta.release.3", "created": "2024-01-02"},
    ]

    archive_data = build_reports_archive(reports)

    with zipfile.ZipFile(io.BytesIO(archive_data), "r") as archive:
        assert sorted(archive.namelist()) == [
            "alpha.v2_2024-01-01.json",
            "beta.release.3_2024-01-02.json",
        ]
