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
import shutil
import warnings
import zipfile

import cassis
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from matplotlib import gridspec
from pycaprio import Pycaprio
from datetime import datetime
import time

# suppress deprecation warnings related to the use of the pyplot
# can be solved by sending the fig instead of the plt to streamlit
st.set_option("deprecation.showPyplotGlobalUse", False)
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
    project_name = project["name"].strip(".zip")
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

    project_data = {
        "project_name": project_name,
        "project_tags": project_tags,
        "doc_categories": doc_categories,
    }

    type_counts = get_type_counts(project_annotations)

    selected_annotation_types = st.multiselect(
        f"Which annotation types would you like to see for {project_name}?",
        list(type_counts.keys()),
        list(type_counts.keys()),
    )
    type_counts = {
        k: v for k, v in type_counts.items() if k in selected_annotation_types
    }

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
    ax1.set_title("Documents Status")

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
    ax2.set_title("Types of Annotations")
    ax2.barh(
        [f"{type} = {value}" for type, value in type_counts.items()],
        list(type_counts.values()),
        color=colors,
    )
    ax2.set_xlabel("Number of Annotations")

    fig.suptitle(
        f'{project_name.split(".")[0]}\nTotal Annotations: {total_annotations}',
        fontsize=16,
    )
    fig.tight_layout()
    st.pyplot()

    export_data(project_data)


def find_element_by_name(element_list, name):
    """
    Finds an element in the given element list by its name.

    Args:
        element_list (list): A list of elements to search through.
        name (str): The name of the element to find.

    Returns:
        str: The UI name of the found element, or the last part of the name if not found.
    """
    for element in element_list:
        if element.name == name:
            return element.uiName
    return name.split(".")[-1]


def get_type_counts(annotations):
    """
    Calculate the count of each type in the given annotations. Each annotation is a CAS object.

    Args:
        annotations (dict): A dictionary containing the annotations.

    Returns:
        dict: A dictionary containing the count of each type.
    """
    count_dict = {}

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
            if type_name not in count_dict:
                count_dict[type_name] = 0
            count_dict[type_name] += count
    count_dict = {k: v for k, v in count_dict.items() if v > 0}
    count_dict = dict(sorted(count_dict.items(), key=lambda item: item[1]))

    return count_dict


