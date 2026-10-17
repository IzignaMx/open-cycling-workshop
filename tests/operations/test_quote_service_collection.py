"""Tiny synthetic collection regressions; execute only inside the reviewed guard."""

import pytest

pytest_plugins = ["pytester"]


@pytest.fixture
def synthetic_pytester(pytester, monkeypatch):
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    pytester.makeini("[pytest]\n")
    return pytester


def test_indirect_module_mark_rejects_even_unselected_pure_test(synthetic_pytester):
    pytester = synthetic_pytester
    pytester.makepyfile(
        test_synthetic='''
import pytest

pytestmark = pytest.mark.parametrize("database", ["sqlite"], indirect=True)

@pytest.fixture
def database(request):
    return request.param

def test_selected(database):
    assert database == "sqlite"

def test_pure():
    assert True
'''
    )
    result = pytester.runpytest_subprocess(
        "test_synthetic.py::test_selected[sqlite]", "--collect-only", "-q", timeout=5
    )
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stdout.fnmatch_lines(["*function uses no fixture 'database'*"])


def test_separated_pure_module_restores_exact_selected_collection(synthetic_pytester):
    pytester = synthetic_pytester
    pytester.makepyfile(
        test_database='''
import pytest

pytestmark = pytest.mark.parametrize("database", ["sqlite"], indirect=True)

@pytest.fixture
def database(request):
    return request.param

def test_selected(database):
    assert database == "sqlite"
''',
        test_pure='''
def test_pure():
    assert True
''',
    )
    result = pytester.runpytest_subprocess(
        "test_database.py::test_selected[sqlite]",
        "test_pure.py::test_pure",
        "--collect-only",
        "-q",
        timeout=5,
    )
    assert result.ret == pytest.ExitCode.OK
    assert "test_database.py::test_selected[sqlite]" in result.stdout.lines
    assert "test_pure.py::test_pure" in result.stdout.lines
    assert "2 tests collected" in result.stdout.str()
