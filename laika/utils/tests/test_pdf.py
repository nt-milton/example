import io
import pathlib

from laika.utils.pdf import merge


def read_file():
    with open(pathlib.Path(__file__).parent / 'example.pdf', 'rb') as pdf:
        return pdf.read()


def test_merge_same_content():
    pdf_bytes = read_file()

    content = merge(pdf_bytes).read()

    assert len(pdf_bytes) == len(content)


def test_merge_adds_new_content():
    pdf_bytes = read_file()
    pdf_path = str(pathlib.Path(__file__).parent / 'example.pdf')

    content = merge(io.BytesIO(pdf_bytes), pdf_path).read()

    assert len(pdf_bytes) < len(content)
