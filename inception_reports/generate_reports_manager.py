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
import gc
import importlib.resources
import io
import json
import logging
import os
import re
import shutil
import time
import zipfile
from collections import defaultdict
from datetime import datetime
from itertools import islice

import cassis
import pandas as pd
import pkg_resources
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from pycaprio import Pycaprio
from rdflib.plugins.stores.sparqlstore import SPARQLStore
from inception_reports.dashboard_version import DASHBOARD_VERSION

st.set_page_config(
    page_title="INCEpTION Reporting Dashboard",
    layout="wide",
    initial_sidebar_state=st.session_state.setdefault("sidebar_state", "expanded"),
)

if st.session_state.get("flag"):
    st.session_state.sidebar_state = st.session_state.flag
    del st.session_state.flag
    time.sleep(0.01)
    st.rerun()


log = logging.getLogger()


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
        section.main > div {max-width:95%}
        </style>
        """,
        unsafe_allow_html=True,
    )

    project_info = get_project_info()
    if project_info:
        current_version = project_info
        package_name = "inception-reports"
        latest_version = check_package_version(current_version, package_name)
        version_message = f"Dashboard Version: {current_version}"
        
        if latest_version and pkg_resources.parse_version(current_version) < pkg_resources.parse_version(latest_version):
            st.sidebar.warning(f"{version_message} (Update available: {latest_version})")
        else:
            st.sidebar.info(version_message)


def get_project_info():
    return DASHBOARD_VERSION


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
        
def ensure_default_config():
    """
    Ensure excluded_types.json exists in ~/.inception_reports.
    If not, copy the packaged default there.
    """
    home_dir = os.path.expanduser("~")
    config_dir = os.path.join(home_dir, ".inception_reports")
    os.makedirs(config_dir, exist_ok=True)

    user_config = os.path.join(config_dir, "excluded_types.json")

    if not os.path.exists(user_config):
        try:
            with importlib.resources.path("inception_reports.data", "excluded_types.json") as default_path:
                shutil.copy(default_path, user_config)
                log.info(f"Copied default excluded_types.json to {user_config}")
        except Exception as e:
            log.error(f"Failed to copy default excluded_types.json: {e}")

    return user_config

        
def load_excluded_types():
    """
    Always load excluded types from ~/.inception_reports/excluded_types.json.
    Ensures the file exists by copying the packaged default if necessary.
    """
    config_path = ensure_default_config()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        excluded = set(config.get("excluded_types", []))
        # excluded.add(None)  # handle None explicitly
        return excluded
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Could not read excluded_types.json: {e}")
        return set()

def batched(iterable, n):
    """Yield successive n-sized batches from iterable."""
    it = iter(iterable)
    while batch := list(islice(it, n)):
        yield batch

def get_snomed_semantic_tag_map(
    base_url: str,
    project_id: int,
    kb_id: str,
    snomed_ids: set,
    auth: tuple = None,
    batch_size: int = 50,
) -> dict:
    """
    Query the INCEpTION SPARQL endpoint to retrieve SNOMED semantic tags
    for a batch of concept IDs at once.

    Returns:
        dict[str, str]: Mapping of full SNOMED URI -> semantic tag (e.g., "disorder").
    """

    # Ensure scheme is present
    if not base_url.startswith(("http://", "https://")):
        base_url = f"http://{base_url}"

    base_url = f"{base_url.rstrip('/')}/api/aero/v1"
    endpoint = f"{base_url}/projects/{project_id}/kbs/{kb_id}/sparql"
    headers = {"Accept": "application/sparql-results+xml"}

    semantic_map = {}
    paren_pattern = re.compile(r'\(([^)]+)\)')

    for batch in batched(snomed_ids, batch_size):
        values_clause = "\n    ".join(f"<{uri}>" for uri in batch)
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?concept ?label WHERE {{
          VALUES ?concept {{ {values_clause} }}
          ?concept (rdfs:label) ?label .
          FILTER (lang(?label) = "en")
        }}
        """

        try:
            store = SPARQLStore(
                endpoint,
                method="POST",
                auth=auth,
                returnFormat="xml",
                headers=headers,
            )
            results = store.query(query)

            for row in results:
                concept_uri = str(row.concept)
                label = str(row.label)
                matches = paren_pattern.findall(label)
                if matches:
                    semantic_map[concept_uri] = matches[-1]

        except Exception as e:
            log.warning(f"SPARQL batch query failed for {len(batch)} IDs: {e}")

    return semantic_map


