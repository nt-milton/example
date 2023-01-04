from abc import ABC, abstractmethod

from django.db import transaction

from seeder.seeders.commons import (
    are_columns_empty,
    are_columns_required_empty,
    get_formatted_headers,
)


class Seeder(ABC):
    def __init__(self):
        self._row_error = False
        self._sheet = None

    def seed(self):
        if self._sheet_name not in self._workbook.sheetnames:
            return self._status_detail

        self._sheet = self._workbook[self._sheet_name]

        if self._sheet.cell(row=2, column=1).value is None:
            return self._status_detail

        self._get_rows()
        self._process_related_data()

        for row in self._sheet.iter_rows(min_row=2):
            with transaction.atomic():
                try:
                    self._get_rows_data(row)
                    if self._skip_empty_rows():
                        continue

                    self._validate_required_fields()
                    if self._row_error:
                        self._row_error = False
                        continue

                    self._process_data()
                except Exception as e:
                    self._process_exception(e)

        # This is for controls and vendors, as they do it a bit
        # different with a bulk create after processing each row
        with transaction.atomic():
            self._store_related_data()

        return self._status_detail

    def _get_rows(self):
        # TODO: Replace with method get_headers from commons
        rows = self._sheet.iter_rows(min_row=1, max_row=1)
        first_row = next(rows)
        # get the first row
        headings = [header.value for header in first_row]
        headers = get_formatted_headers(headings)

        self._headers = headers

    def _process_related_data(self):
        pass

    def _get_rows_data(self, row):
        headers_len = len(self._headers)
        self._dictionary = dict(
            zip(self._headers, [entry.value for entry in row[0:headers_len]])
        )
        self._other = [str(a.value).strip() for a in row[4:22] if a.value]

    def _skip_empty_rows(self):
        return are_columns_empty(self._dictionary, self._fields)

    def _validate_required_fields(self):
        if are_columns_required_empty(self._dictionary, self._required_fields):
            self._status_detail.append(self._required_error_msg)
            self._row_error = True

    @abstractmethod
    def _process_data(self):
        pass

    @abstractmethod
    def _process_exception(self, e):
        pass

    def _store_related_data(self):
        pass
