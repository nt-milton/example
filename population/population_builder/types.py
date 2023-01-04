from laika.utils.schema_builder.types.text_field import TextFieldType


class TextFieldLaikaSourceType(TextFieldType):
    def validate(self, value):
        strip_value = value.strip() if value is not None else value
        return super().validate(strip_value if strip_value else None)
