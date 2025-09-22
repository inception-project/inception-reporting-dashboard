# INCEpTION Reporting Dashboard

The INCEpTION Reporting Dashboard helps you track and visualize the progress of your INCEpTION project(s). It provides tools for project managers and leads to monitor metrics, analyze annotations, and export progress reports.

## Features

- Visualize project metrics and annotation types.
- Export progress reports for centralized tracking.
- Browser-based interface for ease of use.

## Getting Started

1. **Check Python Version**: Ensure you have Python 3.11 or higher installed. You can verify this by running:

   ```bash
   python --version
   ```

2. **Install the Package**: Install the package using pip:

   ```bash
   pip install -U inception-reports
   ```

3. **Run the Application**:

   - For managing a single project or location, use:

     ```bash
     inception_reports --manager
     ```

   - For tracking the status of multiple projects, use:

     ```bash
     inception_reports --lead
     ```

4. **Follow the Instructions**: The application will open a browser window. Follow the on-screen instructions to proceed.

## Notes on Customization

This package has been developed with [GeMTeX](https://www.medizininformatik-initiative.de/en/gemtex-automated-indexing-medical-texts-research) in mind, and certain configurations, such as `excluded_types.json` in the `inception_reports` home directory, are tailored to its requirements. Users are encouraged to adjust these configurations to suit the specific needs of their projects.

## Issues and Contributions

This package is under active development. If you encounter any bugs or issues, please open a [GitHub issue](https://github.com/inception-project/inception-reporting-dashboard/issues).

We welcome contributions! For details on how to contribute, see our [Contributing Guidelines](CONTRIBUTORS.txt).

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.
