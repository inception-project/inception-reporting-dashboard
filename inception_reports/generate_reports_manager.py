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

import hashlib
import json
import warnings
import zipfile
from matplotlib import gridspec
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import math
import argparse
import os
import cassis
from collections import defaultdict



# suppress deprecation warnings related to the use of the pyplot
# can be solved by sending the fig instead of the plt to streamlit
st.set_option("deprecation.showPyplotGlobalUse", False)
st.set_page_config(page_title="INCEpTION Reporting Dashboard", layout="centered")
css='''
<style>
    section.main > div {max-width:50%}
</style>
'''
st.markdown(css, unsafe_allow_html=True)
warnings.filterwarnings(
    "ignore", message="Boolean Series key will be reindexed to match DataFrame index"
)


def anonymize_users(df) -> pd.DataFrame:
    """
    Anonymizes user data in a DataFrame by mapping user names to NATO alphabet codes.

    This function takes a DataFrame containing a column named "user" and replaces
    the user names with corresponding NATO alphabet codes, excluding the "<SYSTEM>"
    user. The mapping is done in alphabetical order.

    Parameters:
        df (pandas.DataFrame): The DataFrame containing the user data.

    Returns:
        pandas.DataFrame: The DataFrame with the "user" column anonymized using NATO
        alphabet codes.
    """
    users = np.sort(df["user"].unique())
    users = users[users != "<SYSTEM>"]
    nato_alphabet = [
        "Alpha",
        "Bravo",
        "Charlie",
        "Delta",
        "Echo",
        "Foxtrot",
        "Golf",
        "Hotel",
        "India",
        "Juliett",
        "Kilo",
        "Lima",
        "Mike",
        "November",
        "Oscar",
        "Papa",
        "Quebec",
        "Romeo",
        "Sierra",
        "Tango",
        "Uniform",
        "Victor",
        "Whiskey",
        "X-Ray",
        "Yankee",
        "Zulu",
    ]

    user_mapping = dict(zip(users, nato_alphabet[: len(users)]))
    user_mapping["<SYSTEM>"] = "<SYSTEM>"

    df["user"] = df["user"].map(user_mapping)
    return df


def anonymize_filenames(project_files: dict) -> dict:
    """
    Anonymizes filenames in a dictionary of project files by mapping filenames to a SHA256 hash.

    Parameters:
        project_files (dict): The dictionary of project files.

    Returns:
        dict: The dictionary of project files with the filenames anonymized using SHA256 hashes.
    """
    anonymized_project_files = {}
    for file_name, file_info in project_files.items():
        if str(file_name) == "nan":
            continue
        sha256_hash = hashlib.sha256()
        sha256_hash.update(str(file_name).encode("utf-8"))
        anon_name = sha256_hash.hexdigest()
        anonymized_project_files[anon_name] = file_info

    return anonymized_project_files

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
        "#fc1c03",
        "#fcbe03",
        "#03fc17",
        "#0373fc",
        "#4e03fc",
    ]
    pie_percentages = 100.0 * np.array(data_sizes) / np.array(data_sizes).sum()
    plt.figure(figsize=(15, 9))
    gs = gridspec.GridSpec(1, 3, width_ratios=[1, 0.01, 1])

    ax1 = plt.subplot(gs[0])

    wedges, texts = plt.pie(
        data_sizes,
        colors=pie_colors,
        startangle=140
    )

    plt.axis("equal")
    total_annotations = sum(
        [len(cas_file.select_all()) for cas_file in project_annotations.values()]
    )
    plt.title(f"Documents' Status")

    # Create a legend with labels and percentages
    legend_labels = [
        f"{label} ({percent:.2f}% / {size} files)"
        for label, size, percent in zip(pie_labels, data_sizes, pie_percentages)
    ]
    plt.legend(
        wedges,
        legend_labels,
        title="Categories",
        loc="center left",
        bbox_to_anchor=(1, 0.5),
    )

    ax2 = plt.subplot(gs[2])

    plt.title(f"Types of Annotations")
    plt.barh(
        list(type_counts.keys()),
        list(type_counts.values()),
    )

    plt.suptitle(f'{project_name.split(".")[0]}\nTotal Annotations: {total_annotations}', fontsize=16)
    plt.tight_layout()
    st.pyplot()


def get_type_counts(annotations):
    type_names = []
    for doc in annotations:
        for t in annotations[doc].typesystem.get_types():
            count = len(annotations[doc].select(t.name))
            name = t.name.split(".")[-1]
            if not name == "Token":
                type_names.append((name, count))

    count_dict = defaultdict(int)
    for type_name, count in type_names:
        count_dict[type_name] += count

    aggregated_type_names = list(count_dict.items())
    aggregated_type_names.sort(key=lambda x: x[1], reverse=True)

    return count_dict


def read_dir(dir) -> list[dict]:
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
                # change the following line to only select files with the name event.log
                # log_files = [name for name in zip_file.namelist() if name == "event.log"][0]
                # if log_files:
                # with zip_file.open(log_files) as log_file:
                #     logs = pd.read_json(log_file, lines=True)
                #     logs = anonymize_users(logs)
                #     logs["created_readable"] = pd.to_datetime(
                #         logs["created"], unit="ms"
                #     )
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
    # parser = argparse.ArgumentParser(
    # description="Generate plots for logs of your INCEpTION project."
    # )
    # parser.add_argument("filename", help="The name of the file to process")
    # args = parser.parse_args()
    # filename = args.filename
    
    st.title(f"INCEpTION Berlin Projects Statistics")

    projects = read_dir("/berlin_projects")
    projects.sort(key=lambda x: x["name"])
    for project in projects:
        plot_project_progress(project)


if __name__ == "__main__":
    main()
