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


def plot_project_progress(project_progress_data) -> None:
    """
    Generate a visual representation of project progress based on an export of project details provided by the site manager.

    This function takes a dict containing project progress data and generates a pie chart showing the percentage of files finished vs. remaining.


    Parameters:
        project_progress_data (dict): A dictionary containing project progress data.

    """
    
    data_sizes = [project_progress_data["number_of_finished_documents"],
                  project_progress_data["number_of_remaining_documents"]]
    
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
    bar_values = [project_progress_data["total_finished_time"],
                  project_progress_data["estimated_remaining_time"]]
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
    else:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Visualize project progress for your INCEpTION project."
    )
    parser.add_argument("filename", help="The name of the file containing project details.")
    args = parser.parse_args()
    filename = args.filename
    st.title(f"INCEpTION Statistics")

    project_files = read_file(filename)
    if project_files is None:
        st.write("Error: No project files found. Please check your input file.")
        st.stop()
    else:
        plot_project_progress(project_files)

if __name__ == "__main__":
    main()