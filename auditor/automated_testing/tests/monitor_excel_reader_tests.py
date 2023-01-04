import pytest
from django.core.files import File

from auditor.automated_testing.monitor_source import MonitorExcelReader
from laika.utils.exceptions import ServiceException


@pytest.fixture
def exception_monitor_file(exception_monitor_file_path: str):
    return File(open(exception_monitor_file_path, "rb"))


@pytest.fixture
def not_monitor_file(not_monitor_file_path: str):
    return File(open(not_monitor_file_path, "rb"))


@pytest.mark.functional
def test_init_with_incorrect_file(not_monitor_file: File):
    with pytest.raises(ServiceException) as error:
        MonitorExcelReader(not_monitor_file)
        assert str(error) == 'Monitor excel file must be .xlsx'


@pytest.mark.functional
def test_init_with_correct_file(exception_monitor_file: File):
    excel_reader = MonitorExcelReader(exception_monitor_file)
    assert 'MonitorExcelReader' in str(type(excel_reader))
    assert excel_reader._workbook is not None


@pytest.mark.functional
def test_is_sheet_in_workbook(exception_monitor_file: File):
    excel_reader = MonitorExcelReader(exception_monitor_file)
    assert excel_reader._is_sheet_in_workbook('Unfiltered Data') is True


@pytest.mark.functional
def test_count_items_on_sheet(exception_monitor_file: File):
    excel_reader = MonitorExcelReader(exception_monitor_file)
    assert excel_reader.count_items_on_sheet('Unfiltered Data') == 4


@pytest.mark.functional
def test_count_items_on_unexisting_sheet(exception_monitor_file: File):
    excel_reader = MonitorExcelReader(exception_monitor_file)
    assert excel_reader.count_items_on_sheet('Unknown Data') == 0
