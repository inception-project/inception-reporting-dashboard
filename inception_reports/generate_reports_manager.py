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
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import math
import argparse


# suppress deprecation warnings related to the use of the pyplot
# can be solved by sending the fig instead of the plt to streamlit
st.set_option("deprecation.showPyplotGlobalUse", False)
warnings.filterwarnings(
    "ignore", message="Boolean Series key will be reindexed to match DataFrame index"
)


# List of events representing annotations.
interesting_events = [
    "DocumentOpenedEvent",
    "ChainLinkCreatedEvent",
    "ChainLinkDeletedEvent",
    "ChainSpanCreatedEvent",
    "ChainSpanDeletedEvent",
    "DocumentMetadataCreatedEvent",
    "DocumentMetadataDeletedEvent",
    "FeatureValueUpdatedEvent",
    "RelationCreatedEvent",
    "RelationDeletedEvent",
    "SpanCreatedEvent",
    "SpanDeletedEvent",
    "SpanMovedEvent",
    "AnnotationStateChangeEvent",
]

# List of events representing deleting a previously created annotation.
deleted_events = [
    "ChainLinkDeletedEvent",
    "ChainSpanDeletedEvent",
    "DocumentMetadataDeletedEvent",
    "RelationDeletedEvent",
    "SpanDeletedEvent",
]


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


def plot_averages(df) -> None:
    """
    Generates and displays a series of plots to visualize various statistics based on a DataFrame of log data.

    This function takes a DataFrame containing and generates plots to visualize three aspects:
    1. Cumulative duration of user sessions: Plots the cumulative duration of user sessions for each user.
    2. Average session duration per user: Plots the average session duration for each user.
    3. Average time per annotation per user: Plots the average time spent on each annotation for each user.

    Parameters:
        df (pd.DataFrame): The input DataFrame containing log data.
    """

    # we remove "DocumentOpenedEvent" because it does not indicate an annotation
    interesting_events.remove("DocumentOpenedEvent")
    filtered_df = df[df["event"].isin(interesting_events)]

    unique_year = sorted(filtered_df["created_readable"].dt.year.unique())
    selected_year = st.selectbox("Select a year", unique_year, index=0)
    filtered_df = filtered_df[(df["created_readable"].dt.year == selected_year)]

    selected_option = st.checkbox("Filter by month too?")
    if selected_option:
        unique_month = sorted(filtered_df["created_readable"].dt.month.unique())
        selected_month = st.selectbox("Select a month", unique_month, index=0)
        filtered_df = filtered_df[(df["created_readable"].dt.month == selected_month)]

    threshold = st.slider(
        "Threshold for Session Breaks (minutes)",
        min_value=1,
        max_value=10,
        value=1,
        step=1,
    )
    threshold = threshold * 60000

    filtered_df = filtered_df.sort_values(by="created", ascending=True)
    filtered_df["time_interval"] = filtered_df["created"].diff()
    filtered_df["session"] = (filtered_df["time_interval"] > threshold).cumsum() + 1
    filtered_df.reset_index(inplace=True)

    filtered_df["duration"] = filtered_df.groupby("session")[
        "created_readable"
    ].transform(lambda x: x.max() - x.min())
    filtered_df["duration_readable"] = filtered_df["duration"].apply(lambda x: str(x))
    filtered_df["duration_seconds"] = filtered_df["duration"].dt.total_seconds()
    filtered_df["duration_minutes"] = filtered_df["duration"].dt.total_seconds() / 60
    filtered_df["duration_hours"] = filtered_df["duration"].dt.total_seconds() / 3600

    cumulative_sessions_duration = (
        filtered_df.groupby(["user", "session"])["duration_hours"]
        .first()
        .groupby("user")
        .transform("cumsum")
        .groupby("user")
        .max()
    )

    # Generate formatted x-labels for users based on session count per user
    user_sessions_count = (
        filtered_df.groupby(["user", "session"])["duration_hours"]
        .first()
        .cumsum()
        .reset_index()
        .groupby("user")
        .size()
    )
    x_labels = [
        f"{user}\n{sessions} Sessions" for user, sessions in user_sessions_count.items()
    ]

    fig, ax = plt.subplots(figsize=(12, 6))

    for user, user_data in cumulative_sessions_duration.to_dict().items():
        ax.bar(
            user,
            user_data,
            label=user,
        )

    ax.set_xlabel("User")
    ax.set_ylabel("Cumulative Duration")
    ax.set_title(f"Cumulative Time (hours) Spent on Documents")
    ax.legend()
    ax.grid(True)
    ax.set_xticks(range(0, len(x_labels)))
    ax.set_xticklabels(x_labels, rotation=45)
    st.pyplot(fig)

    # Calculates the average session duration per user
    # denominator: cumluative time spent per user, in minutes
    # numerator: total amount of sessions per user
    average_sess_duration = (
        filtered_df.groupby(["user", "session"])["duration_minutes"]
        .first()
        .groupby("user")
        .transform("cumsum")
        .groupby("user")
        .max()
        / filtered_df.groupby(["user", "session"])["duration_minutes"]
        .first()
        .cumsum()
        .reset_index()
        .groupby("user")
        .size()
    )

    fig2, ax2 = plt.subplots(figsize=(12, 6))

    for user, user_data in average_sess_duration.to_dict().items():
        ax2.bar(
            user,
            user_data,
            label=user,
        )

    ax2.set_xlabel("User")
    ax2.set_ylabel("Average Time (minutes)")
    ax2.set_title(f"Average time per session (minutes) spent on Documents")
    ax2.legend()
    ax2.grid(True)
    ax2.set_xticks(range(0, len(x_labels)))
    ax2.set_xticklabels(x_labels, rotation=45)
    st.pyplot(fig2)

    # Calculates the average session duration per user
    # denominator: cumluative time spent per user, in seconds
    # numerator: total amount of events, i.e. annotations, per user
    avg_time_per_annotation = (
        filtered_df.groupby(["user", "session"])["duration_seconds"]
        .first()
        .groupby("user")
        .transform("cumsum")
        .groupby("user")
        .max()
        / filtered_df.groupby("user")["event"].count()
    )

    # Generate formatted x-labels for users based on total event, i.e. annotation, count per user
    x_labels = [
        f"{user}\n{sessions} Annos."
        for user, sessions in filtered_df.groupby("user")["event"]
        .count()
        .to_dict()
        .items()
    ]

    fig3, ax3 = plt.subplots(figsize=(12, 6))

    for user, user_data in avg_time_per_annotation.to_dict().items():
        ax3.bar(
            user,
            user_data,
            label=user,
        )

    ax3.set_xlabel("User")
    ax3.set_ylabel("Average time (seconds)")
    ax3.set_title(f"Average time (seconds) per Annotation")
    ax3.legend()
    ax3.grid(True)
    ax3.set_xticks(range(0, len(x_labels)))
    ax3.set_xticklabels(x_labels, rotation=45)
    st.pyplot(fig2)