def get_kb_id_from_project_meta(project_meta: dict) -> str | None:
    """
    Determine which knowledge base ID to use from the exportedproject.json metadata.

    - If any layer feature type starts with "kb:", a KB is needed.
    - If that feature's type is "kb:<ANY>", return the first enabled KB's ID.
    - Otherwise, return the KB matching the feature's KB name (if specified).
    """
    knowledge_bases = project_meta.get("knowledge_bases", [])
    if not knowledge_bases:
        return None

    kb_id = None

    for layer in project_meta.get("layers", []):
        for feature in layer.get("features", []):
            feature_type = feature.get("type", "")
            if feature_type.startswith("kb:"):
                kb_type = feature_type.split("kb:", 1)[1]
                if kb_type == "<ANY>":
                    # Use the first enabled KB
                    for kb in knowledge_bases:
                        if kb.get("enabled", False):
                            kb_id = kb.get("id")
                            break
                else:
                    # Try to match the KB name (case-insensitive)
                    for kb in knowledge_bases:
                        if kb["name"].lower() == kb_type.lower():
                            kb_id = kb.get("id")
                            break
            if kb_id:
                break
        if kb_id:
            break

    return kb_id


def read_dir(
    dir_path: str,
    selected_projects_data: dict,
    mode: str,
    api_url: str = None,
    auth: tuple = None,
    progress_callback=None,
) -> list[dict]:

    projects = []

    # Load excluded types once per read, not per CAS
    excluded_types = load_excluded_types()

    # ---- Pre-count all CAS files across all selected projects (for global progress bar) ----
    total_cas_overall = 0
    for file_name in os.listdir(dir_path):
        project_stem = file_name.split(".")[0]
        if selected_projects_data and project_stem not in selected_projects_data:
            continue

        file_path = os.path.join(dir_path, file_name)
        if not zipfile.is_zipfile(file_path):
            continue

        try:
            with zipfile.ZipFile(file_path, "r") as zip_file:
                try:
                    project_meta = json.loads(
                        zip_file.read("exportedproject.json").decode("utf-8")
                    )
                except KeyError:
                    # If the project is malformed, skip it entirely
                    continue

                project_documents = project_meta.get("source_documents", [])
                if not project_documents:
                    continue

                for doc in project_documents:
                    doc_name = doc["name"]
                    state = doc.get("state", "")
                    folder_prefix = (
                        f"curation/{doc_name}/"
                        if state == "CURATION_FINISHED"
                        else f"annotation/{doc_name}/"
                    )
                    for info in zip_file.infolist():
                        if (
                            info.filename.startswith(folder_prefix)
                            and info.filename.endswith(".json")
                            and not info.is_dir()
                        ):
                            total_cas_overall += 1
        except Exception as e:
            log.error(f"Error pre-counting CAS files in {file_name}: {e}")
            continue

    if progress_callback and total_cas_overall == 0:
        # Inform the UI that there is nothing to process
        progress_callback(0, 0, None, None)

    processed_cas_overall = 0

    # ---- Actual processing loop (per project) ----
    for file_name in os.listdir(dir_path):
        project_stem = file_name.split(".")[0]
        if selected_projects_data and project_stem not in selected_projects_data:
            continue

        file_path = os.path.join(dir_path, file_name)
        if not zipfile.is_zipfile(file_path):
            continue

        try:
            with zipfile.ZipFile(file_path, "r") as zip_file:

                # ---- Read project metadata ----
                try:
                    project_meta = json.loads(
                        zip_file.read("exportedproject.json").decode("utf-8")
                    )
                except KeyError:
                    log.warning(f"No exportedproject.json found in {file_name}")
                    continue

                project_documents = project_meta.get("source_documents", [])
                if not project_documents:
                    log.warning(f"No source documents found in project {file_name}")
                    continue

                # ---- Extract tags from description ----
                description = project_meta.get("description", "")
                project_tags = (
                    [translate_tag(word.strip("#")) for word in description.split() if word.startswith("#")]
                    if description else []
                )

                log.info(f"Started processing project {file_name}")

                # ---- Prepare containers ----
                annotations = {}          # per-document → per-annotator → stats
                used_snomed_ids = set()

                # ---- Process each document ----
                for doc in project_documents:
                    doc_name = doc["name"]
                    state = doc.get("state", "")
                    annotations[doc_name] = {}

                    # Determine path (curation or annotation)
                    folder_prefix = (
                        f"curation/{doc_name}/"
                        if state == "CURATION_FINISHED"
                        else f"annotation/{doc_name}/"
                    )

                    # Collect CAS JSON files
                    matching_files = [
                        info.filename
                        for info in zip_file.infolist()
                        if info.filename.startswith(folder_prefix)
                        and info.filename.endswith(".json")
                        and not info.is_dir()
                    ]
                    
                    # Use INITIAL_CAS.json only if it is the *only* file
                    if len(matching_files) > 1:
                        matching_files = [p for p in matching_files if not p.endswith("INITIAL_CAS.json")]

                    if not matching_files:
                        log.warning(
                            f"No CAS found for {doc_name} in {file_name} ({folder_prefix})"
                        )
                        continue

                    # ---- Load each CAS, compute stats, discard CAS ----
                    for cas_path in matching_files:
                        annotator_name = os.path.splitext(os.path.basename(cas_path))[0]

                        try:
                            with zip_file.open(cas_path) as cas_file:
                                cas = cassis.load_cas_from_json(cas_file)

                            cas_counts, cas_snomed_ids = compute_cas_stats(cas, excluded_types)
                            annotations[doc_name][annotator_name] = cas_counts
                            used_snomed_ids.update(cas_snomed_ids)

                            # Drop CAS immediately
                            del cas

                        except Exception as e:
                            log.warning(f"Failed to load {cas_path} from {file_name}: {e}")

                        # Update global UI progress
                        processed_cas_overall += 1
                        if progress_callback and total_cas_overall > 0:
                            progress_callback(
                                processed_cas_overall,
                                total_cas_overall,
                                current_project=project_stem,
                                current_doc=doc_name,
                            )

                # ---- Fetch SNOMED mappings (API mode only) ----
                snomed_label_map = {}
                if mode == "manual":
                    log.info("SNOMED labels are not supported in manual mode")

                elif mode == "api":
                    kb_id = get_kb_id_from_project_meta(project_meta)
                    if kb_id:
                        log.info(f"Detected KB '{kb_id}' for project {file_name}")
                    else:
                        log.warning(f"No KB detected for project {file_name}")

                    if api_url and auth and kb_id and used_snomed_ids:
                        project_id = selected_projects_data[project_stem]
                        snomed_label_map = get_snomed_semantic_tag_map(
                            api_url,
                            project_id,
                            kb_id,
                            used_snomed_ids,
                            auth=auth,
                        )
                        log.info(
                            f"Fetched SNOMED labels for {len(snomed_label_map)} concepts in {file_name}"
                        )

                # ---- Append project ----
                projects.append(
                    {
                        "name": file_name,
                        "tags": project_tags if project_tags else None,
                        "documents": project_documents,
                        "annotations": annotations,
                        "snomed_labels": snomed_label_map,
                        "inception_version": project_meta.get("application_version", "Older than 38.4"),
                    }
                )

            # Encourage cleanup
            gc.collect()

        except Exception as e:
            log.error(f"Error processing {file_name}: {e}")
            continue

    # Ensure the progress bar ends at 100% in the UI
    if progress_callback and total_cas_overall > 0:
        progress_callback(total_cas_overall, total_cas_overall, None, None)

    # Explicitly trigger garbage collection just to make sure all resources are freed
    gc.collect()
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
        try:
            inception_client.api.projects()
            st.sidebar.success("Login successful ✅")
            return True, inception_client
        except Exception:
            st.sidebar.error("Login unsuccessful ❌")
            return False, None
    return False, None


