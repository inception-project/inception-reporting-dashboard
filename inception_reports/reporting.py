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

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

import cassis
from inception_reports.models import (
    AggregatedTypeCounts,
    CasStats,
    ExportedProjectData,
    ExportedTypeCounts,
    LoadedProject,
    ProjectAnnotations,
    ProjectDocument,
)

DOCUMENT_STATES = (
    "NEW",
    "ANNOTATION_IN_PROGRESS",
    "ANNOTATION_FINISHED",
    "CURATION_IN_PROGRESS",
    "CURATION_FINISHED",
)

FEATURE_BREAKDOWN_EXPORT_TYPES = {"PHI", "Concept"}


@dataclass(frozen=True)
class ProjectReport:
    data: ExportedProjectData
    type_counts: AggregatedTypeCounts
    show_only_curated: bool
    has_curated_documents: bool


def _new_count_entry() -> dict[str, object]:
    return {"total": 0, "features": defaultdict(int)}


def find_element_by_name(element_list, name: str) -> str:
    for element in element_list:
        if element.name == name:
            return element.uiName
    return name.split(".")[-1]


def compute_cas_stats(cas, excluded_types: set[str]) -> tuple[CasStats, set[str]]:
    counts = defaultdict(_new_count_entry)
    snomed_ids = set()

    skip_features = {
        cassis.typesystem.FEATURE_BASE_NAME_BEGIN,
        cassis.typesystem.FEATURE_BASE_NAME_END,
        cassis.typesystem.FEATURE_BASE_NAME_SOFA,
        "literal",
    }

    try:
        layer_definitions = cas.select(
            "de.tudarmstadt.ukp.clarin.webanno.api.type.LayerDefinition"
        )
    except Exception:
        layer_definitions = []

    for annotation_type in cas.typesystem.get_types():
        if annotation_type.name in excluded_types:
            continue

        relevant_features = [
            feature
            for feature in annotation_type.all_features
            if feature.name not in skip_features
        ]
        if not relevant_features:
            continue

        is_concept_type = annotation_type.name == "gemtex.Concept"
        type_name = find_element_by_name(layer_definitions, annotation_type.name)
        type_entry = None

        for item in cas.select(annotation_type.name):
            if type_entry is None:
                type_entry = counts[type_name]

            type_entry["total"] += 1

            for feature in relevant_features:
                value = item.get(feature.name)
                if value is None:
                    continue
                if is_concept_type and feature.name == "id":
                    snomed_ids.add(value)
                type_entry["features"][value] += 1

    return counts, snomed_ids


def _merge_counts(counts_list: list[CasStats]) -> CasStats:
    merged = defaultdict(_new_count_entry)
    for type_counts in counts_list:
        for type_name, values in type_counts.items():
            merged[type_name]["total"] += values["total"]
            for feature_name, feature_count in values["features"].items():
                merged[type_name]["features"][feature_name] += feature_count
    return merged


def _average_counts(counts_list: list[CasStats]) -> CasStats:
    if not counts_list:
        return {}

    averaged = _merge_counts(counts_list)
    divisor = len(counts_list)
    for values in averaged.values():
        values["total"] = round(values["total"] / divisor)
        for feature_name in list(values["features"].keys()):
            values["features"][feature_name] = round(
                values["features"][feature_name] / divisor
            )
    return averaged


def _max_counts(counts_list: list[CasStats]) -> CasStats:
    best_counts = {}
    best_total = -1

    for type_counts in counts_list:
        total = sum(values["total"] for values in type_counts.values())
        if total > best_total:
            best_total = total
            best_counts = type_counts

    return best_counts


def _aggregate_document_counts(
    counts_list: list[CasStats], aggregation_mode: str
) -> CasStats:
    if aggregation_mode == "Average":
        return _average_counts(counts_list)
    if aggregation_mode == "Max":
        return _max_counts(counts_list)
    return _merge_counts(counts_list)


def get_type_counts(
    annotations: ProjectAnnotations,
    snomed_labels: dict[str, str] | None = None,
    aggregation_mode: str = "Sum",
) -> AggregatedTypeCounts:
    type_counts: AggregatedTypeCounts = {}

    for document_name, annotator_map in annotations.items():
        cas_stats_list = list(annotator_map.values())
        if not cas_stats_list:
            continue

        combined_counts = _aggregate_document_counts(cas_stats_list, aggregation_mode)

        if snomed_labels:
            concept_counts = combined_counts.get("Concept")
            if concept_counts:
                mapped_features = defaultdict(int)
                for raw_value, count in concept_counts["features"].items():
                    label = snomed_labels.get(raw_value, raw_value)
                    mapped_features[label] += count
                concept_counts["features"] = mapped_features

        for type_name, values in combined_counts.items():
            if type_name not in type_counts:
                type_counts[type_name] = {"total": 0, "documents": {}, "features": {}}
            type_counts[type_name]["total"] += values["total"]
            type_counts[type_name]["documents"][document_name] = values["total"]

            for feature_name, feature_count in values["features"].items():
                feature_documents = type_counts[type_name]["features"].setdefault(
                    feature_name, {}
                )
                feature_documents[document_name] = feature_count

    for type_name, values in type_counts.items():
        values["features"] = dict(
            sorted(
                values["features"].items(),
                key=lambda item: sum(item[1].values()),
                reverse=True,
            )
        )

    return dict(
        sorted(type_counts.items(), key=lambda item: item[1]["total"], reverse=True)
    )