def plot_project_progress(df) -> None:
    """
    Generate a visual representation of project progress based on a DataFrame of log data.

    This function takes a DataFrame containing log data and generates
    visualizations to represent the progress of different documents. It calculates the
    total time spent on each document, divides it into sessions based on a specified
    threshold, and displays a pie chart showing the percentage of finished and remaining
    documents, along with a bar chart showing the total time spent on finished documents
    compared to the estimated time for remaining documents.

    Parameters:
        df (pandas.DataFrame): : The input DataFrame containing event data.

    """

    threshold_p = st.slider(
        "Threshold for Session Breaks (minutes)",
        min_value=1,
        max_value=10,
        value=1,
        step=1,
    )
    threshold = threshold_p * 60000

    finished_files = {}

    # Iterate over all documents
    # Calculate total amount of time spent on them
    for file, doc_df in df.groupby("document_name"):
        filtered_doc_df = doc_df[doc_df["event"].isin(interesting_events)]
        filtered_doc_df = filtered_doc_df.sort_values(by="created", ascending=True)
        filtered_doc_df.reset_index(inplace=True)

        # total time spent on document is the sum of time spent on events
        # between opening the document for the first time and marking it finished for the last time
        last_finish = filtered_doc_df[
            filtered_doc_df["details"].apply(
                lambda x: isinstance(x, dict) and x.get("state") == "FINISHED"
            )
        ].index.max()
        # If there is no "Finished" event, then the document hasn't been marked finished and is still in progress
        if math.isnan(last_finish):
            continue

        first_open = filtered_doc_df[
            filtered_doc_df["event"] == "DocumentOpenedEvent"
        ].index.min()
        # If there is no "DocumentOpenedEvent" then the document hasn't been opened yet, i.e. is not finished yet
        if math.isnan(first_open):
            continue

        # filter for events between first open and last finish
        filtered_doc_df = filtered_doc_df[first_open : last_finish + 1]
        filtered_doc_df["time_interval"] = filtered_doc_df["created"].diff()
        filtered_doc_df["session"] = (
            filtered_doc_df["time_interval"] > threshold
        ).cumsum() + 1
        filtered_doc_df.reset_index(inplace=True)

        # This is just a workaround for the first event not having an interval because it's the first event
        if math.isnan(filtered_doc_df.at[0, "time_interval"]):
            filtered_doc_df.at[0, "time_interval"] = threshold

        # calculate the duration of time spent on each session iteratively
        filtered_doc_df["duration"] = filtered_doc_df.groupby("session")[
            "created_readable"
        ].transform(lambda x: x.max() - x.min())
        filtered_doc_df["duration_minutes"] = (
            filtered_doc_df["duration"].dt.total_seconds() / 60
        )

        # cumluative amount of time spent on each session
        total_time = (
            filtered_doc_df.groupby(["session"])["duration_minutes"]
            .first()
            .cumsum()
            .max()
        )
        # store each file and its corresponding total amount of time
        finished_files[file] = total_time

    all_document_names = df["document_name"].unique()
    finished_document_names = list(finished_files.keys())
    remaining_document_names = [
        name for name in all_document_names if name not in finished_document_names
    ]

    finished_documents_times = list(finished_files.values())
    total_finished_time = int(np.sum(finished_documents_times))
    average_finished_time = int(np.mean(finished_documents_times))
    estimated_remaining_time = len(remaining_document_names) * average_finished_time

    project_progress_data = {
        "total_finished_time": total_finished_time,
        "estimated_remaining_time": estimated_remaining_time,
        "number_of_finished_documents": len(finished_document_names),
        "number_of_remaining_documents": len(remaining_document_names)
    }
    
    if st.button("Export finished files"):
        with open("project_progress_data.json", "w") as output_file:
            output_file.write(json.dumps(project_progress_data))
        st.success("Finished files exported successfully ✅")

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


