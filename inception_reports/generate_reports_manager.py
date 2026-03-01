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

import copy
import logging
import os
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from packaging.version import parse as parse_version
from pycaprio import Pycaprio
from inception_reports.dashboard_version import DASHBOARD_VERSION
from inception_reports.models import ExportedProjectData, LoadedProject
from inception_reports.project_loader import (
    create_directory_in_home,
    read_dir as load_projects_from_directory,
)
from inception_reports.reporting import (
    build_project_report,
    compute_cas_stats,
    find_element_by_name,
)
from inception_reports.storage import build_reports_archive, export_project_data
from inception_reports.storage import normalize_project_name

st.set_page_config(
    page_title="INCEpTION Reporting Dashboard",
    layout="wide",
    initial_sidebar_state=st.session_state.setdefault("sidebar_state", "expanded"),
)

if st.session_state.get("flag"):
    st.session_state.sidebar_state = st.session_state.flag
    del st.session_state.flag
    time.sleep(0.01)
    st.rerun()


log = logging.getLogger()


def startup():

    st.markdown(
        """

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
        """,
        unsafe_allow_html=True,
    )

    project_info = get_project_info()
    if project_info:
        current_version = project_info
        package_name = "inception-reports"
        latest_version = check_package_version(current_version, package_name)
        version_message = f"Dashboard Version: {current_version}"
        
        if latest_version and parse_version(current_version) < parse_version(latest_version):
            st.sidebar.warning(f"{version_message} (Update available: {latest_version})")
        else:
            st.sidebar.info(version_message)


def get_project_info():
    return DASHBOARD_VERSION


def check_package_version(current_version, package_name):
    try:
        response = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=5)
        if response.status_code == 200:
            latest_version = response.json()["info"]["version"]
            if parse_version(
                current_version
            ) < parse_version(latest_version):
                return latest_version
    except requests.RequestException:
        return None
    return None

def read_dir(
    dir_path: str,
    selected_projects_data: dict,
    mode: str,
    api_url: str = None,
    auth: tuple = None,
    progress_callback=None,
    ca_bundle: str = None,
    verify_ssl: bool = True,
) -> list[LoadedProject]:
    return load_projects_from_directory(
        dir_path=dir_path,
        selected_projects_data=selected_projects_data,
        mode=mode,
        api_url=api_url,
        auth=auth,
        progress_callback=progress_callback,
        ca_bundle=ca_bundle,
        verify_ssl=verify_ssl,
        compute_stats=compute_cas_stats,
    )


def login_to_inception(api_url, username, password, ca_bundle=None, verify_ssl=True):
    """
    Logs in to the Inception API using the provided API URL, username, and password.

    Args:
        api_url (str): The URL of the Inception API.
        username (str): The username for authentication.
        password (str): The password for authentication.
        ca_bundle (str, optional): Path to a custom CA certificate file. Defaults to None.
        verify_ssl (bool): SSL verification behavior:
            - True (default): Verify SSL certificates using system CAs + ca_bundle if provided
            - False: Disable SSL verification

    Returns:
        tuple: A tuple containing a boolean value indicating whether the login was successful and an instance of the Inception client.

    """
    if "http" not in api_url:
        api_url = f"http://{api_url}"
    button = st.sidebar.button("Login")
    if button:
        inception_client = Pycaprio(api_url, (username, password), ca_bundle=ca_bundle, verify=verify_ssl)
        try:
            inception_client.api.projects()
            st.sidebar.success("Login successful")
            return True, inception_client
        except Exception:
            st.sidebar.error("Login unsuccessful")
            return False, None
    return False, None


