import logging
import nest_asyncio

def setup_logging(log_file='agent_program.log', level=logging.DEBUG):
    nest_asyncio.apply()
    logging.basicConfig(
        filename=log_file,
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
