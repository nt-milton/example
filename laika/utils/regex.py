# Ex: camelCase
REGEX_CAMEL_CASE = '([a-z0-9])([A-Z])'
# Ex: Upper Case
REGEX_UPPER_CASE = '(.)([A-Z][a-z]+)'
URL_DOMAIN_NAME = '(?:http[s]?://)?(?:www\\.+)?([-\\w]+).*'
# Ex: test.png.jpeg => .jpeg
FILE_NAME_EXTENSION = r'\.[^\/.]+$'
NO_WORD = r'/[\W_]+/g'
SPECIAL_CHAR = r'[^\w\s]'
SPECIAL_CHAR_FOR_GLOBAL_SEARCH = '[^0-9a-zA-Z|\\- |\\. |\\_ *]'
ONLY_NUMBERS = '[^A-Za-z0-9]+'
MENTIONED_EMAILS = r'\@\((.*?)\)'
