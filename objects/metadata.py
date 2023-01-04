import re

IS_PROTECTED = 'is_protected'
DEFAULT_VALUE = 'default_value'
SELECT_OPTIONS = 'select_options'


class Metadata:
    def __init__(self, metadata={}):
        if metadata is None:
            metadata = {}
        self.is_protected = bool(metadata.get(IS_PROTECTED))
        self.default_value = metadata.get(DEFAULT_VALUE)
        self.select_options = (
            metadata.get(SELECT_OPTIONS) if metadata.get(SELECT_OPTIONS) else []
        )

    def to_json(self, csv_select_options=False):
        select_options = (
            self.get_csv_select_options() if csv_select_options else self.select_options
        )
        return {
            IS_PROTECTED: self.is_protected,
            DEFAULT_VALUE: self.default_value,
            SELECT_OPTIONS: select_options,
        }

    def get_csv_select_options(self):
        if self.select_options:
            options = ",".join(f'"{item}"' for item in self.select_options)
            return options
        return None

    def set_select_options_from_csv(self, selected_options):
        if not selected_options:
            return
        separator = "\n|\r"
        for reference in selected_options.split(','):
            if reference:
                value = re.sub(separator, ' ', reference).strip()
                if value:
                    self.select_options.append(value)
