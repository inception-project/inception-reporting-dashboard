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
from unittest.mock import MagicMock, patch

from inception_reports.generate_reports_lead import (
    get_unique_tags,
    plot_multiples,
    read_dir,
)


def test_get_unique_tags():
    """
    Test case for the get_unique_tags function.

    This test case verifies that the get_unique_tags function returns the expected result
    when given a list of projects with tags.
    """
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
    """
    Test case for the read_dir function.

    This test case verifies that the read_dir function correctly reads the contents of a directory and returns the expected result.

    Args:
        mock_open: A mock object for the built-in open function.

    Returns:
        None
    """

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
    """
    Test case for the plot_project_progress function.
    """
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
        "doc_token_categories": {
            "ANNOTATION_IN_PROGRESS": 13339,
            "ANNOTATION_FINISHED": 0,
            "CURATION_IN_PROGRESS": 8092,
            "CURATION_FINISHED": 0,
            "NEW": 0,
        },
        "created": "2024-06-11",
    }

    plot_multiples([project_data], ["tag1", "tag2", "tag3"])
    assert True, "Should not raise any exceptions"
