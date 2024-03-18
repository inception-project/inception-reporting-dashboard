# INCEpTION Reporting Dashboard
This script will generate some plots for your INCEpTION project.
In it current state, it can be used by the project manager on site to visualize different metrics regarding the progress of the project, and the type of annotations done.
In case the project is part of a bigger project, the project progress can be exported to be sent to a project lead in a centralized location.

## Getting started
Generate some plots for your INCEpTION projects with the following steps:
- Export your project in the correct format:
    - In your INCEpTION project go to Settings -> Export -> In Secondary Format choose "UIMA CAS JSON 0.4.0"
    - Download and copy the exported project into a separate folder.
- Make sure you have Python 3.11+
- Clone this repo.
- Navigate into the repo.
- ``pip install .``
- Follow the instructions in ``inception_reports --help``
    - You will need to point to the folder with your exported INCEpTION project.
        - Note: The script needs takes a folder path instead of a project path to account for plotting mutliple projects simultaneously.
    - Next, choose which role you have in the project (go for manager if you don't know what that means.)
- tada!
