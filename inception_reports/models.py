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

from dataclasses import asdict, dataclass
from typing import Any, TypeAlias, TypedDict


class ProjectDocument(TypedDict):
    name: str
    state: str


FeatureCounts: TypeAlias = dict[str, int]
PerDocumentCounts: TypeAlias = dict[str, int]


class CasTypeStats(TypedDict):
    total: int
    features: FeatureCounts


CasStats: TypeAlias = dict[str, CasTypeStats]
AnnotationSet: TypeAlias = dict[str, CasStats]
ProjectAnnotations: TypeAlias = dict[str, AnnotationSet]


class AggregatedTypeStats(TypedDict):
    total: int
    documents: PerDocumentCounts
    features: dict[str, PerDocumentCounts]


AggregatedTypeCounts: TypeAlias = dict[str, AggregatedTypeStats]


class ExportedTypeSummary(TypedDict, total=False):
    total: int
    total_by_status: dict[str, int]
    features: dict[str, dict[str, int]]


ExportedTypeCounts: TypeAlias = dict[str, ExportedTypeSummary]


@dataclass(frozen=True)
class LoadedProject:
    name: str
    tags: list[str] | None
    documents: list[ProjectDocument]
    annotations: ProjectAnnotations
    snomed_labels: dict[str, str]
    inception_version: str | None


@dataclass(frozen=True)
class ExportedProjectData:
    project_name: str
    project_tags: list[str] | None
    doc_categories: dict[str, int]
    doc_token_categories: dict[str, int]
    type_counts: ExportedTypeCounts
    aggregation_mode: str
    created: str
    inception_version: str | None
    dashboard_version: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