def select_method_to_import_data(progress_container=None):
    """
    Allows the user to select a method to import data for generating reports.
    """

    def init_progress():
        """
        Create a label + progress bar in the top-of-page container and return a
        Streamlit-friendly progress callback.

        Returns:
            (progress_label, progress_bar, progress_callback)
        """
        if progress_container is None:
            return None, None, None

        container = progress_container.container()
        progress_label = container.empty()
        progress_bar = container.progress(0)

        def progress_callback(done, total, current_project=None, current_doc=None):
            if progress_label is None or progress_bar is None:
                return

            if total <= 0:
                progress_label.text("No CAS files found to process.")
                progress_bar.progress(0)
                return

            fraction = min(max(done / total, 0.0), 1.0)
            percent = int(fraction * 100)
            msg = f"Generating reports: {done}/{total} CAS files"
            if current_project:
                msg += f" • Project: {current_project}"
            if current_doc:
                msg += f" • Document: {current_doc}"
            progress_label.text(msg)
            progress_bar.progress(percent)

        return progress_label, progress_bar, progress_callback

    method = st.sidebar.radio(
        "Choose your method to import data:", ("Manually", "API"), index=1
    )

    # --- MANUAL IMPORT ---
    if method == "Manually":
        uploaded_files = st.sidebar.file_uploader(
            "Upload project files:", accept_multiple_files=True, type="zip"
        )

        button = st.sidebar.button("Generate Reports")
        if button:
            if uploaded_files:
                temp_dir = os.path.join(
                    os.path.expanduser("~"), ".inception_reports", "temp_uploads"
                )
                os.makedirs(temp_dir, exist_ok=True)

                for uploaded_file in uploaded_files:
                    file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.read())

                selected_projects = [f.name.split(".")[0] for f in uploaded_files]

                progress_label, progress_bar, progress_callback = init_progress()

                st.session_state["projects"] = read_dir(
                    dir_path=temp_dir,
                    selected_projects_data={name: -1 for name in selected_projects},
                    mode="manual",
                    progress_callback=progress_callback,
                )
                st.session_state["projects_folder"] = temp_dir

                if progress_label is not None and progress_bar is not None:
                    progress_label.text("Report generation complete.")
                    progress_bar.progress(100)

            st.session_state["method"] = "Manually"
            button = False

    # --- API IMPORT ---
    elif method == "API":
        projects_folder = f"{os.path.expanduser('~')}/.inception_reports/projects"
        os.makedirs(os.path.dirname(projects_folder), exist_ok=True)
        st.session_state["projects_folder"] = projects_folder

        api_url = st.sidebar.text_input("Enter API URL:", "")
        username = st.sidebar.text_input("Username:", "")
        password = st.sidebar.text_input("Password:", type="password", value="")

        inception_status = st.session_state.get("inception_status", False)
        inception_client = st.session_state.get("inception_client", None)

        if not inception_status:
            inception_status, inception_client = login_to_inception(
                api_url, username, password
            )
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
                selected_projects[project_id] = st.sidebar.checkbox(
                    project_name, value=False
                )
                st.session_state["selected_projects"] = selected_projects

            selected_projects_data = {}
            button = st.sidebar.button("Generate Reports")
            if button:
                # Determine which projects are actually selected
                selected_ids = [pid for pid, is_selected in selected_projects.items() if is_selected]
                if not selected_ids:
                    st.sidebar.warning("Please select at least one project to generate reports.")
                    return

                # --- TOP-OF-PAGE SPINNER + STATUS TEXT FOR EXPORT PHASE ---
                if progress_container is not None:
                    export_container = progress_container.container()
                else:
                    export_container = st.container()

                with export_container:
                    with st.spinner("Exporting selected projects from INCEpTION…"):

                        for _, project_id in enumerate(selected_ids, start=1):
                            project = inception_client.api.project(project_id)
                            project_name = project.project_name

                            selected_projects_data[project_name] = project_id
                            file_path = f"{projects_folder}/{project_name}.zip"

                            st.sidebar.write(f"Importing project: {project_name}")
                            log.info(
                                f"Importing project {project_name} into {file_path}"
                            )

                            project_export = inception_client.api.export_project(
                                project, "jsoncas"
                            )
                            with open(file_path, "wb") as f:
                                f.write(project_export)
                            log.debug("Import Success")

                # Clear spinner/status area before showing the CAS progress bar
                if progress_container is not None:
                    progress_container.empty()

                st.session_state["method"] = "API"

                # Now initialize the CAS-processing progress bar at the top
                progress_label, progress_bar, progress_callback = init_progress()

                st.session_state["projects"] = read_dir(
                    dir_path=projects_folder,
                    selected_projects_data=selected_projects_data,
                    api_url=api_url,
                    auth=(username, password),
                    mode="api",
                    progress_callback=progress_callback,
                )

                if progress_label is not None and progress_bar is not None:
                    progress_label.text("Report generation complete.")
                    progress_bar.progress(100)


    # --- AGGREGATION MODE SELECTOR (always visible once projects exist) ---
    if "projects" in st.session_state or "projects_folder" in st.session_state:
        st.sidebar.markdown("---")
        aggregation_mode = st.sidebar.radio(
            "Annotation Aggregation Mode",
            ("Sum", "Average", "Max"),
            index=0,
            help=(
                "How to combine multiple annotator CAS files per document:\n\n"
                "- **Sum**: Count all annotations from all annotators (default)\n"
                "- **Average**: Normalize counts by number of annotators\n"
                "- **Max**: Take the annotator with the most annotations"
            ),
        )
        st.session_state["aggregation_mode"] = aggregation_mode
    
    st.sidebar.markdown("---")
    # --- Visualization scope toggle ---
    show_only_curated = st.sidebar.checkbox(
        "Show only curated documents in bar chart",
        value=True,
        help="If checked, the annotation type bar chart will only include documents whose state is CURATION_FINISHED.",
    )
    st.session_state["show_only_curated"] = show_only_curated





