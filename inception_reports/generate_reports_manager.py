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

import argparse
import hashlib
import json
import os
import shutil
import warnings
import zipfile
from collections import defaultdict

import cassis
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib import gridspec

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

    type_counts = get_type_counts(project_annotations)

    project_data = {
        "project_name": project_name,
        "project_tags": project_tags,
        "doc_categories": doc_categories,
    }

    # st.title(f"Project: {project_name.split('.')[0]}")
    if st.button(f"Export data for {project_name.split('.')[0]}"):
        with open(f"{project_name.split('.')[0]}_data.json", "w") as output_file:
            output_file.write(json.dumps(project_data, indent=4))
        st.success(f"{project_name.split('.')[0]} data exported successfully ✅")

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
    ax1.set_title(f"Documents' Status")

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
    ax2.set_title(f"Types of Annotations")
    ax2.barh(
        list(type_counts.keys()),
        list(type_counts.values()),
        color=colors,
    )
    ax2.set_xscale("log")

    ax2.set_xlabel("Number of Annotations (log scale)")
    fig.suptitle(
        f'{project_name.split(".")[0]}\nTotal Annotations: {total_annotations}',
        fontsize=16,
    )
    fig.tight_layout()
    st.pyplot()


def find_element_by_name(element_list, name):
    for element in element_list:
        if element.name == name:
            return element.uiName
    return name.split(".")[-1]


def get_type_counts(annotations):
    count_dict = defaultdict(int)

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
            if count > 0:
                count_dict[type_name] += count

    aggregated_type_names = list(count_dict.items())
    aggregated_type_names.sort(key=lambda x: x[1], reverse=True)

    return count_dict


def read_dir(dir_path: str) -> list[dict]:
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
                    if name.endswith("INITIAL_CAS.json")
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

                shutil.rmtree(zip_path)

    return projects


def read_dir_old(dir) -> list[dict]:
    """
    Read a file and return a pandas dataframe, regardless of the file type.

    Parameters:
        dir (str): The dir of INCEpTION projects.

    Returns
        List[dict]: A list of dicts containing the project data.
    """
    projects = []

    for file in os.listdir(dir):
        if zipfile.is_zipfile(os.path.join(dir, file)):
            with zipfile.ZipFile(os.path.join(dir, file), "r") as zip_file:
                project_meta = [
                    name
                    for name in zip_file.namelist()
                    if name == "exportedproject.json"
                ][0]
                with zip_file.open(project_meta) as project_meta_file:
                    project_meta = json.load(project_meta_file)
                    project_tags = [
                        w.strip("#")
                        for w in project_meta["description"].split()
                        if w.startswith("#")
                    ]
                    project_documents = project_meta["source_documents"]
                annotations = {}
                # only list the folders that start with "annotation"
                annotation_folders = [
                    name
                    for name in zip_file.namelist()
                    if name.startswith("annotation/")
                    and name.endswith("INITIAL_CAS.json")
                ]
                if annotation_folders:
                    for annotation_file in annotation_folders:
                        subfolder_name = os.path.dirname(annotation_file).split("/")[1]
                        with zip_file.open(annotation_file) as cas_file:
                            cas = cassis.load_cas_from_json(cas_file)
                            annotations[subfolder_name] = cas

                projects.append(
                    {
                        "name": file,
                        "tags": project_tags,
                        "documents": project_documents,
                        # "logs": logs,
                        "annotations": annotations,
                    }
                )
    return projects


def main():
    parser = argparse.ArgumentParser(
        description="Generate plots for your INCEpTION project."
    )
    parser.add_argument("projects_folder", help="The folder of INCEpTION projects.")
    args = parser.parse_args()

    st.title(f"INCEpTION Berlin Projects Statistics")

    projects = read_dir(args.projects_folder)
    projects.sort(key=lambda x: x["name"])
    for project in projects:
        plot_project_progress(project)


if __name__ == "__main__":
    main()
