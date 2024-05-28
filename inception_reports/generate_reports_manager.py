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
import json
import os
import shutil
import time
import zipfile
from datetime import datetime

import cassis
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pycaprio import Pycaprio
import importlib.resources

st.set_page_config(
    page_title="INCEpTION Reporting Dashboard",
    layout="centered",
    initial_sidebar_state=st.session_state.setdefault("sidebar_state", "expanded"),
)

if st.session_state.get("flag"):
    st.session_state.sidebar_state = st.session_state.flag
    del st.session_state.flag
    time.sleep(0.01)
    st.rerun()


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
        section.main > div {max-width:90%}
        </style>
        """,
        unsafe_allow_html=True,
    )


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
    """
    Reads a directory containing zip files, extracts the contents, and retrieves project metadata and annotations.

    Parameters:
        dir_path (str): The path to the directory containing the zip files.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a project and contains the following keys:
            - "name": The name of the zip file.
            - "tags": A list of tags extracted from the project metadata.
            - "documents": A list of source documents from the project metadata.
            - "annotations": A dictionary mapping annotation subfolder names to their corresponding CAS objects.
    """
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
                        project_tags = [
                            translate_tag(word.strip("#"))
                            for word in project_meta["description"].split()
                            if word.startswith("#")
                        ]
                        project_documents = project_meta["source_documents"]

                annotations = {}
                # Find annotation folders
                annotation_folders = [
                    name
                    for name in zip_file.namelist()
                    if name.startswith("annotation/")
                    and name.endswith(".json")
                    and not name.endswith("INITIAL_CAS.json")
                ]
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
        st.sidebar.success("Login successful ✅")
        button = False
        return True, inception_client
    return False, None


def select_method_to_import_data():
    """
    Allows the user to select a method to import data for generating reports.
    """

    method = st.sidebar.radio(
        "Choose your method to import data:", ("Manually", "API"), index=1
    )

    if method == "Manually":
        st.sidebar.write(
            "Please input the path to the folder containing the INCEpTION projects."
        )
        projects_folder = st.sidebar.text_input("Projects Folder:", value="")
        button = st.sidebar.button("Generate Reports")
        if button:
            st.session_state["method"] = "Manually"
            st.session_state["projects"] = read_dir(projects_folder)
            button = False
            set_sidebar_state("collapsed")
    elif method == "API":
        projects_folder = f"{os.path.expanduser('~')}/.inception_reports/projects"
        os.makedirs(os.path.dirname(projects_folder), exist_ok=True)
        api_url = st.sidebar.text_input("Enter API URL:", "")
        username = st.sidebar.text_input("Username:", "")
        password = st.sidebar.text_input("Password:", type="password", value="")
        inception_status = st.session_state.get("inception_status", False)
        inception_client = st.session_state.get("inception_client", None)
        if not inception_status:
            inception_status, inception_client = login_to_inception(api_url, username, password)
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
                selected_projects[project_id] = st.sidebar.checkbox(project_name, value=False)
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
                        project_export = inception_client.api.export_project(project, "jsoncas")
                        with open(file_path, "wb") as f:
                            f.write(project_export)
                
                st.session_state["method"] = "API"
                st.session_state["projects"] = read_dir(projects_folder, selected_projects_names)
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
        dict: A dictionary containing the count of each type.
    """
    count_dict = {}
    layerDefinition = next(iter(annotations.values())).select(
        "de.tudarmstadt.ukp.clarin.webanno.api.type.LayerDefinition"
    )
    for doc in annotations:
        type_names = [
            (
                find_element_by_name(layerDefinition, t.name),
                len(annotations[doc].select(t.name)),
            )
            for t in annotations[doc].typesystem.get_types()
            if t.name != "de.tudarmstadt.ukp.clarin.webanno.api.type.LayerDefinition"
        ]

        for type_name, count in type_names:
            if type_name not in count_dict:
                count_dict[type_name] = 0
            count_dict[type_name] += count
    count_dict = {k: v for k, v in count_dict.items() if v > 0}
    count_dict = dict(sorted(count_dict.items(), key=lambda item: item[1]))

    return count_dict


def export_data(project_data, output_directory=None):
    """
    Export project data to a JSON file, and store it in a directory named after the project and the current date.

    Parameters:
        project_data (dict): The data to be exported.
    """
    current_date = datetime.now().strftime("%Y_%m_%d")
    directory_name = f"exported_data_{current_date}"

    if output_directory is None:
        output_directory = os.path.join(os.getcwd(), directory_name)
    else:
        output_directory = os.path.join(output_directory, directory_name)

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    project_name = project_data["project_name"]
    with open(
        f"{output_directory}/{project_name.split('.')[0]}_data_{current_date}.json", "w"
    ) as output_file:
        json.dump(project_data, output_file, indent=4)
    st.success(
        f"{project_name.split('.')[0]} documents status exported successfully ✅"
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

    project_data = {
        "project_name": project_name,
        "project_tags": project_tags,
        "doc_categories": doc_categories,
    }

    type_counts = get_type_counts(project_annotations)

    data_sizes = [
        project_data["doc_categories"]["NEW"],
        project_data["doc_categories"]["ANNOTATION_IN_PROGRESS"],
        project_data["doc_categories"]["ANNOTATION_FINISHED"],
        project_data["doc_categories"]["CURATION_IN_PROGRESS"],
        project_data["doc_categories"]["CURATION_FINISHED"],
    ]

    pie_labels = [
        "New",
        "Annotation In Progress",
        "Annotation Finished",
        "Curation In Progress",
        "Curation Finished",
    ]

    df_pie = pd.DataFrame({"Labels": pie_labels, "Sizes": data_sizes}).sort_values(
        by="Labels", ascending=True
    )

    df_bar = pd.DataFrame(
        {
            "Types": [type for type, _ in type_counts.items()],
            "Counts": list(type_counts.values()),
        }
    )

    pie_chart = go.Figure(
        go.Pie(
            labels=df_pie["Labels"],
            values=df_pie["Sizes"],
            sort=False,
            hole=0.4,
            hoverinfo="label+value",
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
    )

    bar_chart = go.Figure()

    for _, row in df_bar.iterrows():
        bar_chart.add_trace(
            go.Bar(
                y=[row["Types"]],
                x=[row["Counts"]],
                orientation="h",
                name=row["Types"],
                legendgroup=row["Types"],
                showlegend=True,
                hoverinfo="x+y",
            )
        )

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
        height= 60 * len(df_bar),
        font=dict(size=18),
        legend=dict(font=dict(size=12)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40),
        colorway=px.colors.qualitative.Plotly,
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
