import logging

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
DIR_PROMPTS = "prompts"

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