def select_method_to_import_data(progress_container=None):
    """
    Allows the user to select a method to import data for generating reports.
    """

    def init_progress():
        """
        Create a label + progress bar in the top-of-page container and return a
        Streamlit-friendly progress callback.

        Returns:
            (progress_label, progress_bar, progress_callback)
        """
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
            msg = f"Generating reports: {done}/{total} CAS files"
            if current_project:
                msg += f" • Project: {current_project}"
            if current_doc:
                msg += f" • Document: {current_doc}"
            progress_label.text(msg)
            progress_bar.progress(percent)

        return progress_label, progress_bar, progress_callback

    method = st.sidebar.radio(
        "Choose your method to import data:", ("Manually", "API"), index=1
    )

    # --- MANUAL IMPORT ---
    if method == "Manually":
        uploaded_files = st.sidebar.file_uploader(
            "Upload project files:", accept_multiple_files=True, type="zip"
        )

        button = st.sidebar.button("Generate Reports")
        if button:
            if uploaded_files:
                temp_dir = os.path.join(
                    os.path.expanduser("~"), ".inception_reports", "temp_uploads"
                )
                os.makedirs(temp_dir, exist_ok=True)

                for uploaded_file in uploaded_files:
                    file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.read())

                selected_projects = [
                    normalize_project_name(uploaded_file.name)
                    for uploaded_file in uploaded_files
                ]

                progress_label, progress_bar, progress_callback = init_progress()

                st.session_state["projects"] = read_dir(
                    dir_path=temp_dir,
                    selected_projects_data={name: -1 for name in selected_projects},
                    mode="manual",
                    progress_callback=progress_callback,
                )
                st.session_state["projects_folder"] = temp_dir

                if progress_label is not None and progress_bar is not None:
                    progress_label.text("Report generation complete.")
                    progress_bar.progress(100)

            st.session_state["method"] = "Manually"
            button = False

    # --- API IMPORT ---
    elif method == "API":
        projects_folder = f"{os.path.expanduser('~')}/.inception_reports/projects"
        os.makedirs(os.path.dirname(projects_folder), exist_ok=True)
        st.session_state["projects_folder"] = projects_folder

        api_url = st.sidebar.text_input("Enter API URL:", "")
        username = st.sidebar.text_input("Username:", "")
        password = st.sidebar.text_input("Password:", type="password", value="")

        inception_status = st.session_state.get("inception_status", False)
        inception_client = st.session_state.get("inception_client", None)

        # Get certificate configuration from environment variables
        ca_bundle = os.getenv("INCEPTION_CA_BUNDLE", None)
        verify_ssl_str = os.getenv("INCEPTION_VERIFY_SSL", "true")
        verify_ssl = verify_ssl_str.lower() != "false"

        if not inception_status:
            inception_status, inception_client = login_to_inception(
                api_url, username, password, ca_bundle=ca_bundle, verify_ssl=verify_ssl
            )
            st.session_state["inception_status"] = inception_status
            st.session_state["inception_client"] = inception_client

        if inception_status and "available_projects" not in st.session_state:
            inception_projects = inception_client.api.projects()
            st.session_state["available_projects"] = inception_projects

        if inception_status and "available_projects" in st.session_state:
            st.sidebar.write("Select the projects to import:")
            selected_projects = st.session_state.get("selected_projects", {})

            for inception_project in st.session_state["available_projects"]:
                project_name = inception_project.project_name
                project_id = inception_project.project_id
                selected_projects[project_id] = st.sidebar.checkbox(
                    project_name, value=False
                )
                st.session_state["selected_projects"] = selected_projects

            selected_projects_data = {}
            button = st.sidebar.button("Generate Reports")
            if button:
                # Determine which projects are actually selected
                selected_ids = [pid for pid, is_selected in selected_projects.items() if is_selected]
                if not selected_ids:
                    st.sidebar.warning("Please select at least one project to generate reports.")
                    return

                # --- TOP-OF-PAGE SPINNER + STATUS TEXT FOR EXPORT PHASE ---
                if progress_container is not None:
                    export_container = progress_container.container()
                else:
                    export_container = st.container()

                with export_container:
                    with st.spinner("Exporting selected projects from INCEpTION…"):

                        for _, project_id in enumerate(selected_ids, start=1):
                            project = inception_client.api.project(project_id)
                            project_name = project.project_name

                            selected_projects_data[project_name] = project_id
                            file_path = f"{projects_folder}/{project_name}.zip"

                            st.sidebar.write(f"Importing project: {project_name}")
                            log.info(
                                f"Importing project {project_name} into {file_path}"
                            )

                            project_export = inception_client.api.export_project(
                                project, "jsoncas"
                            )
                            with open(file_path, "wb") as f:
                                f.write(project_export)
                            log.debug("Import Success")

                # Clear spinner/status area before showing the CAS progress bar
                if progress_container is not None:
                    progress_container.empty()

                st.session_state["method"] = "API"

                # Now initialize the CAS-processing progress bar at the top
                progress_label, progress_bar, progress_callback = init_progress()

                st.session_state["projects"] = read_dir(
                    dir_path=projects_folder,
                    selected_projects_data=selected_projects_data,
                    api_url=api_url,
                    auth=(username, password),
                    mode="api",
                    progress_callback=progress_callback,
                    ca_bundle=ca_bundle,
                    verify_ssl=verify_ssl,
                )

                if progress_label is not None and progress_bar is not None:
                    progress_label.text("Report generation complete.")
                    progress_bar.progress(100)


    # --- AGGREGATION MODE SELECTOR (always visible once projects exist) ---
    if "projects" in st.session_state or "projects_folder" in st.session_state:
        st.sidebar.markdown("---")
        aggregation_mode = st.sidebar.radio(
            "Annotation Aggregation Mode",
            ("Sum", "Average", "Max"),
            index=0,
            help=(
                "How to combine multiple annotator CAS files per document:\n\n"
                "- **Sum**: Count all annotations from all annotators (default)\n"
                "- **Average**: Normalize counts by number of annotators\n"
                "- **Max**: Take the annotator with the most annotations"
            ),
        )
        st.session_state["aggregation_mode"] = aggregation_mode
    
    st.sidebar.markdown("---")
    # --- Visualization scope toggle ---
    show_only_curated = st.sidebar.checkbox(
        "Show only curated documents in bar chart",
        value=True,
        help="If checked, the annotation type bar chart will only include documents whose state is CURATION_FINISHED.",
    )
    st.session_state["show_only_curated"] = show_only_curated