def find_element_by_name(element_list, name):
    """
    Finds an element in the given element list by its name.

    Args:
        element_list (list): A list of elements to search through.
        name (str): The name of the element to find.

    Returns:
        str: The UI name of the found element, or the last part of the name if not found.
    """
    # if "gemtex" in name:
        # return name
    for element in element_list:
        if element.name == name:
            return element.uiName
    return name.split(".")[-1]

def compute_cas_stats(cas, excluded_types):
    """
    Compute lightweight stats for a single CAS and return:
      - counts: {type_ui_name: {"total": int, "features": {value: count}}}
      - snomed_ids: set of SNOMED IDs seen in gemtex.Concept/id

    This avoids keeping the CAS object around after counting.
    """
    counts = defaultdict(lambda: {"total": 0, "features": defaultdict(int)})
    snomed_ids = set()

    skip_features = {
        cassis.typesystem.FEATURE_BASE_NAME_END,
        cassis.typesystem.FEATURE_BASE_NAME_BEGIN,
        cassis.typesystem.FEATURE_BASE_NAME_SOFA,
        "literal",
    }

    try:
        layer_defs = cas.select(
            "de.tudarmstadt.ukp.clarin.webanno.api.type.LayerDefinition"
        )
    except Exception:
        layer_defs = []

    for t in cas.typesystem.get_types():
        if t.name in excluded_types:
            continue

        relevant_features = [
            f for f in t.all_features if f.name not in skip_features
        ]
        if not relevant_features:
            continue

        is_concept_type = t.name == "gemtex.Concept"
        has_any = False
        type_entry = None

        for item in cas.select(t.name):
            if not has_any:
                type_name = find_element_by_name(layer_defs, t.name)
                type_entry = counts[type_name]
                has_any = True

            type_entry["total"] += 1

            for feature in relevant_features:
                value = item.get(feature.name)
                if value is None:
                    continue
                if is_concept_type and feature.name == "id":
                    snomed_ids.add(value)
                type_entry["features"][value] += 1

    return counts, snomed_ids


