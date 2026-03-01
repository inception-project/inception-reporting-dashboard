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

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from inception_reports.models import AggregatedTypeCounts, ExportedProjectData

PIE_LABELS = [
    "New",
    "Annotation In Progress",
    "Annotation Finished",
    "Curation In Progress",
    "Curation Finished",
]
MAX_FEATURES_PER_TYPE = 30


def build_documents_status_figure(project_data: ExportedProjectData) -> go.Figure:
    data_sizes_docs = [
        project_data.doc_categories["NEW"],
        project_data.doc_categories["ANNOTATION_IN_PROGRESS"],
        project_data.doc_categories["ANNOTATION_FINISHED"],
        project_data.doc_categories["CURATION_IN_PROGRESS"],
        project_data.doc_categories["CURATION_FINISHED"],
    ]
    data_sizes_tokens = [
        project_data.doc_token_categories["NEW"],
        project_data.doc_token_categories["ANNOTATION_IN_PROGRESS"],
        project_data.doc_token_categories["ANNOTATION_FINISHED"],
        project_data.doc_token_categories["CURATION_IN_PROGRESS"],
        project_data.doc_token_categories["CURATION_FINISHED"],
    ]

    documents_frame = pd.DataFrame({"Labels": PIE_LABELS, "Sizes": data_sizes_docs})
    tokens_frame = pd.DataFrame({"Labels": PIE_LABELS, "Sizes": data_sizes_tokens})

    figure = go.Figure()
    figure.add_trace(
        go.Pie(
            labels=documents_frame["Labels"],
            values=documents_frame["Sizes"],
            sort=False,
            hole=0.4,
            hoverinfo="percent+label",
            textinfo="value",
        )
    )
    figure.add_trace(
        go.Pie(
            labels=tokens_frame["Labels"],
            values=tokens_frame["Sizes"],
            sort=False,
            hole=0.4,
            hoverinfo="percent+label",
            textinfo="value",
            visible=False,
        )
    )

    figure.update_layout(
        title=dict(
            text="Documents Status",
            font=dict(size=24),
            y=0.95,
            x=0.5,
            xanchor="center",
        ),
        font=dict(size=18),
        legend=dict(font=dict(size=12), y=0.5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40),
        updatemenus=[
            {
                "buttons": [
                    {
                        "label": "Documents",
                        "method": "update",
                        "args": [
                            {"visible": [True, False]},
                            {"title": "Documents Status"},
                        ],
                    },
                    {
                        "label": "Tokens",
                        "method": "update",
                        "args": [
                            {"visible": [False, True]},
                            {"title": "Tokens Status"},
                        ],
                    },
                ],
                "direction": "down",
                "showactive": True,
            }
        ],
    )
    return figure


def build_annotation_breakdown_figure(
    type_counts: AggregatedTypeCounts, show_only_curated: bool
) -> go.Figure:
    figure = go.Figure()
    main_traces = 0
    total_feature_traces = 0
    feature_buttons = []

    for category, details in type_counts.items():
        figure.add_trace(
            go.Bar(
                y=[category],
                x=[details["total"]],
                text=[details["total"]],
                textposition="auto",
                name=category.capitalize(),
                visible=True,
                orientation="h",
                hoverinfo="x+y",
            )
        )
        main_traces += 1

    for category, details in type_counts.items():
        features_items = list(details["features"].items())
        if len(features_items) < 2:
            continue

        top_features = features_items[:MAX_FEATURES_PER_TYPE]
        category_start = total_feature_traces

        for subcategory, value in top_features:
            total_value = sum(value.values()) if isinstance(value, dict) else value
            figure.add_trace(
                go.Bar(
                    y=[subcategory],
                    x=[total_value],
                    text=[total_value],
                    textposition="auto",
                    name=subcategory,
                    visible=False,
                    orientation="h",
                    hoverinfo="x+y",
                )
            )
            total_feature_traces += 1

        visibility = [False] * main_traces + [False] * total_feature_traces
        for index in range(category_start, total_feature_traces):
            visibility[main_traces + index] = True

        feature_buttons.append(
            {
                "args": [{"visible": visibility}],
                "label": category,
                "method": "update",
            }
        )

    figure.update_layout(
        title=dict(
            text=f"Types of Annotations {'(Curated Docs)' if show_only_curated else '(All Docs)'}",
            font=dict(size=24),
            y=0.95,
            x=0.45,
            xanchor="center",
        ),
        xaxis_title="Number of Annotations",
        barmode="overlay",
        height=max(200, min(160 * len(type_counts), 500)),
        font=dict(size=18),
        legend=dict(font=dict(size=10)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10),
        colorway=px.colors.qualitative.Plotly,
        updatemenus=[
            {
                "buttons": [
                    {
                        "args": [
                            {
                                "visible": [True] * main_traces
                                + [False] * total_feature_traces
                            }
                        ],
                        "label": "Overview",
                        "method": "update",
                    }
                ]
                + feature_buttons,
                "direction": "down",
                "showactive": True,
                "x": 0.45,
                "y": 1.15,
                "xanchor": "center",
                "yanchor": "top",
            }
        ],
    )
    return figure


def render_project_charts(
    project_data: ExportedProjectData,
    type_counts: AggregatedTypeCounts,
    show_only_curated: bool,
) -> None:
    pie_chart = build_documents_status_figure(project_data)
    bar_chart = build_annotation_breakdown_figure(type_counts, show_only_curated)

    col1, _, col3 = st.columns([1, 0.1, 1])
    with col1:
        st.plotly_chart(pie_chart)
    with col3:
        st.plotly_chart(bar_chart)
