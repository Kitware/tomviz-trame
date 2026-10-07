from loguru import logger

PACKAGE_NAME = "tomviz_web"


def enable_logging():
    logger.enable(PACKAGE_NAME)


def disable_logging():
    logger.disable(PACKAGE_NAME)


disable_logging()

__version__ = "1.1.0"