def get_type_counts(annotations, snomed_labels=None, aggregation_mode="Sum"):
    """
    Calculate the count of each annotation type across all documents.

    Args:
        annotations (dict):
            {doc_name: {annotator_name: cas_stats}}
            where cas_stats is:
                {type_name: {'total': int, 'features': {value: count}}}
        snomed_labels (dict): Optional mapping for SNOMED concept IDs -> semantic tag.
        aggregation_mode (str): One of "Sum", "Average", or "Max".

    Returns:
        dict: {type_name: {'total': count, 'documents': {doc_id: count}, 'features': {...}}}
    """

    type_count = {}

    def merge_counts(counts_list):
        merged = defaultdict(lambda: {"total": 0, "features": defaultdict(int)})
        for cdict in counts_list:
            for t, vals in cdict.items():
                merged[t]["total"] += vals["total"]
                for feat, feat_count in vals["features"].items():
                    merged[t]["features"][feat] += feat_count
        return merged

    def average_counts(counts_list):
        if not counts_list:
            return {}
        merged = merge_counts(counts_list)
        n = len(counts_list)
        for t, vals in merged.items():
            vals["total"] = round(vals["total"] / n)
            for feat in list(vals["features"].keys()):
                vals["features"][feat] = round(vals["features"][feat] / n)
        return merged

    def max_counts(counts_list):
        max_total = 0
        best = {}
        for cdict in counts_list:
            total = sum(v["total"] for v in cdict.values())
            if total > max_total:
                max_total = total
                best = cdict
        return best

    for doc_name, annotator_map in annotations.items():
        cas_stats_list = list(annotator_map.values())
        if not cas_stats_list:
            continue

        if aggregation_mode == "Sum":
            combined_counts = merge_counts(cas_stats_list)
        elif aggregation_mode == "Average":
            combined_counts = average_counts(cas_stats_list)
        elif aggregation_mode == "Max":
            combined_counts = max_counts(cas_stats_list)
        else:
            combined_counts = merge_counts(cas_stats_list)

        # Apply SNOMED mapping at the aggregated per-document level for Concept type
        if snomed_labels:
            concept_counts = combined_counts.get("Concept")
            if concept_counts:
                mapped_features = defaultdict(int)
                for raw_val, count in concept_counts["features"].items():
                    label = snomed_labels.get(raw_val, raw_val)
                    mapped_features[label] += count
                concept_counts["features"] = mapped_features

        for tname, vals in combined_counts.items():
            if tname not in type_count:
                type_count[tname] = {"total": 0, "documents": {}, "features": {}}
            type_count[tname]["total"] += vals["total"]
            type_count[tname]["documents"][doc_name] = vals["total"]

            for feat_val, feat_count in vals["features"].items():
                if feat_val not in type_count[tname]["features"]:
                    type_count[tname]["features"][feat_val] = {}
                type_count[tname]["features"][feat_val][doc_name] = feat_count

    for tname, tvals in type_count.items():
        tvals["features"] = dict(
            sorted(tvals["features"].items(), key=lambda x: sum(x[1].values()), reverse=True)
        )
    type_count = dict(
        sorted(type_count.items(), key=lambda item: item[1]["total"], reverse=True)
    )

    return type_count