def read_file(filename) -> pd.DataFrame:
    """
    Read a file and return a pandas dataframe, regardless of the file type.

    Parameters:
        filename (str): The name of the file to read.

    Returns
        pandas.DataFrame: A pandas dataframe containing the contents of the file.
    """
    if filename.endswith(".log"):
        return pd.read_json(filename, lines=True)
    elif filename.endswith(".zip"):
        with zipfile.ZipFile(filename, "r") as zip_file:
            # change the following line to only select files with the name event.log
            log_files = [name for name in zip_file.namelist() if name == "event.log"]
            if log_files:
                with zip_file.open(log_files[0]) as log_file:
                    return pd.read_json(log_file, lines=True)
    else:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Generate plots for logs of your INCEpTION project."
    )
    parser.add_argument("filename", help="The name of the file to process")
    args = parser.parse_args()
    filename = args.filename
    st.title(f"INCEpTION Project Statistics")

    df = read_file(filename)
    if df is None:
        st.write("Error: No log files found. Please check your input file.")
        st.stop()
    else:
        with st.sidebar:
            selected_option = st.radio(
                "Choose a plot:", ["Average Work Times", "Project Progress"], index=0
            )
        with st.sidebar:
            annonymize = st.checkbox("Anonymize annotators' names?")

        if annonymize:
            df = anonymize_users(df)

        df["created_readable"] = pd.to_datetime(df["created"], unit="ms")
        df["created_readable_dates"] = df["created_readable"].dt.date

        if selected_option == "Average Work Times":
            plot_averages(df)
        elif selected_option == "Project Progress":
            plot_project_progress(df.copy())


if __name__ == "__main__":
    main()