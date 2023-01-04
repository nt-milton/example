import logging

from laika.celery import app as celery_app
from search.indexing.policy_index import policy_search_index
from search.indexing.question_index import question_search_index

logger = logging.getLogger(__name__)


@celery_app.task(name='Search - Cloudsearch Indexing')
def run_cloudsearch_index_task():
    logger.info('Search Indexing pending records - Starting')
    policy_search_index.reconcile()
    question_search_index.reconcile()
    logger.info('Search Indexing pending records - Finished')
