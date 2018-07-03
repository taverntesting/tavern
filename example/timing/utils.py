import logging
import time

from tavern.util.testutils import inject_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@inject_context
def timer_start(context):
    context['timer_start'] = time.time()


@inject_context
def timer_stop(context):
    start = context.pop('timer_start')
    elapsed = time.time() - start

    logger.info('request took %.3f seconds', elapsed)


@inject_context
def load_number(context):
    context['variables']['input'] = 5
    context['variables']['output'] = 10
