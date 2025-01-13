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
import time

import pandas as pd
import pkg_resources
import plotly.graph_objects as go
import requests
import streamlit as st
import toml
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="INCEpTION Reporting Dashboard",
    layout="centered",
    initial_sidebar_state=st.session_state.setdefault("sidebar_state", "expanded"),
)

if st.session_state.get("flag"):
    st.session_state.sidebar_state = st.session_state.flag
    del st.session_state.flag  # or you could do => st.session_state.flag = False
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
        .block-container {
            padding-top: 0rem;
            padding-bottom: 5rem;
            padding-left: 5rem;
            padding-right: 5rem;
        }
        </style>

        <style>
        div[data-testid="stFullScreenFrame"] {
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


def set_sidebar_state(value):
    if st.session_state.sidebar_state == value:
        st.session_state.flag = value
        st.session_state.sidebar_state = (
            "expanded" if value == "collapsed" else "collapsed"
        )
    else:
        st.session_state.sidebar_state = value
    st.rerun()


def change_width(page_width=80) -> None:
    css = f"""
    <style>
    section.main > div {{max-width:{page_width}%}}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def plot_multiples(projects, tag) -> None:

    pie_labels = [
        "New",
        "Annotation In Progress",
        "Annotation Finished",
        "Curation In Progress",
        "Curation Finished",
    ]

    fig = make_subplots(
        rows=1, cols=len(projects), specs=[[{"type": "domain"}] * len(projects)]
    )
    for idx, project in enumerate(projects):
        # df_pie = pd.DataFrame(
        #     {"Labels": pie_labels, "Sizes": list(project["doc_categories"].values())}
        # ).sort_values(by="Labels")
        df_pie_docs = pd.DataFrame(
            {"Labels": pie_labels, "Sizes": list(project["doc_categories"].values())}
        ).sort_values(by="Labels", ascending=True)
        df_pie_tokens = pd.DataFrame(
            {
                "Labels": pie_labels,
                "Sizes": list(project["doc_token_categories"].values()),
            }
        ).sort_values(by="Labels", ascending=True)

        fig.add_trace(
            go.Pie(
                title=dict(
                    text=project["project_name"].split(".")[0],
                ),
                labels=df_pie_docs["Labels"],
                values=df_pie_docs["Sizes"],
                sort=False,
                name=project["project_name"].split(".")[0],
                hole=0.4,
                hoverinfo="percent+label",
                textinfo="value",
            ),
            1,
            idx + 1,
        )

        fig.add_trace(
            go.Pie(
                title=dict(
                    text=project["project_name"].split(".")[0],
                ),
                labels=df_pie_tokens["Labels"],
                values=df_pie_tokens["Sizes"],
                sort=False,
                name=project["project_name"].split(".")[0],
                hole=0.4,
                hoverinfo="percent+label",
                textinfo="value",
                visible=False,
            ),
            1,
            idx + 1,
        )

    fig.update_layout(
        title=dict(
            text=f"Documents Status of projects with tag: {tag}",
            font=dict(size=24),
            y=0.95,
            x=0.5,
            xanchor="center",
        ),
        font=dict(size=18),
        legend=dict(font=dict(size=16), y=0.5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=100, r=100),
        autosize=True,
        updatemenus=[
            {
                "buttons": [
                    {
                        "label": "Documents",
                        "method": "update",
                        "args": [
                            {"visible": [True, False]},
                            {"title": f"Documents Status of projects with tag: {tag}"},
                        ],
                    },
                    {
                        "label": "Tokens",
                        "method": "update",
                        "args": [
                            {"visible": [False, True]},
                            {"title": f"Tokens Status of projects with tag: {tag}"},
                        ],
                    },
                ],
                "direction": "down",
                "showactive": True,
            }
        ],
    )

    st.plotly_chart(fig, use_container_width=True)


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
        project_tags = project.get("project_tags")
        if project_tags:
            unique_tags.update(project_tags)
        else:
            st.warning(f"No tags found for project: {project['project_name']}")
    return list(unique_tags)


def select_data_folder_or_files():
    """
    Generate a sidebar widget to select the data folder or individual JSON files containing the INCEpTION projects.
    """

    st.sidebar.write(
        "Please input the path to the folder containing the INCEpTION projects:"
    )
    projects_folder = st.sidebar.text_input("Projects Folder:", value="")
    uploaded_files = st.sidebar.file_uploader(
        "Or Select project files manually:",
        type=["json"],
        accept_multiple_files=True,
    )
    button = st.sidebar.button("Generate Reports")
    if button:
        st.session_state["initialized"] = True
        if uploaded_files:
            st.write("Uploaded files: ", uploaded_files)
            st.session_state["projects"] = [json.load(file) for file in uploaded_files]
        elif projects_folder:
            st.session_state["projects"] = read_dir(projects_folder)
        button = False
        set_sidebar_state("collapsed")


def main():
    startup()
    st.write(
        "<style> h1 {text-align: center; margin-bottom: 50px, } </style>",
        unsafe_allow_html=True,
    )
    st.title("INCEpTION Reporting Dashboard")
    st.write("<hr>", unsafe_allow_html=True)

    select_data_folder_or_files()

    projects = []
    if st.session_state.get("initialized") and st.session_state.get("projects"):
        projects = [copy.deepcopy(project) for project in st.session_state["projects"]]
        projects = sorted(projects, key=lambda x: x["project_name"])

    if projects:
        unique_tags = get_unique_tags(projects)
        selected_tags = st.multiselect("Select a project tag:", unique_tags)
        for tag in selected_tags:
            multi_projects = [
                project
                for project in projects
                if (
                    project["project_tags"] is not None
                    and tag in project["project_tags"]
                )
            ]
            plot_multiples(multi_projects, tag)


if __name__ == "__main__":
    main()