def export_data(project_data: ExportedProjectData | dict):
    """
    Export project data to a JSON file, and store it in a directory named after the project and the current date.

    Parameters:
        project_data (dict): The data to be exported.
    """
    output_path = export_project_data(project_data)
    project_name = (
        project_data.project_name
        if isinstance(project_data, ExportedProjectData)
        else project_data["project_name"]
    )
    st.success(
        f"{normalize_project_name(project_name)} documents status exported successfully to {output_path.parent}"
    )


def create_zip_download(reports: list[ExportedProjectData]):
    """
    Create a zip file containing all generated JSON reports and provide a download button.
    """

    archive_data = build_reports_archive(reports)
    if archive_data:
        st.download_button(
            label="Download All Reports (ZIP)",
            file_name="all_reports.zip",
            mime="application/zip",
            data=archive_data,
        )


def plot_project_progress(project: LoadedProject) -> ExportedProjectData:
    """
    Generate a visual representation of project progress based on a DataFrame of log data.

    This function takes a DataFrame containing log data and generates
    visualizations to represent the progress of different documents. It calculates the
    total time spent on each document, divides it into sessions based on a specified
    threshold, and displays a pie chart showing the percentage of finished and remaining
    documents, along with a bar chart showing the total time spent on finished documents
    compared to the estimated time for remaining documents.

    Parameters:
        project (dict): A dict containing project information, namely the name, tags, annotations, and logs.

    """

    aggregation_mode = st.session_state.get("aggregation_mode", "Sum")
    show_only_curated = st.session_state.get("show_only_curated", True)
    report = build_project_report(
        project=project,
        aggregation_mode=aggregation_mode,
        dashboard_version=get_project_info(),
        show_only_curated=show_only_curated,
    )
    project_data = report.data
    type_counts = report.type_counts
    project_name = project_data.project_name
    project_tags = project_data.project_tags
    show_only_curated = report.show_only_curated

    if st.session_state.get("show_only_curated", True) and not report.has_curated_documents:
        st.warning(
            f"No curated documents found in project **{project.name}** - "
            "showing annotations break down for all other documents instead."
        )
        st.session_state["show_only_curated"] = False


    if project_tags:
        st.write(
            f"<div style='text-align: center; font-size: 18px;'><b>Project Name</b>: {project_name} <br> <b>Tags</b>: {', '.join(project.tags)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.write(
            f"<div style='text-align: center; font-size: 18px;'><b>Project Name</b>: {project_name} <br> <b>Tags</b>: No tags available</div>",
            unsafe_allow_html=True,
        )

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

    pie_labels = [
        "New",
        "Annotation In Progress",
        "Annotation Finished",
        "Curation In Progress",
        "Curation Finished",
    ]

    df_pie_docs = pd.DataFrame(
        {"Labels": pie_labels, "Sizes": data_sizes_docs}
    ).sort_values(by="Labels", ascending=True)
    df_pie_tokens = pd.DataFrame(
        {"Labels": pie_labels, "Sizes": data_sizes_tokens}
    ).sort_values(by="Labels", ascending=True)

    pie_chart = go.Figure()
    pie_chart.add_trace(
        go.Pie(
            labels=df_pie_docs["Labels"],
            values=df_pie_docs["Sizes"],
            sort=False,
            hole=0.4,
            hoverinfo="percent+label",
            textinfo="value",
        )
    )
    pie_chart.add_trace(
        go.Pie(
            labels=df_pie_tokens["Labels"],
            values=df_pie_tokens["Sizes"],
            sort=False,
            hole=0.4,
            hoverinfo="percent+label",
            textinfo="value",
            visible=False,
        )
    )

    pie_chart.update_layout(
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

    bar_chart = go.Figure()

    main_traces = 0
    total_feature_traces = 0
    category_trace_mapping = {}

    for category, details in type_counts.items():
        bar_chart.add_trace(
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

    feature_buttons = []
    max_features_per_type = 30  # limit feature drilldown size to improve performance

    for category, details in type_counts.items():
        features_items = list(details["features"].items())
        if len(features_items) < 2:
            continue

        # Use only the top-N features (already sorted by frequency)
        top_features = features_items[:max_features_per_type]

        category_start = total_feature_traces
        for subcategory, value in top_features:
            # For PHI, value is a dict with per-document counts, for others it's a total
            if isinstance(value, dict):
                total_value = sum(value.values())
            else:
                total_value = value

            bar_chart.add_trace(
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

        category_end = total_feature_traces
        category_trace_mapping[category] = (category_start, category_end)

        visibility = [False] * main_traces + [False] * total_feature_traces
        for i in range(category_start, category_end):
            visibility[main_traces + i] = True

        feature_buttons.append(
            {
                "args": [{"visible": visibility}],
                "label": category,
                "method": "update",
            }
        )

    bar_chart_buttons = [
        {
            "args": [{"visible": [True] * main_traces + [False] * total_feature_traces}],
            "label": "Overview",
            "method": "update",
        }
    ] + feature_buttons

    bar_chart.update_layout(
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
    )

    bar_chart.update_layout(
        updatemenus=[
            {
                "buttons": bar_chart_buttons,
                "direction": "down",
                "showactive": True,
                "x": 0.45,
                "y": 1.15,
                "xanchor": "center",
                "yanchor": "top",
            }
        ]
    )

    col1, _, col3 = st.columns([1, 0.1, 1])
    with col1:
        st.plotly_chart(pie_chart, use_container_width=True)
    with col3:
        st.plotly_chart(bar_chart, use_container_width=True)

    return project_data



def main():

    startup()
    create_directory_in_home()

    st.write(
        "<style> h1 {text-align: center; margin-bottom: 50px, } </style>",
        unsafe_allow_html=True,
    )
    st.title("INCEpTION Reporting Dashboard")
    st.write("<hr>", unsafe_allow_html=True)
    progress_container = st.empty()
    select_method_to_import_data(progress_container=progress_container)

    generated_reports = []
    if "method" in st.session_state and "projects" in st.session_state:
        projects = [copy.deepcopy(project) for project in st.session_state["projects"]]
        projects = sorted(projects, key=lambda project: project.name)
        for project in projects:
            project_data = plot_project_progress(project)
            export_data(project_data)
            generated_reports.append(project_data)
        st.write("<hr>", unsafe_allow_html=True)
        create_zip_download(generated_reports)


if __name__ == "__main__":
    main()