def export_data(project_data):
    """
    Export project data to a JSON file, and store it in a directory named after the project and the current date.

    Parameters:
        project_data (dict): The data to be exported.
    """
    current_date = datetime.now().strftime("%Y_%m_%d")

    output_directory = os.getenv("INCEPTION_OUTPUT_DIR")

    if output_directory is None:
        output_directory = os.path.join(os.getcwd(), "exported_project_data")

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    project_name = project_data["project_name"]

    with open(
        f"{output_directory}/{project_name.split('.')[0]}_{current_date}.json", "w"
    ) as output_file:
        json.dump(project_data, output_file, indent=4)
    st.success(
        f"{project_name.split('.')[0]} documents status exported successfully to {output_directory} ✅"
    )


def create_zip_download(reports):
    """
    Create a zip file containing all generated JSON reports and provide a download button.
    """

    if reports:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for report in reports:
                file_name = f"{report['project_name'].split('.')[0]}_{report['created']}.json"
                json_data = json.dumps(report, indent=4)
                zip_file.writestr(file_name, json_data)

        zip_buffer.seek(0)

        st.download_button(
            label="Download All Reports (ZIP)",
            file_name="all_reports.zip",
            mime="application/zip",
            data=zip_buffer.getvalue(),
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
    aggregation_mode = st.session_state.get("aggregation_mode", "Sum")
    type_counts = get_type_counts(project_annotations, project.get("snomed_labels", {}), aggregation_mode)

    show_only_curated = st.session_state.get("show_only_curated", True)

    curated_docs = {
        doc["name"]
        for doc in project["documents"]
        if doc.get("state") == "CURATION_FINISHED"
    }

    # If no curated documents exist, force disable this mode
    if show_only_curated and not curated_docs:
        st.warning(
            f"No curated documents found in project **{project['name']}** — "
            "showing annotations break down for all other documents instead."
        )
        show_only_curated = False
        st.session_state["show_only_curated"] = False

    # Proceed with filtering only if the flag is still True
    if show_only_curated:
        curated_type_counts = {}

        for tname, tvals in type_counts.items():
            curated_docs_counts = {
                doc: count for doc, count in tvals["documents"].items() if doc in curated_docs
            }

            if not curated_docs_counts:
                continue  # skip types that appear only in non-curated docs

            curated_total = sum(curated_docs_counts.values())

            curated_features = {}
            for feat, feat_docs in tvals["features"].items():
                filtered_feat_docs = {
                    doc: count for doc, count in feat_docs.items() if doc in curated_docs
                }
                if filtered_feat_docs:
                    curated_features[feat] = filtered_feat_docs

            curated_type_counts[tname] = {
                "total": curated_total,
                "documents": curated_docs_counts,
                "features": curated_features,
            }

        # Keep both versions
        full_type_counts = type_counts
        type_counts = curated_type_counts
    else:
        # Use all documents
        full_type_counts = type_counts


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

    doc_token_categories = {
        "ANNOTATION_IN_PROGRESS": 0,
        "ANNOTATION_FINISHED": 0,
        "CURATION_IN_PROGRESS": 0,
        "CURATION_FINISHED": 0,
        "NEW": 0,
    }

    for doc in project_documents:
        log.debug(f"Start processing tokens for document {doc}")
        state = doc["state"]
        if state in doc_token_categories:
            token_docs = full_type_counts.get("Token", {}).get("documents", {})
            doc_token_categories[state] += token_docs.get(doc["name"], 0)

    output_type_counts = {}
    doc_states = {doc["name"]: doc["state"] for doc in project_documents}

    for category, details in full_type_counts.items():
        # Calculate total count split by document status
        total_by_status = defaultdict(int)
        for doc_name, count in details["documents"].items():
            state = doc_states.get(doc_name, "UNKNOWN")
            total_by_status[state] += count
        
        output_type_counts[category] = {
            "total": details["total"],
            "total_by_status": dict(total_by_status)
        }

        if category in ["PHI", "Concept"]:
            feature_state_breakdown = defaultdict(lambda: defaultdict(int))
            
            for feature_value, doc_counts in details["features"].items():
                for doc_name, count in doc_counts.items():
                    state = doc_states.get(doc_name, "UNKNOWN")
                    feature_state_breakdown[feature_value][state] += count

            # Convert to regular dict for export
            output_type_counts[category]["features"] = {
                feature: dict(state_counts)
                for feature, state_counts in feature_state_breakdown.items()
            }



    project_data = {
        "project_name": project_name,
        "project_tags": project_tags,
        "doc_categories": doc_categories,
        "doc_token_categories": doc_token_categories,
        "type_counts": output_type_counts,
        "aggregation_mode": st.session_state.get("aggregation_mode", "Sum"),
        "created": datetime.now().date().isoformat(),
        "inception_version": project.get("inception_version"), 
        "dashboard_version": get_project_info() if get_project_info() else None,
    }

    data_sizes_docs = [
        project_data["doc_categories"]["NEW"],
        project_data["doc_categories"]["ANNOTATION_IN_PROGRESS"],
        project_data["doc_categories"]["ANNOTATION_FINISHED"],
        project_data["doc_categories"]["CURATION_IN_PROGRESS"],
        project_data["doc_categories"]["CURATION_FINISHED"],
    ]

    data_sizes_tokens = [
        project_data["doc_token_categories"]["NEW"],
        project_data["doc_token_categories"]["ANNOTATION_IN_PROGRESS"],
        project_data["doc_token_categories"]["ANNOTATION_FINISHED"],
        project_data["doc_token_categories"]["CURATION_IN_PROGRESS"],
        project_data["doc_token_categories"]["CURATION_FINISHED"],
    ]

    pie_labels = [
        "New",
        "Annotation In Progress",
        "Annotation Finished",
        "Curation In Progress",
        "Curation Finished",
    ]

    df_pie_docs = pd.DataFrame(
        {"Labels": pie_labels, "Sizes": data_sizes_docs}
    ).sort_values(by="Labels", ascending=True)
    df_pie_tokens = pd.DataFrame(
        {"Labels": pie_labels, "Sizes": data_sizes_tokens}
    ).sort_values(by="Labels", ascending=True)

    pie_chart = go.Figure()
    pie_chart.add_trace(
        go.Pie(
            labels=df_pie_docs["Labels"],
            values=df_pie_docs["Sizes"],
            sort=False,
            hole=0.4,
            hoverinfo="percent+label",
            textinfo="value",
        )
    )
    pie_chart.add_trace(
        go.Pie(
            labels=df_pie_tokens["Labels"],
            values=df_pie_tokens["Sizes"],
            sort=False,
            hole=0.4,
            hoverinfo="percent+label",
            textinfo="value",
            visible=False,
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
        updatemenus=[
            {
                "buttons": [
                    {
                        "label": "Documents",
                        "method": "update",
                        "args": [
                            {"visible": [True, False]},
                            {"title": "Documents Status"},
                        ],
                    },
                    {
                        "label": "Tokens",
                        "method": "update",
                        "args": [
                            {"visible": [False, True]},
                            {"title": "Tokens Status"},
                        ],
                    },
                ],
                "direction": "down",
                "showactive": True,
            }
        ],
    )

    bar_chart = go.Figure()

    main_traces = 0
    total_feature_traces = 0
    category_trace_mapping = {}

    for category, details in type_counts.items():
        bar_chart.add_trace(
            go.Bar(
                y=[category],
                x=[details["total"]],
                text=[details["total"]],
                textposition="auto",
                name=category.capitalize(),
                visible=True,
                orientation="h",
                hoverinfo="x+y",
            )
        )
        main_traces += 1

    feature_buttons = []
    max_features_per_type = 30  # limit feature drilldown size to improve performance

    for category, details in type_counts.items():
        features_items = list(details["features"].items())
        if len(features_items) < 2:
            continue

        # Use only the top-N features (already sorted by frequency)
        top_features = features_items[:max_features_per_type]

        category_start = total_feature_traces
        for subcategory, value in top_features:
            # For PHI, value is a dict with per-document counts, for others it's a total
            if isinstance(value, dict):
                total_value = sum(value.values())
            else:
                total_value = value

            bar_chart.add_trace(
                go.Bar(
                    y=[subcategory],
                    x=[total_value],
                    text=[total_value],
                    textposition="auto",
                    name=subcategory,
                    visible=False,
                    orientation="h",
                    hoverinfo="x+y",
                )
            )
            total_feature_traces += 1

        category_end = total_feature_traces
        category_trace_mapping[category] = (category_start, category_end)

        visibility = [False] * main_traces + [False] * total_feature_traces
        for i in range(category_start, category_end):
            visibility[main_traces + i] = True

        feature_buttons.append(
            {
                "args": [{"visible": visibility}],
                "label": category,
                "method": "update",
            }
        )

    bar_chart_buttons = [
        {
            "args": [{"visible": [True] * main_traces + [False] * total_feature_traces}],
            "label": "Overview",
            "method": "update",
        }
    ] + feature_buttons

    bar_chart.update_layout(
        title=dict(
            text=f"Types of Annotations {'(Curated Docs)' if show_only_curated else '(All Docs)'}",
            font=dict(size=24),
            y=0.95,
            x=0.45,
            xanchor="center",
        ),
        xaxis_title="Number of Annotations",
        barmode="overlay",
        height=max(200, min(160 * len(type_counts), 500)),
        font=dict(size=18),
        legend=dict(font=dict(size=10)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10),
        colorway=px.colors.qualitative.Plotly,
    )

    bar_chart.update_layout(
        updatemenus=[
            {
                "buttons": bar_chart_buttons,
                "direction": "down",
                "showactive": True,
                "x": 0.45,
                "y": 1.15,
                "xanchor": "center",
                "yanchor": "top",
            }
        ]
    )

    col1, _, col3 = st.columns([1, 0.1, 1])
    with col1:
        st.plotly_chart(pie_chart, use_container_width=True)
    with col3:
        st.plotly_chart(bar_chart, use_container_width=True)

    return project_data



def main():

    startup()
    create_directory_in_home()

    st.write(
        "<style> h1 {text-align: center; margin-bottom: 50px, } </style>",
        unsafe_allow_html=True,
    )
    st.title("INCEpTION Reporting Dashboard")
    st.write("<hr>", unsafe_allow_html=True)
    progress_container = st.empty()
    select_method_to_import_data(progress_container=progress_container)

    generated_reports = []
    if "method" in st.session_state and "projects" in st.session_state:
        projects = [copy.deepcopy(project) for project in st.session_state["projects"]]
        projects = sorted(projects, key=lambda x: x["name"])
        for project in projects:
            project_data = plot_project_progress(project)
            export_data(project_data)
            generated_reports.append(project_data)
        st.write("<hr>", unsafe_allow_html=True)
        create_zip_download(generated_reports)


if __name__ == "__main__":
    main()
