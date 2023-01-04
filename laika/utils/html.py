import html
from html.parser import HTMLParser


class CustomHTMLParser(HTMLParser):
    tag_text = ''

    def handle_data(self, data: str) -> None:
        self.tag_text = data

    def add_data_attribute(
        self,
        tag: str,
        source: str,
        data_attr_key: str,
        data_attr_value: str,
        tag_text_allowed: dict,
    ):
        result = ''
        while True:
            start_index = source.find(f'<{tag}')
            if start_index != -1:
                result += source[:start_index]
                end_index = source.find(f'</{tag}')
            else:
                result += source
                break
            html_tag = source[start_index : end_index + 4]
            self.feed(html_tag)
            if tag_text_allowed.get(self.tag_text):
                html_tag_updated = html_tag.replace(
                    f'<{tag}', f'<{tag} data-{data_attr_key}="{data_attr_value}"'
                )
            else:
                html_tag_updated = html_tag
            source = source[end_index + 4 :]
            result += html_tag_updated

        return result


def get_formatted_html(html_text):
    html_text = html_text.replace('\\n', " ")
    html_text = html_text.replace('\\"', '"')
    return html.unescape(html_text)
