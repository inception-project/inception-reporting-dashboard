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

import warnings
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import pickle
import argparse
import json


# suppress deprecation warnings related to the use of the pyplot
# can be solved by sending the fig instead of the plt to streamlit
st.set_option("deprecation.showPyplotGlobalUse", False)
warnings.filterwarnings("ignore", message="Boolean Series key will be reindexed to match DataFrame index")


def plot_project_progress(project_files) -> None:
    """
    Generate a visual representation of project progress based on an export of project details provided by the site manager.

    This function takes a dict containing filesname as keys, and file status and estimated time spent on it as keys.
    Then, it generates visualizations to represent the progress of different documents.
    It displays a pie chart showing the percentage of finished and remaining
    documents, along with a bar chart showing the total time spent on finished documents
    compared to the estimated time for remaining documents.

    Parameters:
        project_files (dict): A dictionary of all files in the project, with filename as key and a tuple of status (open, finished) and estimated_time as value

    """
    open_files = [filename for filename, (status, _) in project_files.items() if status == 'open']

    finished_files = {filename: estimated_time for filename, (status, estimated_time) in project_files.items() if status == 'finished'}

    finished_documents_times = list(finished_files.values())
    total_finished_time = int(np.sum(finished_documents_times))
    average_finished_time = int(np.mean(finished_documents_times))
    estimated_remaining_time = len(open_files) * average_finished_time

    data_sizes = [len(finished_files), len(open_files)]
    pie_labels = ["Finished", "Remaining"]
    pie_colors = ["lightgreen", "lightcoral"]

    pie_labels_with_count = [
        f"{label}\n({size} files)" for label, size in zip(pie_labels, data_sizes)
    ]

    plt.figure(figsize=(10, 6))

    plt.subplot(1, 2, 1)
    plt.pie(
        data_sizes,
        labels=pie_labels_with_count,
        colors=pie_colors,
        autopct="%1.1f%%",
        startangle=140,
    )
    plt.axis("equal")
    plt.title("Percentage of Files Finished vs. Remaining")

    plt.subplot(1, 2, 2)
    bar_labels = ["Time"]
    bar_values = [total_finished_time, estimated_remaining_time]
    bar_colors = ["lightgreen", "lightcoral"]
    bar_legend_labels = [
        f"{label} ({size} files)"
        for label, size in zip(["Finished", "Estimated Remaining"], data_sizes)
    ]

    plt.bar(bar_labels, bar_values[0], color=bar_colors[0], label=bar_legend_labels[0])
    plt.bar(
        bar_labels,
        bar_values[1],
        bottom=bar_values[0],
        color=bar_colors[1],
        label=bar_legend_labels[1],
    )
    plt.ylabel("Time (minutes)")
    plt.title("Total Time Spent vs. Estimated Time for Remaining Files")

    # Add text labels showing bar values in hours
    # positioning them centered in the bars
    for i, val in enumerate(bar_values):
        plt.text(
            0,
            val / 2 if i == 0 else bar_values[i - 1] + val / 2,
            f"{(val / 60):.1f} hours",
            color="black",
            ha="center",
            va="center",
            fontsize=12,
        )

    plt.legend()
    plt.tight_layout()
    st.pyplot()


def read_file(filename) -> pickle.OBJ:
    """
    Load the pickle file containing the names of all project file and their respective status.

    Parameters:
        filename (str): The name of the file to read.

    Returns:
        The pickle object containing the project files data.
    """
    if filename.endswith(".json"):
        return json.load(open(filename, "r"))
    # elif filename.endswith(".zip"):
    #     with zipfile.ZipFile(filename, "r") as zip_file:
    #         # change the following line to only select files with the name event.log
    #         project_files = [name for name in zip_file.namelist() if name == "event.log"]
    #         if log_files:
    #             with zip_file.open(log_files[0]) as log_file:
    #                 return pd.read_json(log_file, lines=True)
    else:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Visualize project progress for your INCEpTION project."
    )
    parser.add_argument("filename", help="The name of the file containing project details.")
    args = parser.parse_args()
    filename = args.filename
    st.title(f"INCEpTION {filename} Statistics")

    project_files = read_file(filename)
    if project_files is None:
        st.write("Error: No project files found. Please check your input file.")
        st.stop()
    else:
        plot_project_progress(project_files)

if __name__ == "__main__":
    main()