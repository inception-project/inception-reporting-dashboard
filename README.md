# INCEpTION Reporting Dashboard

This package will generate plots to track the progress of your INCEpTION project(s).

In its current state, it can be used by the project manager on site to visualize different metrics regarding the progress of the project, and the type of annotations done.

In case the project is part of a bigger project, the project progress can be exported to be sent to a project lead in a centralized location who, in turn, can use the package to get an overview of the progress across the different projects and locations.

## Getting started

1. Ensure you have python 3.11 or higher (check it using python --version)
2. Install the package using ``pip install -U inception-reports``
3. Run the script using ``inception_reports --help`` this will show you the options you have:
    1. Run it with ``inception_reports --manager`` if you have one python project, or are responsible for one location.
    2. Run it with ``inception_reports --lead`` if you're leading multiple projects, or multiple locations.
4. Regardless of the mode you run the package with, it should open a browser window. Follow the instructions on the page to proceed.

## Issues

This package is under early development, if you notice any bugs, or face any issues, do not hesitate to open a [Github issue](https://github.com/inception-project/inception-reporting-dashboard/issues).
