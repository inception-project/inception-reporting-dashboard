import json
import zipfile
from unittest.mock import patch

from inception_reports.project_loader import read_dir


def _write_archive(tmp_path, archive_name, exported_project, cas_files=None):
    archive_path = tmp_path / archive_name
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("exportedproject.json", exported_project)
        for cas_path, cas_content in cas_files or []:
            archive.writestr(cas_path, cas_content)
    return archive_path


@patch("cassis.load_cas_from_json")
def test_read_dir_skips_invalid_exportedproject_json(mock_load_cas, tmp_path):
    mock_load_cas.return_value = object()
    _write_archive(tmp_path, "broken.zip", "{not-json", [])

    projects = read_dir(
        str(tmp_path),
        selected_projects_data={"broken": -1},
        mode="manual",
        compute_stats=lambda cas, excluded: ({}, set()),
    )

    assert projects == []


@patch("cassis.load_cas_from_json")
def test_read_dir_skips_projects_without_source_documents(mock_load_cas, tmp_path):
    mock_load_cas.return_value = object()
    _write_archive(
        tmp_path,
        "empty.zip",
        json.dumps({"description": "#tag", "source_documents": []}),
        [],
    )

    projects = read_dir(
        str(tmp_path),
        selected_projects_data={"empty": -1},
        mode="manual",
        compute_stats=lambda cas, excluded: ({}, set()),
    )

    assert projects == []


@patch("inception_reports.project_loader.get_snomed_semantic_tag_map")
@patch("cassis.load_cas_from_json")
def test_read_dir_fetches_snomed_labels_in_api_mode(
    mock_load_cas, mock_get_snomed_semantic_tag_map, tmp_path
):
    mock_load_cas.return_value = object()
    mock_get_snomed_semantic_tag_map.return_value = {"SNOMED:123": "disorder"}
    _write_archive(
        tmp_path,
        "project.alpha.zip",
        json.dumps(
            {
                "description": "#tag",
                "source_documents": [
                    {"name": "doc1.txt", "state": "ANNOTATION_IN_PROGRESS"}
                ],
                "knowledge_bases": [
                    {"id": "kb1", "name": "SNOMED", "enabled": True}
                ],
                "layers": [{"features": [{"type": "kb:<ANY>"}]}],
            }
        ),
        [("annotation/doc1.txt/annotator1.json", "{}")],
    )

    projects = read_dir(
        str(tmp_path),
        selected_projects_data={"project.alpha": 123},
        mode="api",
        api_url="https://example.org",
        auth=("user", "pass"),
        compute_stats=lambda cas, excluded: (
            {"Concept": {"total": 1, "features": {"SNOMED:123": 1}}},
            {"SNOMED:123"},
        ),
    )

    assert projects[0].snomed_labels == {"SNOMED:123": "disorder"}
    mock_get_snomed_semantic_tag_map.assert_called_once_with(
        "https://example.org",
        123,
        "kb1",
        {"SNOMED:123"},
        auth=("user", "pass"),
        ca_bundle=None,
        verify_ssl=True,
    )
