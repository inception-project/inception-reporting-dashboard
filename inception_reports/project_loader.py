# Licensed to the Technische Universitaet Darmstadt under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The Technische Universitaet Darmstadt
# licenses this file to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import gc
import json
import logging
import os
import re
import shutil
import ssl
import urllib.request
import zipfile
from functools import lru_cache
from importlib.resources import as_file, files
from itertools import islice
from pathlib import Path
from typing import Any, Callable

import cassis
import requests
from rdflib.plugins.stores.sparqlstore import SPARQLStore
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from inception_reports.reporting import compute_cas_stats

log = logging.getLogger(__name__)

INCEPTION_HOME_DIR = ".inception_reports"
PROJECTS_DIR_NAME = "projects"
EXCLUDED_TYPES_FILE = "excluded_types.json"
SPARQL_HEADERS = {"Accept": "application/sparql-results+xml"}


def create_directory_in_home() -> Path:
    home_directory = Path.home() / INCEPTION_HOME_DIR
    (home_directory / PROJECTS_DIR_NAME).mkdir(parents=True, exist_ok=True)
    return home_directory


@lru_cache(maxsize=1)
def _load_default_translation_map() -> dict[str, str]:
    data_directory = files("inception_reports.data")
    translation_map = {}
    for file_name in ("specialties.json", "document_types.json"):
        with data_directory.joinpath(file_name).open("r", encoding="utf-8") as handle:
            translation_map.update(json.load(handle))
    return translation_map


def translate_tag(tag: str, translation_path: str | None = None) -> str:
    if translation_path:
        with open(translation_path, "r", encoding="utf-8") as handle:
            translation_map = json.load(handle)
        return translation_map.get(tag, tag)

    return _load_default_translation_map().get(tag, tag)


def ensure_default_config() -> Path:
    config_directory = create_directory_in_home()
    user_config_path = config_directory / EXCLUDED_TYPES_FILE

    if user_config_path.exists():
        return user_config_path

    try:
        default_config = files("inception_reports.data").joinpath(EXCLUDED_TYPES_FILE)
        with as_file(default_config) as packaged_config:
            shutil.copy(packaged_config, user_config_path)
        log.info("Copied default excluded_types.json to %s", user_config_path)
    except Exception as error:
        log.error("Failed to copy default excluded_types.json: %s", error)

    return user_config_path


def load_excluded_types() -> set[str]:
    config_path = ensure_default_config()

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (json.JSONDecodeError, OSError) as error:
        log.warning("Could not read excluded_types.json: %s", error)
        return set()

    return set(config.get("excluded_types", []))


def batched(iterable, batch_size: int):
    iterator = iter(iterable)
    while batch := list(islice(iterator, batch_size)):
        yield batch


class CustomSSLAdapter(HTTPAdapter):
    def __init__(
        self, ca_bundle: str | None = None, verify_ssl: bool = True, **kwargs
    ) -> None:
        self.ca_bundle = ca_bundle
        self.verify_ssl = verify_ssl
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = _create_ssl_context(
            self.ca_bundle, self.verify_ssl, log_errors=False
        )
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs["ssl_context"] = _create_ssl_context(
            self.ca_bundle, self.verify_ssl, log_errors=False
        )
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def _create_ssl_context(
    ca_bundle: str | None = None,
    verify_ssl: bool = True,
    *,
    log_errors: bool = True,
) -> ssl.SSLContext:
    if not verify_ssl:
        context = create_urllib3_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    context = ssl.create_default_context()
    if not ca_bundle:
        return context

    if not os.path.isfile(ca_bundle) or not os.access(ca_bundle, os.R_OK):
        if log_errors:
            log.error("CA bundle file not found or not readable: %s", ca_bundle)
        return context

    context.load_verify_locations(cafile=ca_bundle)
    return context


def create_ssl_session(
    ca_bundle: str | None = None, verify_ssl: bool = True
) -> requests.Session:
    session = requests.Session()
    adapter = CustomSSLAdapter(ca_bundle=ca_bundle, verify_ssl=verify_ssl)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.verify = verify_ssl
    return session


def configure_ssl_context(
    ca_bundle: str | None = None, verify_ssl: bool = True
) -> None:
    try:
        ssl_context = _create_ssl_context(ca_bundle, verify_ssl)
        https_handler = urllib.request.HTTPSHandler(context=ssl_context)
        urllib.request.install_opener(urllib.request.build_opener(https_handler))
    except Exception as error:
        log.error("Failed to configure SSL context: %s", error, exc_info=True)


