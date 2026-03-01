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

import streamlit as st

PAGE_STYLES = """
<style>
.block-container {
    padding-top: 0rem;
    padding-bottom: 5rem;
    padding-left: 5rem;
    padding-right: 5rem;
}
</style>

<style>
div[data-testid="stHorizontalBlock"] {
    margin-top: 1rem;
    border: thick double #999999;
    box-shadow: 0px 0px 10px #999999;
}
</style>

<style>
section.main > div {max-width:95%}
</style>
"""


def apply_dashboard_styles() -> None:
    st.markdown(PAGE_STYLES, unsafe_allow_html=True)


def render_version_status(
    current_version: str, latest_version: str | None = None
) -> None:
    version_message = f"Dashboard Version: {current_version}"
    if latest_version:
        st.sidebar.warning(f"{version_message} (Update available: {latest_version})")
        return
    st.sidebar.info(version_message)


def create_progress_widgets(progress_container=None):
    if progress_container is None:
        return None, None, None

    container = progress_container.container()
    progress_label = container.empty()
    progress_bar = container.progress(0)

    def progress_callback(done, total, current_project=None, current_doc=None):
        if progress_label is None or progress_bar is None:
            return

        if total <= 0:
            progress_label.text("No CAS files found to process.")
            progress_bar.progress(0)
            return

        fraction = min(max(done / total, 0.0), 1.0)
        percent = int(fraction * 100)
        message = f"Generating reports: {done}/{total} CAS files"
        if current_project:
            message += f" • Project: {current_project}"
        if current_doc:
            message += f" • Document: {current_doc}"
        progress_label.text(message)
        progress_bar.progress(percent)

    return progress_label, progress_bar, progress_callback


def render_dashboard_title() -> None:
    st.write(
        "<style> h1 {text-align: center; margin-bottom: 50px, } </style>",
        unsafe_allow_html=True,
    )
    st.title("INCEpTION Reporting Dashboard")
    st.write("<hr>", unsafe_allow_html=True)


def render_project_header(project_name: str, project_tags: list[str] | None) -> None:
    tags_text = ", ".join(project_tags) if project_tags else "No tags available"
    st.write(
        f"<div style='text-align: center; font-size: 18px;'><b>Project Name</b>: {project_name} <br> <b>Tags</b>: {tags_text}</div>",
        unsafe_allow_html=True,
    )


def render_missing_curated_documents_warning(project_name: str) -> None:
    st.warning(
        f"No curated documents found in project **{project_name}** - "
        "showing annotations break down for all other documents instead."
    )
