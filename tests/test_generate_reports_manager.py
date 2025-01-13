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
import os
import tempfile
import zipfile
from unittest.mock import Mock, patch
from datetime import datetime

from inception_reports.generate_reports_manager import find_element_by_name, read_dir, export_data


def test_find_element_by_name():
    MockElement_1 = Mock()
    MockElement_1.configure_mock(**{"name": "element1", "uiName": "UI Element 1"})
    MockElement_2 = Mock()
    MockElement_2.configure_mock(**{"name": "element2", "uiName": "UI Element 2"})
    MockElement_3 = Mock()
    MockElement_3.configure_mock(**{"name": "element3", "uiName": "UI Element 3"})

    element_list = [MockElement_1, MockElement_2, MockElement_3]

    result = find_element_by_name(element_list, "element2")
    assert result == "UI Element 2", "Should return the uiName of the found element"

    result = find_element_by_name(element_list, "element4")
    assert result == "element4", "Should return the last part of the name if not found"

    result = find_element_by_name([], "element2")
    assert result == "element2", "Should handle empty input list"



@patch('cassis.load_cas_from_json', return_value="MockCASObject")
@patch('os.listdir', return_value=['project1.zip'])
@patch('zipfile.is_zipfile', return_value=True)
@patch('shutil.rmtree')
def test_read_dir_correctly_parses_zip_files(mock_rmtree, mock_is_zipfile, mock_listdir, mock_cas_loader):
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_name = "project1.zip"
        zip_path = os.path.join(temp_dir, zip_name)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            project_meta = {
                "description": "A mock project #tag1 #tag2",
                "source_documents": ["doc1.txt", "doc2.txt"]
            }
            zipf.writestr('exportedproject.json', json.dumps(project_meta))

            annotation_content = {"dummy": "content"}
            zipf.writestr('annotation/doc1/annotator1.json', json.dumps(annotation_content))

        projects = read_dir(temp_dir)

        assert len(projects) == 1, "Should correctly parse zip files and extract project data"
        project = projects[0]
        print(project['annotations'])
        assert project['name'] == zip_name, "Project name should match the zip file name"
        assert set(project['tags']) == {"tag1", "tag2"}, "Should extract correct tags from project metadata"
        assert project['documents'] == ["doc1.txt", "doc2.txt"], "Should list all source documents"
        assert 'doc1' in project['annotations'], "Should include annotations in the project data"
        assert project['annotations']['doc1'] == "MockCASObject", "Should load CAS objects for annotations"


def test_export_data(tmpdir):
    project_data = {
        "project_name": "project1",
        "project_tags": ["tag1", "tag2"],
        "doc_categories": {
            "NEW": 10,
            "ANNOTATION_IN_PROGRESS": 5,
            "ANNOTATION_FINISHED": 15,
            "CURATION_IN_PROGRESS": 3,
            "CURATION_FINISHED": 7,
        },
        "created": "2024-06-11"
    }

    current_date = datetime.now().strftime("%Y_%m_%d")
    output_directory = tmpdir.mkdir("output")
    os.environ["INCEPTION_OUTPUT_DIR"] = str(output_directory)
    export_data(project_data)

    expected_file_path = os.path.join(output_directory, f"{project_data['project_name']}_{current_date}.json")
    print(expected_file_path)
    assert os.path.exists(expected_file_path)

    with open(expected_file_path, "r") as output_file:
        exported_data = json.load(output_file)

    assert exported_data == project_data