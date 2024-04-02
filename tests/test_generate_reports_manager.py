import json
import os
import tempfile
import zipfile
from unittest.mock import Mock, patch

from inception_reports.generate_reports_manager import *


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
            zipf.writestr('annotations/annotation1/INITIAL_CAS.json', json.dumps(annotation_content))

        projects = read_dir(temp_dir)

        assert len(projects) == 1, "Should correctly parse zip files and extract project data"
        project = projects[0]
        assert project['name'] == zip_name, "Project name should match the zip file name"
        assert set(project['tags']) == {"tag1", "tag2"}, "Should extract correct tags from project metadata"
        assert project['documents'] == ["doc1.txt", "doc2.txt"], "Should list all source documents"
        assert 'annotation1' in project['annotations'], "Should include annotations in the project data"
        assert project['annotations']['annotation1'] == "MockCASObject", "Should load CAS objects for annotations"