def get_snomed_semantic_tag_map(
    base_url: str,
    project_id: int,
    kb_id: str,
    snomed_ids: set[str],
    auth: tuple | None = None,
    batch_size: int = 50,
    ca_bundle: str | None = None,
    verify_ssl: bool = True,
) -> dict[str, str]:
    configure_ssl_context(ca_bundle=ca_bundle, verify_ssl=verify_ssl)

    if not base_url.startswith(("http://", "https://")):
        base_url = f"http://{base_url}"

    endpoint = (
        f"{base_url.rstrip('/')}/api/aero/v1/projects/{project_id}/kbs/{kb_id}/sparql"
    )
    semantic_map = {}
    parentheses_pattern = re.compile(r"\(([^)]+)\)")
    session = create_ssl_session(ca_bundle=ca_bundle, verify_ssl=verify_ssl)

    for batch in batched(snomed_ids, batch_size):
        values_clause = "\n    ".join(f"<{concept_uri}>" for concept_uri in batch)
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
                headers=SPARQL_HEADERS,
                httpsession=session,
            )
            for row in store.query(query):
                matches = parentheses_pattern.findall(str(row.label))
                if matches:
                    semantic_map[str(row.concept)] = matches[-1]
        except Exception as error:
            log.warning("SPARQL batch query failed for %s IDs: %s", len(batch), error)

    return semantic_map


def get_kb_id_from_project_meta(project_meta: dict[str, Any]) -> str | None:
    knowledge_bases = project_meta.get("knowledge_bases", [])
    if not knowledge_bases:
        return None

    for layer in project_meta.get("layers", []):
        for feature in layer.get("features", []):
            feature_type = feature.get("type", "")
            if not feature_type.startswith("kb:"):
                continue

            kb_type = feature_type.split("kb:", 1)[1]
            if kb_type == "<ANY>":
                for knowledge_base in knowledge_bases:
                    if knowledge_base.get("enabled", False):
                        return knowledge_base.get("id")
                continue

            for knowledge_base in knowledge_bases:
                if knowledge_base["name"].lower() == kb_type.lower():
                    return knowledge_base.get("id")

    return None


def _project_stem(file_name: str) -> str:
    return file_name.split(".")[0]


def _iter_selected_archives(
    dir_path: str, selected_projects_data: dict[str, Any] | None
) -> list[tuple[str, str, str]]:
    archives = []
    for file_name in sorted(os.listdir(dir_path)):
        project_stem = _project_stem(file_name)
        if selected_projects_data and project_stem not in selected_projects_data:
            continue

        file_path = os.path.join(dir_path, file_name)
        if zipfile.is_zipfile(file_path):
            archives.append((file_name, project_stem, file_path))

    return archives


def _load_project_meta(zip_file: zipfile.ZipFile, file_name: str) -> dict[str, Any] | None:
    try:
        return json.loads(zip_file.read("exportedproject.json").decode("utf-8"))
    except KeyError:
        log.warning("No exportedproject.json found in %s", file_name)
        return None


def _document_folder_prefix(document: dict[str, Any]) -> str:
    document_name = document["name"]
    if document.get("state") == "CURATION_FINISHED":
        return f"curation/{document_name}/"
    return f"annotation/{document_name}/"


def _matching_cas_files(
    zip_file: zipfile.ZipFile, document: dict[str, Any]
) -> list[str]:
    folder_prefix = _document_folder_prefix(document)
    matching_files = [
        info.filename
        for info in zip_file.infolist()
        if info.filename.startswith(folder_prefix)
        and info.filename.endswith(".json")
        and not info.is_dir()
    ]

    if len(matching_files) > 1:
        matching_files = [
            path for path in matching_files if not path.endswith("INITIAL_CAS.json")
        ]

    return matching_files


def _count_archive_cas_files(
    zip_file: zipfile.ZipFile, project_documents: list[dict[str, Any]]
) -> int:
    total = 0
    for document in project_documents:
        total += len(_matching_cas_files(zip_file, document))
    return total


def _project_tags(project_meta: dict[str, Any]) -> list[str]:
    description = project_meta.get("description", "")
    if not description:
        return []

    return [
        translate_tag(word.strip("#"))
        for word in description.split()
        if word.startswith("#")
    ]


def _load_document_annotations(
    zip_file: zipfile.ZipFile,
    file_name: str,
    project_stem: str,
    project_documents: list[dict[str, Any]],
    excluded_types: set[str],
    progress_callback,
    processed_cas_overall: int,
    total_cas_overall: int,
    compute_stats: Callable[[Any, set[str]], tuple[dict[str, Any], set[str]]],
) -> tuple[dict[str, dict[str, Any]], set[str], int]:
    annotations = {}
    used_snomed_ids = set()

    for document in project_documents:
        document_name = document["name"]
        annotations[document_name] = {}
        matching_files = _matching_cas_files(zip_file, document)

        if not matching_files:
            log.warning(
                "No CAS found for %s in %s (%s)",
                document_name,
                file_name,
                _document_folder_prefix(document),
            )
            continue

        for cas_path in matching_files:
            annotator_name = os.path.splitext(os.path.basename(cas_path))[0]
            try:
                with zip_file.open(cas_path) as cas_file:
                    cas = cassis.load_cas_from_json(cas_file)
                cas_counts, cas_snomed_ids = compute_stats(cas, excluded_types)
                annotations[document_name][annotator_name] = cas_counts
                used_snomed_ids.update(cas_snomed_ids)
                del cas
            except Exception as error:
                log.warning("Failed to load %s from %s: %s", cas_path, file_name, error)

            processed_cas_overall += 1
            if progress_callback and total_cas_overall > 0:
                progress_callback(
                    processed_cas_overall,
                    total_cas_overall,
                    current_project=project_stem,
                    current_doc=document_name,
                )

    return annotations, used_snomed_ids, processed_cas_overall


