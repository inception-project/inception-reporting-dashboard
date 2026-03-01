from inception_reports.manager_charts import (
    build_annotation_breakdown_figure,
    build_documents_status_figure,
)
from inception_reports.models import ExportedProjectData


def _project_data() -> ExportedProjectData:
    return ExportedProjectData(
        project_name="project.alpha",
        project_tags=["tag1"],
        doc_categories={
            "NEW": 1,
            "ANNOTATION_IN_PROGRESS": 2,
            "ANNOTATION_FINISHED": 3,
            "CURATION_IN_PROGRESS": 4,
            "CURATION_FINISHED": 5,
        },
        doc_token_categories={
            "NEW": 10,
            "ANNOTATION_IN_PROGRESS": 20,
            "ANNOTATION_FINISHED": 30,
            "CURATION_IN_PROGRESS": 40,
            "CURATION_FINISHED": 50,
        },
        type_counts={},
        aggregation_mode="Sum",
        created="2024-01-01",
        inception_version="38.4",
        dashboard_version="0.9.7",
    )


def test_build_documents_status_figure_has_document_and_token_traces():
    figure = build_documents_status_figure(_project_data())

    assert len(figure.data) == 2
    assert figure.layout.updatemenus[0].buttons[0].label == "Documents"
    assert figure.layout.updatemenus[0].buttons[1].label == "Tokens"


def test_build_annotation_breakdown_figure_adds_feature_drilldown():
    figure = build_annotation_breakdown_figure(
        {
            "Concept": {
                "total": 3,
                "documents": {"doc1.txt": 3},
                "features": {
                    "disorder": {"doc1.txt": 2},
                    "finding": {"doc1.txt": 1},
                },
            }
        },
        show_only_curated=True,
    )

    assert len(figure.data) == 3
    assert figure.layout.title.text == "Types of Annotations (Curated Docs)"
    assert figure.layout.updatemenus[0].buttons[1].label == "Concept"
