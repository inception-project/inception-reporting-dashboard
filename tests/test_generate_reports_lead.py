import os
from unittest.mock import MagicMock, patch

from inception_reports.generate_reports_lead import *


def test_get_unique_tags():
    projects = [
        {"project_tags": ["tag1", "tag2"]},
        {"project_tags": ["tag2", "tag3"]},
        {"project_tags": ["tag3", "tag4"]},
    ]
    expected_result = ["tag1", "tag2", "tag3", "tag4"]
    assert get_unique_tags(projects).sort() == expected_result.sort()


def fake_json_loads(file):
    """
    Mimics json.load operation for a mocked file object.
    This function will be called by json.load(mocked_open_instance).
    """
    return {
        "project_name": "project_1",
        "project_tags": ["tag1", "tag2", "tag3"],
        "doc_categories": {
            "ANNOTATION_IN_PROGRESS": 12,
            "ANNOTATION_FINISHED": 5,
            "CURATION_IN_PROGRESS": 0,
            "CURATION_FINISHED": 0,
            "NEW": 4,
        },
    }


@patch("os.listdir", MagicMock(return_value=["project1.json"]))
@patch("builtins.open", new_callable=MagicMock)
@patch("json.load", MagicMock(side_effect=fake_json_loads))
def test_read_dir(mock_open):
    dir = "some/dir"
    expected = [
        {
            "project_name": "project_1",
            "project_tags": ["tag1", "tag2", "tag3"],
            "doc_categories": {
                "ANNOTATION_IN_PROGRESS": 12,
                "ANNOTATION_FINISHED": 5,
                "CURATION_IN_PROGRESS": 0,
                "CURATION_FINISHED": 0,
                "NEW": 4,
            },
        }
    ]

    result = read_dir(dir)

    mock_open.assert_called_once_with(os.path.join(dir, "project1.json"), "r")
    assert result == expected, "Expected result does not match the actual result."


def test_get_unique_tags():
    projects = [
        {"project_tags": ["tag1", "tag2"]},
        {"project_tags": ["tag2", "tag3"]},
        {"project_tags": ["tag3", "tag4"]},
    ]
    expected_result = ["tag1", "tag2", "tag3", "tag4"]
    assert get_unique_tags(projects).sort() == expected_result.sort()


def fake_json_loads(file):
    """
    Mimics json.load operation for a mocked file object.
    This function will be called by json.load(mocked_open_instance).
    """
    return {
        "project_name": "project_1",
        "project_tags": ["tag1", "tag2", "tag3"],
        "doc_categories": {
            "ANNOTATION_IN_PROGRESS": 12,
            "ANNOTATION_FINISHED": 5,
            "CURATION_IN_PROGRESS": 0,
            "CURATION_FINISHED": 0,
            "NEW": 4,
        },
    }


@patch("os.listdir", MagicMock(return_value=["project1.json"]))
@patch("builtins.open", new_callable=MagicMock)
@patch("json.load", MagicMock(side_effect=fake_json_loads))
def test_read_dir(mock_open):
    dir = "some/dir"
    expected = [
        {
            "project_name": "project_1",
            "project_tags": ["tag1", "tag2", "tag3"],
            "doc_categories": {
                "ANNOTATION_IN_PROGRESS": 12,
                "ANNOTATION_FINISHED": 5,
                "CURATION_IN_PROGRESS": 0,
                "CURATION_FINISHED": 0,
                "NEW": 4,
            },
        }
    ]

    result = read_dir(dir)

    mock_open.assert_called_once_with(os.path.join(dir, "project1.json"), "r")
    assert result == expected, "Expected result does not match the actual result."


def test_plot_project_progress():
    project_data = {
        "project_name": "project_1",
        "project_tags": ["tag1", "tag2", "tag3"],
        "doc_categories": {
            "ANNOTATION_IN_PROGRESS": 12,
            "ANNOTATION_FINISHED": 5,
            "CURATION_IN_PROGRESS": 0,
            "CURATION_FINISHED": 0,
            "NEW": 4,
        },
    }

    plot_project_progress(project_data)
    assert True, "Should not raise any exceptions"
