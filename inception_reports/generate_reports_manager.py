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

from collections import defaultdict
import copy
import importlib.resources
import json
import os
import shutil
import time
import zipfile
from datetime import datetime
import logging

import cassis
import pandas as pd
import pkg_resources
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import toml
from pycaprio import Pycaprio

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
        current_version, package_name = project_info
        latest_version = check_package_version(current_version, package_name)
        if latest_version:
            st.sidebar.warning(
                f"A new version ({latest_version}) of {package_name} is available. "
                f"You are currently using version ({current_version}). Please update the package."
            )



def get_project_info():
    try:
        pyproject_path = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")
        with open(pyproject_path, "r") as f:
            pyproject_data = toml.load(f)
        version = pyproject_data["project"].get("version")
        name = pyproject_data["project"].get("name")
        if version and name:
            return version, name
        return None
    except (FileNotFoundError, KeyError):
        return None


def check_package_version(current_version, package_name):
    try:
        response = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=5)
        if response.status_code == 200:
            latest_version = response.json()["info"]["version"]
            if pkg_resources.parse_version(
                current_version
            ) < pkg_resources.parse_version(latest_version):
                return latest_version
    except requests.RequestException:
        return None
    return None


def create_directory_in_home():
    """
    Creates a directory in the user's home directory for storing Inception reports imported over the API.
    """
    home_dir = os.path.expanduser("~")
    new_dir_path = os.path.join(home_dir, ".inception_reports")
    try:
        os.makedirs(new_dir_path)
        os.makedirs(os.path.join(new_dir_path, "projects"))
    except FileExistsError:
        pass


def set_sidebar_state(value):
    if st.session_state.sidebar_state == value:
        st.session_state.flag = value
        st.session_state.sidebar_state = (
            "expanded" if value == "collapsed" else "collapsed"
        )
    else:
        st.session_state.sidebar_state = value
    st.rerun()


def translate_tag(tag, translation_path=None):
    """
    Translate the given tag to a human-readable format.
    """

    if translation_path:
        with open(translation_path, "r") as f:
            translation = json.load(f)
        if tag in translation:
            return translation[tag]
        else:
            return tag
    else:
        data_path = importlib.resources.files("inception_reports.data")
        with open(data_path.joinpath("specialties.json"), "r") as f:
            specialties = json.load(f)
        with open(data_path.joinpath("document_types.json"), "r") as f:
            document_types = json.load(f)

        if tag in specialties:
            return specialties[tag]
        elif tag in document_types:
            return document_types[tag]
        else:
            return tag


def read_dir(dir_path: str, selected_projects: list = None) -> list[dict]:
    projects = []

    for file_name in os.listdir(dir_path):
        if selected_projects and file_name.split(".")[0] not in selected_projects:
            continue
        file_path = os.path.join(dir_path, file_name)
        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path, "r") as zip_file:
                zip_path = f"{dir_path}/{file_name.split('.')[0]}"
                zip_file.extractall(path=zip_path)

                # Find project metadata file
                project_meta_path = os.path.join(zip_path, "exportedproject.json")
                if os.path.exists(project_meta_path):
                    with open(project_meta_path, "r") as project_meta_file:
                        project_meta = json.load(project_meta_file)
                        description = project_meta.get("description", "")
                        project_tags = (
                            [
                                translate_tag(word.strip("#"))
                                for word in description.split()
                                if word.startswith("#")
                            ]
                            if description
                            else []
                        )

                        project_documents = project_meta.get("source_documents")
                        if not project_documents:
                            raise ValueError(
                                "No source documents found in the project."
                            )

                annotations = {}
                folder_files = defaultdict(list)
                for name in zip_file.namelist():
                    if name.startswith("annotation/") and name.endswith(".json"):
                        folder = '/'.join(name.split('/')[:-1])
                        folder_files[folder].append(name)

                annotation_folders = []
                for folder, files in folder_files.items():
                    if len(files) == 1 and files[0].endswith("INITIAL_CAS.json"):
                        annotation_folders.append(files[0])
                    else:
                        annotation_folders.extend(
                            file for file in files if not file.endswith("INITIAL_CAS.json")
                        )
                for annotation_file in annotation_folders:
                    subfolder_name = os.path.dirname(annotation_file).split("/")[1]
                    with zip_file.open(annotation_file) as cas_file:
                        cas = cassis.load_cas_from_json(cas_file)
                        annotations[subfolder_name] = cas

                projects.append(
                    {
                        "name": file_name,
                        "tags": project_tags if project_tags else None,
                        "documents": project_documents,
                        "annotations": annotations,
                    }
                )

                # Clean up extracted files
                shutil.rmtree(zip_path)

    return projects


