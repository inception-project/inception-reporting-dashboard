from unittest.mock import patch

from inception_reports import cli


@patch("inception_reports.cli.streamlit_cli.main", return_value=7)
@patch("inception_reports.cli.setup_logging")
def test_main_launches_manager_dashboard(mock_setup_logging, mock_streamlit_main, monkeypatch):
    monkeypatch.delenv("INCEPTION_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("INCEPTION_CA_BUNDLE", raising=False)
    monkeypatch.delenv("INCEPTION_VERIFY_SSL", raising=False)

    exit_code = cli.main(
        ["--output", "/tmp/reports", "--ca-bundle", "/tmp/ca.pem", "--verify-ssl", "false"]
    )

    mock_setup_logging.assert_called_once_with(None)
    mock_streamlit_main.assert_called_once()
    assert exit_code == 7
    assert cli.sys.argv == ["streamlit", "run", cli.resolve_dashboard_script()]
    assert cli.os.environ["INCEPTION_OUTPUT_DIR"] == "/tmp/reports"
    assert cli.os.environ["INCEPTION_CA_BUNDLE"] == "/tmp/ca.pem"
    assert cli.os.environ["INCEPTION_VERIFY_SSL"] == "false"


def test_apply_environment_overrides_updates_runtime(monkeypatch):
    monkeypatch.delenv("INCEPTION_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("INCEPTION_CA_BUNDLE", raising=False)
    monkeypatch.delenv("INCEPTION_VERIFY_SSL", raising=False)

    args = cli.build_argument_parser().parse_args(
        ["--output", "/tmp/output", "--ca-bundle", "/tmp/ca.pem"]
    )
    cli.apply_environment_overrides(args)

    assert cli.os.environ["INCEPTION_OUTPUT_DIR"] == "/tmp/output"
    assert cli.os.environ["INCEPTION_CA_BUNDLE"] == "/tmp/ca.pem"
    assert cli.os.environ["INCEPTION_VERIFY_SSL"] == "true"
