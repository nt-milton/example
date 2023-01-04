import logging
import re
from typing import List

import pandas as pd
from django.core.files.base import ContentFile, File

from policy.models import Policy

from .constants import EMBEDDING_CSV_SIMILARITY_KEY, OPEN_AI_FLAG, SEARCH_ENGINE
from .open_ai import get_embedding

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1_250
POLICY_CHUNKS = 'policy-chunks.csv'
EMBEDDINGS_FILE = 'embeddings.csv'
POLICY_PATH = './policies'


def _clean_content(content: str):
    # Replace multiple new lines with only one.
    content = re.sub("\n+", "\n", content)
    # Replace multiple tabs with only one.
    content = re.sub("\t+", " ", content)
    # Replace trailing spaces with a new line only.
    content = re.sub(" +\n", "\n", content)
    # Replace more than two spaces with empty string.
    content = re.sub(" {2,}", "", content)

    return content


def _convert_content_to_chunks(content: str):
    """
    ~ 255 characters for the question -> ~50 tokens
    ~ 255 characters for the instruction -> ~50 tokens
    ~ 2500 characters for each chunk  -> ~500 tokens
    """
    chunks = []
    chunk = ''
    index = 0
    for letter in content:
        chunk += letter
        if index >= CHUNK_SIZE and (letter == ' ' or letter == '\n'):
            chunks.append(f'{chunk}')
            chunk = ''
            index = 0
        index += 1
    if chunk:
        chunks.append(chunk)
    return chunks


def _generate_policy_data_frame(chunks: List[str]):
    df = pd.DataFrame(
        {
            'Id': range(1, len(chunks) + 1),
            'Text': chunks,
        }
    )
    return df


def _generate_embeddings(content: str):
    chunks = _convert_content_to_chunks(content)
    df = _generate_policy_data_frame(chunks)
    embeddings = []
    for index, chunk in enumerate(chunks):
        embedding = get_embedding(chunk, engine=SEARCH_ENGINE)
        embeddings.append(embedding)
    df[EMBEDDING_CSV_SIMILARITY_KEY] = embeddings
    return df


def generate_policy_embedding(policy: Policy):
    organization = policy.organization
    if not organization.is_flag_active(OPEN_AI_FLAG) or not policy.is_published:
        return

    try:
        cleaned_content = _clean_content(policy.policy_text)
        embedding = _generate_embeddings(cleaned_content)
        published_policy = policy.versions.latest('version')
        if published_policy:
            published_policy.embedding = File(
                name='embedding.csv',
                file=ContentFile(embedding.to_csv().encode('utf-8')),
            )
            published_policy.save()
    except Exception as e:
        logger.error(f'Error trying to generate policy embedding {e}')