def login_to_inception(api_url, username, password):
    """
    Logs in to the Inception API using the provided API URL, username, and password.

    Args:
        api_url (str): The URL of the Inception API.
        username (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        tuple: A tuple containing a boolean value indicating whether the login was successful and an instance of the Inception client.

    """
    if "http" not in api_url:
        api_url = f"http://{api_url}"
    button = st.sidebar.button("Login")
    if button:
        inception_client = Pycaprio(api_url, (username, password))
        try:
            inception_client.api.projects()  # Check if login is successful
            st.sidebar.success("Login successful ✅")
            return True, inception_client
        except Exception:
            st.sidebar.error("Login unsuccessful ❌")
            return False, None
    return False, None


def select_method_to_import_data():
    """
    Allows the user to select a method to import data for generating reports.
    """

    method = st.sidebar.radio(
        "Choose your method to import data:", ("Manually", "API"), index=0
    )    
    if method == "Manually":
        st.sidebar.write(
            "Please input the path to the folder containing the INCEpTION projects."
        )
        projects_folder = st.sidebar.text_input(
            "Projects Folder:", value=""
        )
        uploaded_files = st.sidebar.file_uploader(
            "Or upload project files:", accept_multiple_files=True, type="zip"
        )

        button = st.sidebar.button("Generate Reports")
        if button:
            if uploaded_files:
                # Handle uploaded files
                temp_dir = os.path.join(
                    os.path.expanduser("~"), ".inception_reports", "temp_uploads"
                )

                os.makedirs(temp_dir, exist_ok=True)

                for uploaded_file in uploaded_files:
                    file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.read())

                selected_projects_names = [uploaded_file.name.split(".")[0] for uploaded_file in uploaded_files]

                st.session_state["projects"] = read_dir(temp_dir, selected_projects_names)
                st.session_state["projects_folder"] = temp_dir
                # shutil.rmtree(temp_dir)
            elif projects_folder:
                st.session_state["projects_folder"] = projects_folder
                st.session_state["projects"] = read_dir(projects_folder)

            st.session_state["method"] = "Manually"
            button = False            
            set_sidebar_state("collapsed")

    elif method == "API":
        projects_folder = f"{os.path.expanduser('~')}/.inception_reports/projects"
        os.makedirs(os.path.dirname(projects_folder), exist_ok=True)
        st.session_state["projects_folder"] = projects_folder
        api_url = st.sidebar.text_input("Enter API URL:", "")
        username = st.sidebar.text_input("Username:", "")
        password = st.sidebar.text_input("Password:", type="password", value="")
        inception_status = st.session_state.get("inception_status", False)
        inception_client = st.session_state.get("inception_client", None)
        if not inception_status:
            inception_status, inception_client = login_to_inception(
                api_url, username, password
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

            selected_projects_names = []
            button = st.sidebar.button("Generate Reports")
            if button:
                for project_id, is_selected in selected_projects.items():
                    if is_selected:
                        project = inception_client.api.project(project_id)
                        selected_projects_names.append(project.project_name)
                        file_path = f"{projects_folder}/{project.project_name}.zip"
                        st.sidebar.write(f"Importing project: {project.project_name}")
                        log.info(f"Importing project {project.project_name} into {file_path} ")
                        project_export = inception_client.api.export_project(
                            project, "jsoncas"
                        )
                        with open(file_path, "wb") as f:
                            f.write(project_export)
                        log.debug("Import Success")

                st.session_state["method"] = "API"
                st.session_state["projects"] = read_dir(
                    projects_folder, selected_projects_names
                )
                set_sidebar_state("collapsed")


def find_element_by_name(element_list, name):
    """
    Finds an element in the given element list by its name.

    Args:
        element_list (list): A list of elements to search through.
        name (str): The name of the element to find.

    Returns:
        str: The UI name of the found element, or the last part of the name if not found.
    """
    for element in element_list:
        if element.name == name:
            return element.uiName
    return name.split(".")[-1]

def get_type_counts(annotations):
    """
    Calculate the count of each type in the given annotations. Each annotation is a CAS object.

    Args:
        annotations (dict): A dictionary containing the annotations.

    Returns:
        dict: A dictionary containing the count of each type, both total and per document.
              The structure is {type_name: {'total': count, 'documents': {doc_id: count}}}.
    """

    type_count = {}

    # Assuming that all documents have the same layer definition
    first_doc = next(iter(annotations.values()))
    layer_definitions = first_doc.select(
        "de.tudarmstadt.ukp.clarin.webanno.api.type.LayerDefinition"
    )

    # Define a set of types to exclude for clarity and performance
    excluded_types = {
        "uima.tcas.DocumentAnnotation",
        "webanno.custom.Metadata",
        "de.tudarmstadt.ukp.clarin.webanno.api.type.LayerDefinition",
        "de.tudarmstadt.ukp.clarin.webanno.api.type.FeatureDefinition",
        "de.tudarmstadt.ukp.dkpro.core.api.lexmorph.type.morph.MorphologicalFeatures",
        "de.tudarmstadt.ukp.dkpro.core.api.metadata.type.DocumentMetaData",
        "de.tudarmstadt.ukp.dkpro.core.api.metadata.type.TagDescription",
        "de.tudarmstadt.ukp.dkpro.core.api.metadata.type.TagsetDescription",
        None,
    }

    for doc_id, cas in annotations.items():
        log.debug(f"Processing {doc_id}")
        # Get the list of relevant types for the current CAS object
        relevant_types = [
            t for t in cas.typesystem.get_types()
            if t.name not in excluded_types
        ]

        for t in relevant_types:
            cas_select = cas.select(t.name)
            count = len(cas_select)
            if count == 0:
                continue

            # Filter for the features that are relevant
            annotations_features = [
                feature for feature in t.all_features
                if feature.name not in {
                    cassis.typesystem.FEATURE_BASE_NAME_END,
                    cassis.typesystem.FEATURE_BASE_NAME_BEGIN,
                    cassis.typesystem.FEATURE_BASE_NAME_SOFA,
                }
            ]

            # Get UI Name for layer type
            type_name = find_element_by_name(layer_definitions, t.name)

            if type_name not in type_count:
                type_count[type_name] = {
                    "total": 0,
                    "documents": {},
                    "features": {}
                }

            type_count[type_name]["total"] += count
            type_count[type_name]["documents"].setdefault(doc_id, 0)
            type_count[type_name]["documents"][doc_id] += count

            # Count the feature occurrences within the selected CAS
            for feature in annotations_features:
                for cas_item in cas_select:
                    feature_value = cas_item.get(feature.name)
                    if feature_value is None:
                        continue
                    if feature_value not in type_count[type_name]["features"]:
                        type_count[type_name]["features"][feature_value] = {}

                    type_count[type_name]["features"][feature_value].setdefault(doc_id, 0)
                    type_count[type_name]["features"][feature_value][doc_id] += 1


    for type_name, type_data in type_count.items():
        type_data["features"] = dict(sorted(type_data["features"].items(), key=lambda x: sum(x[1].values()), reverse=True))
    type_count = dict(sorted(type_count.items(), key=lambda item: item[1]["total"], reverse=True))
    log.debug(f"Type count object : {type_count}")
    return type_count


def export_data(project_data):
    """
    Export project data to a JSON file, and store it in a directory named after the project and the current date.

    Parameters:
        project_data (dict): The data to be exported.
    """
    current_date = datetime.now().strftime("%Y_%m_%d")

    output_directory = os.getenv("INCEPTION_OUTPUT_DIR")

    if output_directory is None:
        output_directory = os.path.join(os.getcwd(), "exported_project_data")
    
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    project_name = project_data["project_name"]

    project_data["created"] = datetime.now().date().isoformat()

    with open(
        f"{output_directory}/{project_name.split('.')[0]}_{current_date}.json", "w"
    ) as output_file:
        json.dump(project_data, output_file, indent=4)
    st.success(
        f"{project_name.split('.')[0]} documents status exported successfully to {output_directory} ✅"
    )


def plot_project_progress(project) -> None:
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

    # df = project["logs"]
    project_name = project["name"].strip(".zip")
    project_tags = project["tags"]
    project_annotations = project["annotations"]
    project_documents = project["documents"]
    type_counts = get_type_counts(project_annotations)

    if project_tags:
        st.write(
            f"<div style='text-align: center; font-size: 18px;'><b>Project Name</b>: {project_name} <br> <b>Tags</b>: {', '.join(project['tags'])}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.write(
            f"<div style='text-align: center; font-size: 18px;'><b>Project Name</b>: {project_name} <br> <b>Tags</b>: No tags available</div>",
            unsafe_allow_html=True,
        )

    doc_categories = {
        "ANNOTATION_IN_PROGRESS": 0,
        "ANNOTATION_FINISHED": 0,
        "CURATION_IN_PROGRESS": 0,
        "CURATION_FINISHED": 0,
        "NEW": 0,
    }

    for doc in project_documents:
        state = doc["state"]
        if state in doc_categories:
            doc_categories[state] += 1

    doc_token_categories = {
        "ANNOTATION_IN_PROGRESS": 0,
        "ANNOTATION_FINISHED": 0,
        "CURATION_IN_PROGRESS": 0,
        "CURATION_FINISHED": 0,
        "NEW": 0,
    }

    for doc in project_documents:
        log.debug(f"Start processing tokens for document {doc}")
        state = doc["state"]
        if state in doc_token_categories:
            doc_token_categories[state] += type_counts["Token"]["documents"][
                doc["name"]
            ]

    project_data = {
        "project_name": project_name,
        "project_tags": project_tags,
        "doc_categories": doc_categories,
        "doc_token_categories": doc_token_categories,
    }

    data_sizes_docs = [
        project_data["doc_categories"]["NEW"],
        project_data["doc_categories"]["ANNOTATION_IN_PROGRESS"],
        project_data["doc_categories"]["ANNOTATION_FINISHED"],
        project_data["doc_categories"]["CURATION_IN_PROGRESS"],
        project_data["doc_categories"]["CURATION_FINISHED"],
    ]

    data_sizes_tokens = [
        project_data["doc_token_categories"]["NEW"],
        project_data["doc_token_categories"]["ANNOTATION_IN_PROGRESS"],
        project_data["doc_token_categories"]["ANNOTATION_FINISHED"],
        project_data["doc_token_categories"]["CURATION_IN_PROGRESS"],
        project_data["doc_token_categories"]["CURATION_FINISHED"],
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
    feature_traces = 0

    # Add bar traces for the total counts by category
    for category, details in type_counts.items():
        bar_chart.add_trace(go.Bar(
            y=[category],
            x=[details["total"]],
            text=[details["total"]],
            textposition='auto',
            name=category.capitalize(),
            visible=True,
            orientation="h",
            hoverinfo="x+y"
        ))
        main_traces += 1

    feature_buttons = []
    for category, details in type_counts.items():
        if len(details['features']) >= 2:
            for subcategory, subvalues in details['features'].items():
                bar_chart.add_trace(go.Bar(
                    y=[subcategory],
                    x=[sum(subvalues.values())],
                    text=[sum(subvalues.values())],
                    textposition='auto',
                    name=subcategory,
                    visible=False,
                    orientation="h",
                    hoverinfo="x+y"
                ))
                feature_traces += 1
            
            visibility = [False] * main_traces + [True] * feature_traces
            
            feature_buttons.append(
                {
                    "args": [
                        {"visible": visibility}
                    ],
                    "label": category,
                    "method": "update"
                }
            )

    bar_chart_buttons = [
        {
            "args": [
                {"visible": [True] * main_traces + [False] * feature_traces}
            ],
            "label": "Overview",
            "method": "update"
        }
    ] + feature_buttons

    bar_chart.update_layout(
        title=dict(
            text="Types of Annotations",
            font=dict(size=24),
            y=0.95,
            x=0.45,
            xanchor="center",
        ),
        xaxis_title="Number of Annotations",
        barmode="overlay",
        height= min(160 * len(type_counts), 500),
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

    export_data(project_data)


def main():

    startup()
    create_directory_in_home()

    st.write(
        "<style> h1 {text-align: center; margin-bottom: 50px, } </style>",
        unsafe_allow_html=True,
    )
    st.title("INCEpTION Reporting Dashboard")
    st.write("<hr>", unsafe_allow_html=True)
    select_method_to_import_data()

    if "method" in st.session_state and "projects" in st.session_state:
        projects = [copy.deepcopy(project) for project in st.session_state["projects"]]
        projects = sorted(projects, key=lambda x: x["name"])
        for project in projects:
            plot_project_progress(project)


if __name__ == "__main__":
    main()
