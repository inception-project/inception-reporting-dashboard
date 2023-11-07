# inception_reports
This script will generate some plots for your INCEpTION project based on the log data.

Right now we have two main plots:
- ``plot_averages`` will plot the annotation behavior of the annotators in your project.
- ``plot_project_progress`` will plot the progress of your project, and the estimated time remaining to finish. 


## Getting started
Generate some plots for the log data of your INCEpTION projects with the following steps:
- Clone this repo.
- Navigate into the repo.
- ``pip install -e .``
- Copy the exported log data (it's the "event.log" file.)
- ``inception_reports [LOGFILE]``
- tada!