def summarize_document_categories(project_documents: list[ProjectDocument]) -> dict[str, int]:
    categories = {state: 0 for state in DOCUMENT_STATES}
    for document in project_documents:
        state = document.get("state")
        if state in categories:
            categories[state] += 1
    return categories


def summarize_token_categories(
    project_documents: list[ProjectDocument], type_counts: AggregatedTypeCounts
) -> dict[str, int]:
    categories = {state: 0 for state in DOCUMENT_STATES}
    token_documents = type_counts.get("Token", {}).get("documents", {})

    for document in project_documents:
        state = document.get("state")
        if state in categories:
            categories[state] += token_documents.get(document["name"], 0)

    return categories


def get_curated_document_names(project_documents: list[ProjectDocument]) -> set[str]:
    return {
        document["name"]
        for document in project_documents
        if document.get("state") == "CURATION_FINISHED"
    }


def filter_type_counts_to_documents(
    type_counts: AggregatedTypeCounts, allowed_documents: set[str]
) -> AggregatedTypeCounts:
    filtered_counts: AggregatedTypeCounts = {}

    for type_name, values in type_counts.items():
        document_counts = {
            document_name: count
            for document_name, count in values["documents"].items()
            if document_name in allowed_documents
        }
        if not document_counts:
            continue

        feature_counts = {}
        for feature_name, feature_documents in values["features"].items():
            matching_documents = {
                document_name: count
                for document_name, count in feature_documents.items()
                if document_name in allowed_documents
            }
            if matching_documents:
                feature_counts[feature_name] = matching_documents

        filtered_counts[type_name] = {
            "total": sum(document_counts.values()),
            "documents": document_counts,
            "features": feature_counts,
        }

    return filtered_counts


def build_exported_type_counts(
    type_counts: AggregatedTypeCounts, project_documents: list[ProjectDocument]
) -> ExportedTypeCounts:
    exported_counts: ExportedTypeCounts = {}
    document_states = {
        document["name"]: document.get("state", "UNKNOWN")
        for document in project_documents
    }

    for category, details in type_counts.items():
        total_by_status = defaultdict(int)
        for document_name, count in details["documents"].items():
            state = document_states.get(document_name, "UNKNOWN")
            total_by_status[state] += count

        exported_counts[category] = {
            "total": details["total"],
            "total_by_status": dict(total_by_status),
        }

        if category not in FEATURE_BREAKDOWN_EXPORT_TYPES:
            continue

        feature_breakdown = defaultdict(lambda: defaultdict(int))
        for feature_name, document_counts in details["features"].items():
            for document_name, count in document_counts.items():
                state = document_states.get(document_name, "UNKNOWN")
                feature_breakdown[feature_name][state] += count

        exported_counts[category]["features"] = {
            feature_name: dict(state_counts)
            for feature_name, state_counts in feature_breakdown.items()
        }

    return exported_counts


def build_project_report(
    project: LoadedProject,
    aggregation_mode: str,
    dashboard_version: str | None,
    show_only_curated: bool,
) -> ProjectReport:
    full_type_counts = get_type_counts(
        project.annotations,
        project.snomed_labels,
        aggregation_mode,
    )
    curated_documents = get_curated_document_names(project.documents)
    use_curated_documents = show_only_curated and bool(curated_documents)
    visible_type_counts = (
        filter_type_counts_to_documents(full_type_counts, curated_documents)
        if use_curated_documents
        else full_type_counts
    )

    project_data = ExportedProjectData(
        project_name=project.name.removesuffix(".zip"),
        project_tags=project.tags,
        doc_categories=summarize_document_categories(project.documents),
        doc_token_categories=summarize_token_categories(
            project.documents, full_type_counts
        ),
        type_counts=build_exported_type_counts(full_type_counts, project.documents),
        aggregation_mode=aggregation_mode,
        created=date.today().isoformat(),
        inception_version=project.inception_version,
        dashboard_version=dashboard_version,
    )

    return ProjectReport(
        data=project_data,
        type_counts=visible_type_counts,
        show_only_curated=use_curated_documents,
        has_curated_documents=bool(curated_documents),
    )
