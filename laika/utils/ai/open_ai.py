import openai
from openai import Completion, Embedding  # noqa: F401 imported but unused
from openai.embeddings_utils import get_embedding  # noqa: F401 imported but unused

from laika.settings import OPEN_AI_KEY

openai.api_key = OPEN_AI_KEY
