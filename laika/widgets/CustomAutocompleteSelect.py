from django.contrib.admin.widgets import AutocompleteSelectMultiple


class CustomAutocompleteSelect(AutocompleteSelectMultiple):
    def __init__(
        self, field, prompt="", admin_site=None, attrs=None, choices=(), using=None
    ):
        self.prompt = prompt
        super().__init__(field, admin_site, attrs=attrs, choices=choices, using=using)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        attrs.update(
            {
                "data-ajax--delay": 250,
                "data-placeholder": self.prompt,
                "style": "width: 100%;",
            }
        )
        return attrs
