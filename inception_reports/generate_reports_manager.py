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

import requests
import streamlit as st
from packaging.version import parse as parse_version
from pycaprio import Pycaprio
from inception_reports.dashboard_version import DASHBOARD_VERSION
from inception_reports.manager_charts import render_project_charts
from inception_reports.manager_ui import (
    apply_dashboard_styles,
    create_progress_widgets,
    render_dashboard_title,
    render_missing_curated_documents_warning,
    render_project_header,
    render_version_status,
)
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
    apply_dashboard_styles()

    project_info = get_project_info()
    if project_info:
        current_version = project_info
        package_name = "inception-reports"
        latest_version = check_package_version(current_version, package_name)
        has_update = latest_version and parse_version(current_version) < parse_version(
            latest_version
        )
        render_version_status(current_version, latest_version if has_update else None)


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

                progress_label, progress_bar, progress_callback = create_progress_widgets(
                    progress_container
                )

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
                progress_label, progress_bar, progress_callback = create_progress_widgets(
                    progress_container
                )

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
        render_missing_curated_documents_warning(project.name)
        st.session_state["show_only_curated"] = False

    render_project_header(project_name, project_tags)
    render_project_charts(project_data, type_counts, show_only_curated)

    return project_data



def main():

    startup()
    create_directory_in_home()

    render_dashboard_title()
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