def translate_tag(tag):
    """
    Translate the given tag to a human-readable format.
    """

    specialites = {
        "0100": "Innere Medizin",
        "0200": "Geriatrie",
        "0300": "Kardiologie",
        "0400": "Nephrologie",
        "0500": "Hämatologie und internistische Onkologie",
        "0600": "Endokrinologie",
        "0700": "Gastroenterologie",
        "0800": "Pneumologie",
        "0900": "Rheumatologie",
        "1000": "Pädiatrie",
        "1100": "Kinderkardiologie",
        "1200": "Neonatologie",
        "1300": "Kinderchirurgie",
        "1400": "Lungen- und Bronchialheilkunde",
        "1500": "Allgemeine Chirurgie",
        "1600": "Unfallchirurgie",
        "1700": "Neurochirurgie",
        "1800": "Gefäßchirurgie",
        "1900": "Plastische Chirurgie",
        "2000": "Thoraxchirurgie",
        "2100": "Herzchirurgie",
        "2200": "Urologie",
        "2300": "Orthopädie",
        "2316": "Orthopädie und Unfallchirurgie",
        "2400": "Frauenheilkunde und Geburtshilfe",
        "2425": "Frauenheilkunde",
        "2500": "Geburtshilfe",
        "2600": "Hals-, Nasen-, Ohrenheilkunde",
        "2700": "Augenheilkunde",
        "2800": "Neurologie",
        "2900": "Allgemeine Psychiatrie",
        "3000": "Kinder- und Jugendpsychiatrie",
        "3100": "Psychosomatik/Psychotherapie",
        "3200": "Nuklearmedizin",
        "3300": "Strahlenheilkunde",
        "3400": "Dermatologie",
        "3500": "Zahn- und Kieferheilkunde, Mund- und Kieferchirurgie",
        "3600": "Intensivmedizin",
        "3700": "Sonstige Fachabteilung",
    }

    document_types = {
        "AD010101": "Ärztliche Stellungnahme",
        "AD010102": "Durchgangsarztbericht",
        "AD010103": "Entlassungsbericht intern",
        "AD010104": "Entlassungsbericht extern",
        "AD010105": "Reha-Bericht",
        "AD010106": "Verlegungsbericht intern",
        "AD010107": "Verlegungsbericht extern",
        "AD010108": "Vorläufiger Arztbericht",
        "AD010109": "Ärztlicher Befundbericht",
        "AD010110": "Ärztlicher Verlaufsbericht",
        "AD010111": "Ambulanzbrief",
        "AD010112": "Kurzarztbrief",
        "AD010113": "Nachschaubericht",
        "AD010114": "Interventionsbericht",
        "AD010199": "Sonstiger Arztbericht",
        "AD020101": "Arbeitsunfähigkeitsbescheinigung",
        "AD020102": "Beurlaubung",
        "AD020103": "Todesbescheinigung",
        "AD020104": "Ärztliche Bescheinigung",
        "AD020105": "Notfall-/Vertretungsschein",
        "AD020106": "Wiedereingliederungsplan",
        "AD020107": "Aufenthaltsbescheinigung",
        "AD020108": "Geburtsanzeige",
        "AD020199": "Sonstige Bescheinigung",
        "AD020201": "Anatomische Skizze",
        "AD020202": "Befundbogen",
        "AD020203": "Bericht Gesundheitsuntersuchung",
        "AD020204": "Krebsfrüherkennung",
        "AD020205": "Messblatt",
        "AD020206": "Belastungserprobung",
        "AD020207": "Ärztlicher Fragebogen",
        "AD020208": "Befund extern",
        "AD020299": "Sonstige ärztliche Befunderhebung",
        "AD060101": "Konsilanforderung",
        "AD060102": "Konsilanmeldung",
        "AD060103": "Konsilbericht intern",
        "AD060104": "Konsilbericht extern",
        "AD060105": "Visitenprotokoll",
        "AD060106": "Tumorkonferenzprotokoll",
        "AD060107": "Teambesprechungsprotokoll",
        "AD060108": "Anordnung/Verordnung",
        "AD060109": "Verordnung",
        "AD060199": "Sonstige Fallbesprechung",
        "AM010101": "Übersicht abrechnungsrelevanter Diagnosen / Prozeduren",
        "AM010102": "G-AEP Kriterien",
        "AM010103": "Kostenübernahmeverlängerung",
        "AM010104": "Schriftverkehr MD Kasse",
        "AM010105": "Abrechnungsschein",
        "AM010106": "Rechnung ambulante/stationäre Behandlung",
        "AM010107": "MD Prüfauftrag",
        "AM010108": "MD Gutachten",
        "AM010109": "Begründete Unterlagen Leistungskodierung",
        "AM010199": "Sonstige Abrechnungsdokumentation",
        "AM010201": "Antrag auf Rehabilitation",
        "AM010202": "Antrag auf Betreuung",
        "AM010203": "Antrag auf gesetzliche Unterbringung",
        "AM010204": "Verlängerungsantrag",
        "AM010205": "Antrag auf Psychotherapie",
        "AM010206": "Antrag auf Pflegeeinstufung",
        "AM010207": "Kostenübernahmeantrag",
        "AM010208": "Antrag auf Leistungen der Pflegeversicherung",
        "AM010209": "Antrag auf Kurzzeitpflege",
        "AM010210": "Antrag auf Fixierung/Isolierung beim Amtsgericht",
        "AM010299": "Sonstiger Antrag",
        "AM010301": "Anästhesieaufklärungsbogen",
        "AM010302": "Diagnostischer Aufklärungsbogen",
        "AM010303": "Operationsaufklärungsbogen",
        "AM010304": "Aufklärungsbogen Therapie",
        "AM010399": "Sonstiger Aufklärungsbogen",
        "AM030101": "Aktenlaufzettel",
        "AM030102": "Checkliste Entlassung",
        "AM030103": "Entlassungsplan",
        "AM030104": "Patientenlaufzettel",
        "AM030199": "Sonstige Checkliste Administration",
        "AM050101": "Datenschutzerklärung",
        "AM050102": "Einverständniserklärung",
        "AM050103": "Erklärung Nichtansprechbarkeit Patienten",
        "AM050104": "Einverständniserklärung Abrechnung",
        "AM050105": "Einverständniserklärung Behandlung",
        "AM050106": "Einwilligung und Datenschutzerklärung Entlassungsmanagement",
        "AM050107": "Schweigepflichtentbindung",
        "AM050108": "Entlassung gegen ärztlichen Rat",
        "AM050109": "Aufforderung zur Herausgabe der medizinischen Dokumentation",
        "AM050110": "Aufforderung zur Löschung der medizinischen Dokumentation",
        "AM050111": "Aufforderung zur Berichtigung der medizinischen Dokumentation",
        "AM050199": "Sonstige Einwilligung/Erklärung",
        "AM160101": "Blutgruppenausweis",
        "AM160102": "Impfausweis",
        "AM160103": "Vorsorgevollmacht",
        "AM160104": "Patientenverfügung",
        "AM160105": "Wertgegenständeverwaltung",
        "AM160106": "Allergiepass",
        "AM160107": "Herzschrittmacherausweis",
        "AM160108": "Nachlassprotokoll",
        "AM160109": "Mutterpass (Kopie)",
        "AM160110": "Ausweiskopie",
        "AM160111": "Implantat-Ausweis",
        "AM160112": "Betreuerausweis",
        "AM160113": "Patientenbild",
        "AM160199": "Sonstiges patienteneigenes Dokument",
        "AM160201": "Belehrung",
        "AM160202": "Informationsblatt",
        "AM160203": "Informationsblatt Entlassungsmanagement",
        "AM160299": "Sonstiges Patienteninformationsblatt",
        "AM160301": "Heil- / Hilfsmittelverordnung",
        "AM160302": "Krankentransportschein",
        "AM160303": "Verordnung häusliche Krankenpflege",
        "AM160399": "Sonstige poststationäre Verordnung",
        "AM170101": "Dokumentationsbogen Meldepflicht",
        "AM170102": "Hygienestandard",
        "AM170103": "Patientenfragebogen",
        "AM170104": "Pflegestandard",
        "AM170105": "Qualitätssicherungsbogen",
        "AM170199": "Sonstiges Qualitätssicherungsdokument",
        "AM190101": "Anforderung Unterlagen",
        "AM190102": "Schriftverkehr Amtsgericht",
        "AM190103": "Schriftverkehr MD Arzt",
        "AM190104": "Schriftverkehr Krankenkasse",
        "AM190105": "Schriftverkehr Deutsche Rentenversicherung",
        "AM190106": "Sendebericht",
        "AM190107": "Empfangsbestätigung",
        "AM190108": "Handschriftliche Notiz",
        "AM190109": "Lieferschein",
        "AM190110": "Schriftverkehr Amt/Gericht/Anwalt",
        "AM190111": "Schriftverkehr Strafverfolgung und Schadensersatz",
        "AM190112": "Anforderung Unterlagen MD",
        "AM190113": "Widerspruchsbegründung",
        "AM190114": "Schriftverkehr Unfallversicherungsträger und Leistungserbringer",
        "AM190199": "Sonstiger Schriftverkehr",
        "AM190201": "Beratungsbogen Sozialer Dienst",
        "AM190202": "Soziotherapeutischer Betreuungsplan",
        "AM190203": "Einschätzung Sozialdienst",
        "AM190204": "Abschlussbericht Sozialdienst",
        "AM190299": "Sonstiges Dokument Sozialdienst",
        "AM220101": "Behandlungsvertrag",
        "AM220102": "Wahlleistungsvertrag",
        "AM220103": "Heimvertrag",
        "AM220104": "Angaben zur Vergütung von Mitarbeitenden",
        "AM220199": "Sonstiger Vertrag",
        "AU010101": "Anamnesebogen",
        "AU010102": "Anmeldung Aufnahme",
        "AU010103": "Aufnahmebogen",
        "AU010104": "Checkliste Aufnahme",
        "AU010105": "Stammblatt",
        "AU010199": "Sonstige Aufnahmedokumentation",
        "AU050101": "Verordnung von Krankenhausbehandlung",
        "AU050102": "Überweisungsschein",
        "AU050103": "Überweisungsschein Entlassung",
        "AU050104": "Verlegungsschein Intern",
        "AU050199": "Sonstiges Einweisungs-/Überweisungsdokument",
        "AU190101": "Einsatzprotokoll",
        "AU190102": "Notaufnahmebericht",
        "AU190103": "Notaufnahmebogen",
        "AU190104": "Notfalldatensatz",
        "AU190105": "ISAR Screening",
        "AU190199": "Sonstige Dokumentation Rettungsstelle",
        "DG020101": "Anforderung bildgebende Diagnostik",
        "DG020102": "Angiographiebefund",
        "DG020103": "CT-Befund",
        "DG020104": "Echokardiographiebefund",
        "DG020105": "Endoskopiebefund",
        "DG020106": "Herzkatheterprotokoll",
        "DG020107": "MRT-Befund",
        "DG020108": "OCT-Befund",
        "DG020109": "PET-Befund",
        "DG020110": "Röntgenbefund",
        "DG020111": "Sonographiebefund",
        "DG020112": "SPECT-Befund",
        "DG020113": "Szintigraphiebefund",
        "DG020114": "Mammographiebefund",
        "DG020115": "Checkliste bildgebende Diagnostik",
        "DG020199": "Sonstige Dokumentation bildgebende Diagnostik",
        "DG060101": "Anforderung Funktionsdiagnostik",
        "DG060102": "Audiometriebefund",
        "DG060103": "Befund evozierter Potentiale",
        "DG060104": "Blutdruckprotokoll",
        "DG060105": "CTG-Ausdruck",
        "DG060106": "Dokumentationsbogen Feststellung Hirntod",
        "DG060107": "Dokumentationsbogen Herzschrittmacherkontrolle",
        "DG060108": "Dokumentationsbogen Lungenfunktionsprüfung",
        "DG060109": "EEG-Auswertung",
        "DG060110": "EMG-Befund",
        "DG060111": "EKG-Auswertung",
        "DG060112": "Manometriebefund",
        "DG060113": "Messungsprotokoll Augeninnendruck",
        "DG060114": "Neurographiebefund",
        "DG060115": "Rhinometriebefund",
        "DG060116": "Schlaflabordokumentationsbogen",
        "DG060117": "Schluckuntersuchung",
        "DG060118": "Checkliste Funktionsdiagnostik",
        "DG060119": "Ergometriebefund",
        "DG060120": "Kipptischuntersuchung",
        "DG060121": "Augenuntersuchung",
        "DG060122": "Dokumentationsbogen ICD Kontrolle",
        "DG060123": "Zystometrie",
        "DG060124": "Uroflowmetrie",
        "DG060199": "Sonstige Dokumentation Funktionsdiagnostik",
        "DG060201": "Schellong Test",
        "DG060202": "H2 Atemtest",
        "DG060203": "Allergietest",
        "DG060204": "Zahlenverbindungstest",
        "DG060205": "6-Minuten-Gehtest",
        "DG060209": "Sonstige Funktionstests",
        "DG060299": "Sonstiger Funktionstest",
        "ED010199": "Sonstige Audiodokumentation",
        "ED020101": "Fotodokumentation Operation",
        "ED020102": "Fotodokumentation Dermatologie",
        "ED020103": "Fotodokumentation Diagnostik",
        "ED020104": "Videodokumentation Operation",
        "ED020199": "Foto-/Videodokumentation Sonstige",
        "ED110101": "Behandlungspfad",
        "ED110102": "Notfalldatenmanagement (NFDM)",
        "ED110103": "Medikationsplan elektronisch (eMP)",
        "ED110104": "eArztbrief",
        "ED110105": "eImpfpass",
        "ED110106": "eZahnärztliches Bonusheft",
        "ED110107": "eArbeitsunfähigkeitsbescheinigung",
        "ED110108": "eRezept",
        "ED110109": "Pflegebericht",
        "ED110110": "eDMP",
        "ED110111": "eMutterpass",
        "ED110112": "KH-Entlassbrief",
        "ED110113": "U-Heft Untersuchungen",
        "ED110114": "U-Heft Teilnahmekarte",
        "ED110115": "U-Heft Elternnotiz",
        "ED110116": "Überleitungsbogen",
        "ED110199": "Sonstige Dokumentation KIS",
        "ED190101": "E-Mail Befundauskunft",
        "ED190102": "E-Mail Juristische Beweissicherung",
        "ED190103": "E-Mail Arztauskunft",
        "ED190104": "E-Mail Sonstige",
        "ED190105": "Fax Befundauskunft",
        "ED190106": "Fax Juristische Beweissicherung",
        "ED190107": "Fax Arztauskunft",
        "ED190108": "Fax Sonstige",
        "ED190199": "Sonstiger elektronischer Schriftverkehr",
        "LB020101": "Blutgasanalyse",
        "LB020102": "Blutkulturenbefund",
        "LB020103": "Herstellungs- und Prüfprotokoll von Blut und Blutprodukten",
        "LB020104": "Serologischer Befund",
        "LB020199": "Sonstige Dokumentation Blut",
        "LB120101": "Glukosetoleranztestprotokoll",
        "LB120102": "Laborbefund extern",
        "LB120103": "Laborbefund intern",
        "LB120104": "Anforderung Labor",
        "LB120105": "Überweisungsschein Labor",
        "LB120199": "Sonstiger Laborbefund",
        "LB130101": "Mikrobiologiebefund",
        "LB130102": "Urinbefund",
        "LB220101": "Befund über positive Infektionsmarker",
        "LB220102": "Virologiebefund",
        "OP010101": "Anästhesieprotokoll intraoperativ",
        "OP010102": "Aufwachraumprotokoll",
        "OP010103": "Checkliste Anästhesie",
        "OP010199": "Sonstige Anästhesiedokumentation",
        "OP150101": "Chargendokumentation",
        "OP150102": "OP-Anmeldungsbogen",
        "OP150103": "OP-Bericht",
        "OP150104": "OP-Bilddokumentation",
        "OP150105": "OP-Checkliste",
        "OP150106": "OP-Protokoll",
        "OP150107": "Postoperative Verordnung",
        "OP150108": "OP-Zählprotokoll",
        "OP150109": "Dokumentation ambulantes Operieren",
        "OP150199": "Sonstige OP-Dokumentation",
        "OP200101": "Transplantationsprotokoll",
        "OP200102": "Spenderdokument",
        "OP200199": "Sonstige Transplantationsdokumentation",
        "PT080101": "Histologieanforderung",
        "PT080102": "Histologiebefund",
        "PT130101": "Molekularpathologieanforderung",
        "PT130102": "Molekularpathologiebefund",
        "PT230199": "Sonstige pathologische Dokumentation",
        "PT260101": "Zytologieanforderung",
        "PT260102": "Zytologiebefund",
        "SD070101": "Geburtenbericht",
        "SD070102": "Geburtenprotokoll",
        "SD070103": "Geburtenverlaufskurve",
        "SD070104": "Neugeborenenscreening",
        "SD070105": "Partogramm",
        "SD070106": "Wiegekarte",
        "SD070107": "Neugeborenendokumentationsbogen",
        "SD070108": "Säuglingskurve",
        "SD070109": "Geburtenbogen",
        "SD070110": "Perzentilkurve",
        "SD070111": "Entnahme Nabelschnurblut",
        "SD070112": "Datenblatt für den Pädiater",
        "SD070199": "Sonstige Geburtendokumentation",
        "SD070201": "Barthel Index",
        "SD070202": "Dem Tect",
        "SD070203": "ISAR Screening",
        "SD070204": "Sturzrisikoerfassungsbogen",
        "SD070205": "Geriatrische Depressionsskala",
        "SD070206": "Geriatrische Assessmentdokumentation",
        "SD070207": "Mobilitätstest nach Tinetti",
        "SD070208": "Timed Up and Go Test",
        "SD070299": "Sonstiges geriatrisches Dokument",
        "SD110101": "Geriatrische Komplexbehandlungsdokumentation",
        "SD110102": "Intensivmedizinische Komplexbehandlungsdokumentation",
        "SD110103": "MRE/Nicht-MRE Komplexbehandlung",
        "SD110104": "Neurologische Komplexbehandlungsdokumentation",
        "SD110105": "Palliativmedizinische Komplexbehandlungsdokumentation",
        "SD110106": "PKMS-Dokumentation",
        "SD110107": "Dokumentation COVID",
        "SD110199": "Sonstige Komplexbehandlungsdokumentation",
        "SD130101": "Vertrag Maßregelvollzug",
        "SD130102": "Antrag Maßregelvollzug",
        "SD130103": "Schriftverkehr Maßregelvollzug",
        "SD130104": "Einwilligung/Einverständniserklärung Maßregelvollzug",
        "SD130199": "Sonstiges Maßregelvollzugdokument",
        "SD150101": "Follow up-Bogen",
        "SD150102": "Meldebogen Krebsregister",
        "SD150103": "Tumorkonferenzprotokoll",
        "SD150104": "Tumorlokalisationsbogen",
        "SD150199": "Sonstiger onkologischer Dokumentationsbogen",
        "SD160101": "Patientenaufzeichnungen",
        "SD160102": "Testpsychologische Diagnostik",
        "SD160103": "Psychiatrisch-psychotherapeutische Therapieanordnung",
        "SD160104": "Psychiatrisch-psychotherapeutische Therapiedokumentation",
        "SD160105": "Psychiatrisch-psychotherapeutischer Verlaufsbogen",
        "SD160106": "Spezialtherapeutische Verlaufsdokumentation",
        "SD160107": "Therapieeinheiten Ärzte/Psychologen/Spezialtherapeuten",
        "SD160108": "1:1 Betreuung/Einzelbetreuung/Psychiatrische Intensivbehandlung",
        "SD160109": "Checkliste für die Unterbringung psychisch Kranker",
        "SD160110": "Dokumentation Verhaltensanalyse",
        "SD160111": "Dokumentation Depression",
        "SD160112": "Dokumentation Stationsäquivalente Behandlung (StäB)",
        "SD160199": "Sonstiges psychiatrisch-psychotherapeutisches Dokument",
        "SF060101": "Forschungsbericht",
        "SF060199": "Sonstige Forschungsdokumentation",
        "SF190101": "CRF-Bogen",
        "SF190102": "Einwilligung Studie",
        "SF190103": "Protokoll Ein- und Ausschlusskriterien",
        "SF190104": "Prüfplan",
        "SF190105": "SOP-Bogen",
        "SF190106": "Studienbericht",
        "SF190199": "Sonstige Studiendokumentation",
        "TH020101": "Bestrahlungsplan",
        "TH020102": "Bestrahlungsprotokoll",
        "TH020103": "Bestrahlungsverordnung",
        "TH020104": "Radiojodtherapieprotokoll",
        "TH020105": "Therapieprotokoll mit Radionukliden",
        "TH020199": "Sonstiges Bestrahlungstherapieprotokoll",
        "TH060101": "Ergotherapieprotokoll",
        "TH060102": "Logopädieprotokoll",
        "TH060103": "Physiotherapieprotokoll",
        "TH060104": "Anforderung Funktionstherapie",
        "TH060105": "Elektrokonvulsionstherapie",
        "TH060106": "Transkranielle Magnetstimulation",
        "TH060199": "Sonstiges Funktionstherapieprotokoll",
        "TH130101": "Anforderung Medikation",
        "TH130102": "Apothekenbuch",
        "TH130103": "Chemotherapieprotokoll",
        "TH130104": "Hormontherapieprotokoll",
        "TH130105": "Medikamentenplan extern",
        "TH130106": "Medikamentenplan intern/extern (mit BTM)",
        "TH130107": "Medikamentenplan intern/extern",
        "TH130108": "Rezept",
        "TH130109": "Schmerztherapieprotokoll",
        "TH130110": "Prämedikationsprotokoll",
        "TH130111": "Lyse Dokument",
        "TH130199": "Sonstiges Dokument medikamentöser Therapie",
        "TH160101": "Protokoll Ernährungsberatung",
        "TH160199": "Sonstiges Protokoll Patientenschulung",
        "TH200101": "Anforderung Blutkonserven",
        "TH200102": "Blutspendeprotokoll",
        "TH200103": "Bluttransfusionsprotokoll",
        "TH200104": "Konservenbegleitschein",
        "TH200199": "Sonstiges Transfusionsdokument",
        "TH230199": "Sonstige Therapiedokumentation",
        "VL010101": "Dekubitusrisikoeinschätzung",
        "VL010102": "Mini Mental Status Test inkl. Uhrentest",
        "VL010103": "Schmerzerhebungsbogen",
        "VL010104": "Ernährungsscreening",
        "VL010105": "Aphasiescreening",
        "VL010106": "Glasgow Coma Scale",
        "VL010107": "NIH Stroke Scale",
        "VL010108": "IPSS (Internationaler Prostata Symptom Score)",
        "VL010199": "Sonstiger Assessmentbogen",
        "VL040101": "Diabetiker Kurve",
        "VL040102": "Insulinplan",
        "VL040199": "Sonstige Diabetesdokumentation",
        "VL040201": "Dialyseanforderung",
        "VL040202": "Dialyseprotokoll",
        "VL040299": "Sonstige Dialysedokumentation",
        "VL040301": "Ein- und Ausfuhrprotokoll",
        "VL040302": "Fixierungsprotokoll",
        "VL040303": "Isolierungsprotokoll",
        "VL040304": "Lagerungsplan",
        "VL040305": "Punktionsprotokoll",
        "VL040306": "Punktionsprotokoll therapeutisch",
        "VL040307": "Reanimationsprotokoll",
        "VL040308": "Sondenplan",
        "VL040309": "Behandlungsplan",
        "VL040310": "Infektionsdokumentationsbogen",
        "VL040311": "Nosokomialdokumentation",
        "VL040312": "Stomadokumentation",
        "VL040313": "Katheterdokument",
        "VL040314": "Kardioversion",
        "VL040399": "Sonstiger Durchführungsnachweis",
        "VL090101": "Beatmungsprotokoll",
        "VL090102": "Intensivkurve",
        "VL090103": "Intensivpflegebericht",
        "VL090104": "Monitoringausdruck",
        "VL090105": "Intensivdokumentationsbogen",
        "VL090199": "Sonstiger Intensivdokumentationsbogen",
        "VL160101": "Auszug aus den medizinischen Daten",
        "VL160102": "Ernährungsplan",
        "VL160103": "Meldebogen Krebsregister",
        "VL160104": "Pflegeanamnesebogen",
        "VL160105": "Pflegebericht",
        "VL160106": "Pflegekurve",
        "VL160107": "Pflegeplanung",
        "VL160108": "Pflegeüberleitungsbogen",
        "VL160109": "Sturzprotokoll",
        "VL160110": "Überwachungsprotokoll",
        "VL160111": "Verlaufsdokumentationsbogen",
        "VL160112": "Pflegevisite",
        "VL160113": "Fallbesprechung Bezugspflegekraft",
        "VL160114": "Pflegenachweis",
        "VL160115": "Fotodokumentation Dekubitus",
        "VL160199": "Sonstiger Pflegedokumentationsbogen",
        "VL230101": "Wunddokumentationsbogen",
        "VL230102": "Bewegungs- und Lagerungsplan",
        "VL230103": "Fotodokumentation Wunden",
        "VL230199": "Sonstige Wunddokumentation",
        "UB999996": "Nachweise (Zusatz-) Entgelte",
        "UB999997": "Gesamtdokumentation stationäre Versorgung",
        "UB999998": "Gesamtdokumentation ambulante Versorgung",
        "UB999999": "Sonstige medizinische Dokumentation",
    }
    
    if tag in specialites:
        return specialites[tag]
    elif tag in document_types:
        return document_types[tag]
    else:
        return tag

