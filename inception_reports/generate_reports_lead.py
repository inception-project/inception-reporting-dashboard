import argparse
import json
import os
import warnings

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

# suppress deprecation warnings related to the use of the pyplot
# can be solved by sending the fig instead of the plt to streamlit
st.set_option("deprecation.showPyplotGlobalUse", False)
st.set_page_config(page_title="INCEpTION Reporting Dashboard", layout="centered")
warnings.filterwarnings("ignore", message="Boolean Series key will be reindexed to match DataFrame index")


def change_width(page_width=80) -> None:
    css=f'''
    <style>
    section.main > div {{max-width:{page_width}%}}
    </style>
    '''
    st.markdown(css, unsafe_allow_html=True)

def plot_multiples(projects, tag) -> None:

    st.title(f"Projects with tag: {tag}")
    plt.figure(figsize=(30, 6), dpi=800)

    pie_labels = [
        "New",
        "Annotation In Progress",
        "Annotation Finished",
        "Curation In Progress",
        "Curation Finished",
    ]
    pie_colors = [
        'tab:red',
        'cornflowerblue',
        'royalblue',
        'limegreen',
        'forestgreen',
    ]

    for idx, project in enumerate(projects):
        plt.subplot(1, len(projects), idx+1)
        plt.title(project["project_name"].split(".")[0], fontsize=22, fontweight="bold")
        data_sizes = [
            project["doc_categories"]["NEW"],
            project["doc_categories"]["ANNOTATION_IN_PROGRESS"],
            project["doc_categories"]["ANNOTATION_FINISHED"],
            project["doc_categories"]["CURATION_IN_PROGRESS"],
            project["doc_categories"]["CURATION_FINISHED"],
        ]

        pie_percentages = 100.0 * np.array(data_sizes) / np.array(data_sizes).sum()

        wedges, _ = plt.pie(
            data_sizes,
            colors=pie_colors,
            startangle=90,
            radius=2,
            counterclock=False
            )

        plt.axis("equal")

        legend_labels = [
            f"{label} ({percent:.2f}% / {size} files)"
            for label, size, percent in zip(pie_labels, data_sizes, pie_percentages)
        ]
        plt.legend(
            wedges,
            legend_labels,
            title="Categories",
            fontsize=12,
            loc="center left",
            bbox_to_anchor=(1, 0.5),
        )

    plt.tight_layout()
    st.pyplot()


def plot_project_progress(project_data, multiple=False) -> None:
    """
    Generate a visual representation of project progress based on an export of project details provided by the site manager.

    This function takes a dict containing project progress data and generates a pie chart showing the percentage of files finished vs. remaining.


    Parameters:
        project_data (dict): A dictionary containing project progress data.

    """
    st.title(f"Project: {project_data['project_name'].split('.')[0]}")

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
    plt.suptitle(f"Documents' Status\n{project_data['project_tags'][-1].upper()}", fontsize=16, fontweight="bold")
    wedges, texts = plt.pie(
        data_sizes,
        colors=pie_colors,
        startangle=140)

    plt.axis("equal")

    # Create a legend with labels and percentages
    legend_labels = [
        f"{label} ({percent:.2f}% / {size} files)"
        for label, size, percent in zip(pie_labels, data_sizes, pie_percentages)
    ]
    plt.legend(
        wedges,
        legend_labels,
        title="Categories",
        fontsize=12,
        loc="center left",
        bbox_to_anchor=(1, 0.5),
    )
    plt.tight_layout()
    st.pyplot()

def read_dir(dir) -> list[dict]:
    """
    Read a file and return a pandas dataframe, regardless of the file type.

    Parameters:
        dir (str): The dir of INCEpTION projects progress data.

    Returns
        List[dict]: A list of dicts containing the project progress data as json files.
    """
    projects = []

    for file in os.listdir(dir):
        projects.append(json.load(open(os.path.join(dir, file), "r")))
    return projects

def get_unique_tags(projects):
    """
    Get a list of unique tags from a list of projects.

    Args:
        projects (list): A list of projects.

    Returns:
        list: A list of unique tags extracted from the projects.
    """
    unique_tags = set()
    for project in projects:
        unique_tags.update(project.get('project_tags', []))
    return list(unique_tags)


def main():
    parser = argparse.ArgumentParser(
        description="Generate plots for your INCEpTION project."
    )
    parser.add_argument("projects_folder", help="The folder of INCEpTION projects.")
    args = parser.parse_args()

    change_width(80)
    st.title("INCEpTION Projects Progress")

    projects = read_dir(args.projects_folder)
    projects.sort(key=lambda x: x["project_name"])

    unique_tags = get_unique_tags(projects)
    
    selected_tags = []
    columns = st.columns(len(unique_tags))

    for col, tag in zip(columns, unique_tags):
        if col.checkbox(tag.capitalize(), key=tag):
            selected_tags.append(tag)

    for tag in selected_tags:
        multi_projects = [project for project in projects if tag in project["project_tags"]]
        plot_multiples(multi_projects, tag)


if __name__ == "__main__":
    main()