def _fetch_snomed_labels(
    *,
    mode: str,
    api_url: str | None,
    auth: tuple | None,
    project_meta: dict[str, Any],
    selected_projects_data: dict[str, Any],
    project_stem: str,
    used_snomed_ids: set[str],
    file_name: str,
    ca_bundle: str | None,
    verify_ssl: bool,
) -> dict[str, str]:
    if mode == "manual":
        log.info("SNOMED labels are not supported in manual mode")
        return {}

    kb_id = get_kb_id_from_project_meta(project_meta)
    if kb_id:
        log.info("Detected KB '%s' for project %s", kb_id, file_name)
    else:
        log.warning("No KB detected for project %s", file_name)
        return {}

    if not (api_url and auth and used_snomed_ids):
        return {}

    project_id = selected_projects_data[project_stem]
    semantic_map = get_snomed_semantic_tag_map(
        api_url,
        project_id,
        kb_id,
        used_snomed_ids,
        auth=auth,
        ca_bundle=ca_bundle,
        verify_ssl=verify_ssl,
    )
    log.info(
        "Fetched SNOMED labels for %s concepts in %s",
        len(semantic_map),
        file_name,
    )
    return semantic_map


def read_dir(
    dir_path: str,
    selected_projects_data: dict[str, Any],
    mode: str,
    api_url: str | None = None,
    auth: tuple | None = None,
    progress_callback=None,
    ca_bundle: str | None = None,
    verify_ssl: bool = True,
    compute_stats: Callable[[Any, set[str]], tuple[dict[str, Any], set[str]]]
    | None = None,
) -> list[dict[str, Any]]:
    compute_stats = compute_stats or compute_cas_stats
    excluded_types = load_excluded_types()
    archives = _iter_selected_archives(dir_path, selected_projects_data)
    total_cas_overall = 0

    for file_name, _, file_path in archives:
        try:
            with zipfile.ZipFile(file_path, "r") as zip_file:
                project_meta = _load_project_meta(zip_file, file_name)
                if not project_meta:
                    continue

                project_documents = project_meta.get("source_documents", [])
                if not project_documents:
                    continue

                total_cas_overall += _count_archive_cas_files(zip_file, project_documents)
        except Exception as error:
            log.error("Error pre-counting CAS files in %s: %s", file_name, error)

    if progress_callback and total_cas_overall == 0:
        progress_callback(0, 0, None, None)

    projects = []
    processed_cas_overall = 0

    for file_name, project_stem, file_path in archives:
        try:
            with zipfile.ZipFile(file_path, "r") as zip_file:
                project_meta = _load_project_meta(zip_file, file_name)
                if not project_meta:
                    continue

                project_documents = project_meta.get("source_documents", [])
                if not project_documents:
                    log.warning("No source documents found in project %s", file_name)
                    continue

                log.info("Started processing project %s", file_name)
                annotations, used_snomed_ids, processed_cas_overall = (
                    _load_document_annotations(
                        zip_file,
                        file_name,
                        project_stem,
                        project_documents,
                        excluded_types,
                        progress_callback,
                        processed_cas_overall,
                        total_cas_overall,
                        compute_stats,
                    )
                )
                snomed_label_map = _fetch_snomed_labels(
                    mode=mode,
                    api_url=api_url,
                    auth=auth,
                    project_meta=project_meta,
                    selected_projects_data=selected_projects_data,
                    project_stem=project_stem,
                    used_snomed_ids=used_snomed_ids,
                    file_name=file_name,
                    ca_bundle=ca_bundle,
                    verify_ssl=verify_ssl,
                )

                projects.append(
                    {
                        "name": file_name,
                        "tags": _project_tags(project_meta) or None,
                        "documents": project_documents,
                        "annotations": annotations,
                        "snomed_labels": snomed_label_map,
                        "inception_version": project_meta.get(
                            "application_version", "Older than 38.4"
                        ),
                    }
                )

            gc.collect()
        except Exception as error:
            log.error("Error processing %s: %s", file_name, error)

    if progress_callback and total_cas_overall > 0:
        progress_callback(total_cas_overall, total_cas_overall, None, None)

    gc.collect()
    return projects
