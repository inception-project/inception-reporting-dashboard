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
import plotly.graph_objects as go
import streamlit as st
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
        "Annotation In Progress",
        "Annotation Finished",
        "Curation In Progress",
        "Curation Finished",
        "New",
    ]

    fig = make_subplots(
        rows=1, cols=len(projects), specs=[[{"type": "domain"}] * len(projects)]
    )
    for idx, project in enumerate(projects):
        df_pie = pd.DataFrame(
            {"Labels": pie_labels, "Sizes": list(project["doc_categories"].values())}
        ).sort_values(by="Labels")

        fig.add_trace(
            go.Pie(
                title=dict(
                    text=project["project_name"].split(".")[0],
                ),
                labels=df_pie["Labels"],
                values=df_pie["Sizes"],
                sort=False,
                name=project["project_name"].split(".")[0],
                hole=0.4,
                hoverinfo="label+value",
            ),
            1,
            idx + 1,
        )

    fig.update_layout(
        title=dict(
            text=f"Projects with tag: {tag}",
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
        unique_tags.update(project.get("project_tags", []))
    return list(unique_tags)


def select_data_folder():
    """
    Generate a sidebar widget to select the data folder containing the INCEpTION projects.
    """

    st.sidebar.write(
        "Please input the path to the folder containing the INCEpTION projects."
    )
    projects_folder = st.sidebar.text_input(
        "Projects Folder:",
        value="",
    )
    button = st.sidebar.button("Generate Reports")
    if button:
        st.session_state["initialized"] = True
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

    select_data_folder()

    projects = []
    if st.session_state.get("initialized") and st.session_state.get("projects"):
        projects = [copy.deepcopy(project) for project in st.session_state["projects"]]
        projects = sorted(projects, key=lambda x: x["project_name"])

    if projects:
        unique_tags = get_unique_tags(projects)
        selected_tags = st.multiselect("Select a project tag:", unique_tags)

        for tag in selected_tags:
            multi_projects = [
                project for project in projects if tag in project["project_tags"]
            ]
            plot_multiples(multi_projects, tag)


if __name__ == "__main__":
    main()
