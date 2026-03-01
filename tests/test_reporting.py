from inception_reports.reporting import build_project_report


def test_build_project_report_filters_to_curated_documents():
    project = {
        "name": "project_one.zip",
        "tags": ["tag1"],
        "documents": [
            {"name": "doc1.txt", "state": "CURATION_FINISHED"},
            {"name": "doc2.txt", "state": "ANNOTATION_IN_PROGRESS"},
        ],
        "annotations": {
            "doc1.txt": {
                "ann1": {
                    "Token": {"total": 10, "features": {"token": 10}},
                    "Concept": {"total": 2, "features": {"SNOMED:123": 2}},
                }
            },
            "doc2.txt": {
                "ann1": {
                    "Token": {"total": 5, "features": {"token": 5}},
                    "Concept": {"total": 1, "features": {"SNOMED:456": 1}},
                }
            },
        },
        "snomed_labels": {"SNOMED:123": "disorder", "SNOMED:456": "finding"},
        "inception_version": "38.4",
    }

    report = build_project_report(
        project=project,
        aggregation_mode="Sum",
        dashboard_version="0.9.7",
        show_only_curated=True,
    )

    assert report.show_only_curated is True
    assert report.has_curated_documents is True
    assert report.type_counts["Token"]["documents"] == {"doc1.txt": 10}
    assert report.data["doc_token_categories"]["CURATION_FINISHED"] == 10
    assert report.data["type_counts"]["Concept"]["features"]["disorder"] == {
        "CURATION_FINISHED": 2
    }


def test_build_project_report_falls_back_when_no_curated_documents():
    project = {
        "name": "project_two.zip",
        "tags": None,
        "documents": [{"name": "doc1.txt", "state": "ANNOTATION_IN_PROGRESS"}],
        "annotations": {
            "doc1.txt": {"ann1": {"Token": {"total": 4, "features": {"token": 4}}}}
        },
        "snomed_labels": {},
        "inception_version": "38.4",
    }

    report = build_project_report(
        project=project,
        aggregation_mode="Sum",
        dashboard_version="0.9.7",
        show_only_curated=True,
    )

    assert report.show_only_curated is False
    assert report.has_curated_documents is False
    assert report.type_counts["Token"]["documents"] == {"doc1.txt": 4}
