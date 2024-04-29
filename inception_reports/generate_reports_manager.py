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

import json
import os
import shutil
import warnings
import zipfile

import cassis
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from matplotlib import gridspec
from pycaprio import Pycaprio

# suppress deprecation warnings related to the use of the pyplot
# can be solved by sending the fig instead of the plt to streamlit
st.set_option("deprecation.showPyplotGlobalUse", False)
st.set_page_config(page_title="INCEpTION Reporting Dashboard", layout="centered")
css = """
<style>
    section.main > div {max-width:50%}
</style>
"""
st.markdown(css, unsafe_allow_html=True)
warnings.filterwarnings(
    "ignore", message="Boolean Series key will be reindexed to match DataFrame index"
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
    project_name = project["name"]
    project_tags = project["tags"]
    project_annotations = project["annotations"]
    project_documents = project["documents"]

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
    selected_annotation_types = st.multiselect(
        f"Which annotation types would you like to see for {project_name}?",
        list(type_counts.keys()),
        list(type_counts.keys())
    )
    type_counts = {k: v for k, v in type_counts.items() if k in selected_annotation_types}

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
    pie_colors = [
        "tab:red",
        "cornflowerblue",
        "royalblue",
        "limegreen",
        "forestgreen",
    ]
    pie_percentages = 100.0 * np.array(data_sizes) / np.array(data_sizes).sum()
    fig = plt.figure(figsize=(15, 9))
    gs = gridspec.GridSpec(1, 3, width_ratios=[1, 0.01, 1])

    ax1 = plt.subplot(gs[0])

    wedges, _ = ax1.pie(
        data_sizes, colors=pie_colors, startangle=90, radius=2, counterclock=False
    )

    ax1.axis("equal")
    total_annotations = sum(
        [len(cas_file.select_all()) for cas_file in project_annotations.values()]
    )
    ax1.set_title("Documents Status")

    legend_labels = [
        f"{label} ({percent:.2f}% / {size} files)"
        for label, size, percent in zip(pie_labels, data_sizes, pie_percentages)
    ]
    ax1.legend(
        wedges,
        legend_labels,
        title="Categories",
        loc="center left",
        bbox_to_anchor=(1, 0.5),
    )

    ax2 = plt.subplot(gs[2])
    colors = plt.cm.tab10(range(len(type_counts.keys())))
    ax2.set_title("Types of Annotations")
    ax2.barh(
        [f"{type} = {value}" for type, value in type_counts.items()],
        list(type_counts.values()),
        color=colors,
    )
    ax2.set_xlabel("Number of Annotations")
    
    fig.suptitle(
        f'{project_name.split(".")[0]}\nTotal Annotations: {total_annotations}',
        fontsize=16,
    )
    fig.tight_layout()
    st.pyplot()

    # st.title(f"Project: {project_name.split('.')[0]}")
    if st.button(f"Export data for {project_name.split('.')[0]}"):
        with open(f"{project_name.split('.')[0]}_data.json", "w") as output_file:
            output_file.write(json.dumps(project_data, indent=4))
        st.success(f"{project_name.split('.')[0]} data exported successfully ✅")


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

    layerDefinition = annotations.popitem()[1].select(
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


def read_dir(dir_path: str) -> list[dict]:
    """
    Reads a directory containing zip files, extracts the contents, and retrieves project metadata and annotations.

    Args:
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
                            word.strip("#")
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
                        "tags": project_tags,
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
    if st.sidebar.button("Login"):
        inception_client = Pycaprio(api_url, (username, password))
        st.sidebar.success("Login successful ✅")
        return True, inception_client
    return False, None



def select_method_to_import_data():
    """
    Allows the user to select a method to import data for generating reports.
    """
    
    method = st.sidebar.radio("Choose your method to import data:", ('Manually', 'API'), index=0)

    if method == 'Manually':
        st.sidebar.write("Please input the path to the folder containing the INCEpTION projects.")
        projects_folder = st.sidebar.text_input("Projects Folder:", value="data/dresden_projects/")
        if st.sidebar.button("Generate Reports"):
            st.session_state['initialized'] = True
            st.session_state['method'] = 'Manually'
            st.session_state['projects_folder'] = projects_folder
    elif method == 'API':
        api_url = st.sidebar.text_input("Enter API URL:", "")
        username = st.sidebar.text_input("Username:", "")
        password = st.sidebar.text_input("Password:", type="password", value="")
        inception_status, inception_client = login_to_inception(api_url, username, password)
        if inception_status:
            inception_projects = inception_client.api.projects()
            st.sidebar.write("Following projects got imported:")
            for inception_project in inception_projects:
                st.sidebar.write(inception_project.project_name)
                project_export = inception_client.api.export_project(inception_project, "jsoncas")
                with open(f"{os.path.expanduser('~')}/.inception_reports/projects/{inception_project}.zip", "wb") as f:
                    f.write(project_export)
            st.session_state['initialized'] = True
            st.session_state['method'] = 'API'
            st.session_state['projects_folder'] = f"{os.path.expanduser('~')}/.inception_reports/projects"



def create_directory_in_home():
    """
    Creates a directory in the user's home directory for storing Inception reports.
    """
    home_dir = os.path.expanduser("~")
    new_dir_path = os.path.join(home_dir, ".inception_reports")
    try:
        os.makedirs(new_dir_path)
        os.makedirs(os.path.join(new_dir_path, "projects"))
    except FileExistsError:
        pass


def main():
    create_directory_in_home()
    
    st.title("INCEpTION Projects Statistics")

    if 'initialized' not in st.session_state:
        select_method_to_import_data()

    if 'method' in st.session_state:
        projects = read_dir(st.session_state.projects_folder)
        projects.sort(key=lambda x: x["name"])
        for project in projects:
            plot_project_progress(project)


if __name__ == "__main__":
    main()