def read_dir(dir_path: str) -> list[dict]:
    """
    Reads a directory containing zip files, extracts the contents, and retrieves project metadata and annotations.

    Args:
        dir_path (str): The path to the directory containing the zip files.

    Returns:
        list[dict]: A list of dictionaries, where each dictionary represents a project and contains the following keys:
            - "name": The name of the zip file.
            - "tags": A list of tags extracted from the project metadata.
            - "documents": A list of source documents from the project metadata.
            - "annotations": A dictionary mapping annotation subfolder names to their corresponding CAS objects.
    """
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
                            translate_tag(word.strip("#"))
                            for word in project_meta["description"].split()
                            if word.startswith("#")
                        ]
                        project_documents = project_meta["source_documents"]

                annotations = {}
                # Find annotation folders
                annotation_folders = [
                    name
                    for name in zip_file.namelist()
                    if name.startswith("annotation/")
                    and name.endswith(".json")
                    and not name.endswith("INITIAL_CAS.json")
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

                # Clean up extracted files
                shutil.rmtree(zip_path)

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
        st.sidebar.success("Login successful ✅")
        button = False
        return True, inception_client
    return False, None


def set_sidebar_state(value):
    if st.session_state.sidebar_state == value:
        st.session_state.flag = value
        st.session_state.sidebar_state = (
            "expanded" if value == "collapsed" else "collapsed"
        )
    else:
        st.session_state.sidebar_state = value
    st.rerun()


def select_method_to_import_data():
    """
    Allows the user to select a method to import data for generating reports.
    """

    method = st.sidebar.radio(
        "Choose your method to import data:", ("Manually", "API"), index=0
    )

    if method == "Manually":
        st.sidebar.write(
            "Please input the path to the folder containing the INCEpTION projects."
        )
        projects_folder = st.sidebar.text_input(
            "Projects Folder:", value="data/dresden_projects/"
        )
        button = st.sidebar.button("Generate Reports")
        if button:
            st.session_state["initialized"] = True
            st.session_state["method"] = "Manually"
            st.session_state["projects"] = read_dir(projects_folder)
            button = False
            set_sidebar_state("collapsed")
    elif method == "API":
        api_url = st.sidebar.text_input("Enter API URL:", "")
        username = st.sidebar.text_input("Username:", "")
        password = st.sidebar.text_input("Password:", type="password", value="")
        inception_status, inception_client = login_to_inception(
            api_url, username, password
        )
        if inception_status:
            inception_projects = inception_client.api.projects()
            st.sidebar.write("Following projects got imported:")
            for inception_project in inception_projects:
                st.sidebar.write(inception_project.project_name)
                project_export = inception_client.api.export_project(
                    inception_project, "jsoncas"
                )
                with open(
                    f"{os.path.expanduser('~')}/.inception_reports/projects/{inception_project}.zip",
                    "wb",
                ) as f:
                    f.write(project_export)
            st.session_state["initialized"] = True
            st.session_state["method"] = "API"
            st.session_state["projects"] = read_dir(projects_folder)
            set_sidebar_state("collapsed")


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


def export_data(project_data, output_directory=None):
    """
    Export project data to a JSON file, and store it in a directory named after the project and the current date.

    Parameters:
        project_data (dict): The data to be exported.
    """
    current_date = datetime.now().strftime("%Y_%m_%d")
    directory_name = f"exported_data_{current_date}"

    if output_directory is None:
        output_directory = os.path.join(os.getcwd(), directory_name)
    else:
        output_directory = os.path.join(output_directory, directory_name)

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    project_name = project_data["project_name"]
    with open(
        f"{output_directory}/{project_name.split('.')[0]}_data_{current_date}.json", "w"
    ) as output_file:
        json.dump(project_data, output_file, indent=4)
    st.success(
        f"{project_name.split('.')[0]} documents status exported successfully ✅"
    )


def main():
    create_directory_in_home()

    st.title("INCEpTION Projects Statistics")

    if "initialized" not in st.session_state:
        select_method_to_import_data()

    if "method" in st.session_state and "projects" in st.session_state:
        projects = [copy.deepcopy(project) for project in st.session_state["projects"]]
        for project in projects:
            plot_project_progress(project)


if __name__ == "__main__":
    main()
