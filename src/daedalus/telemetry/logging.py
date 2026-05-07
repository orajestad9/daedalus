import logging


LOGGER_NAME = "daedalus"
HANDLER_NAME = "daedalus-console"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(log_level: str = "INFO") -> None:
    """Configure standard-library logging for Daedalus."""
    level = _parse_log_level(log_level)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
    handler = _get_or_create_handler(logger)
    handler.setLevel(level)
    handler.setFormatter(formatter)


def _parse_log_level(log_level: str) -> int:
    level = logging.getLevelName(log_level.upper())
    if not isinstance(level, int):
        msg = f"Invalid log level: {log_level}"
        raise ValueError(msg)

    return level


def _get_or_create_handler(logger: logging.Logger) -> logging.Handler:
    for handler in logger.handlers:
        if handler.get_name() == HANDLER_NAME:
            return handler

    handler = logging.StreamHandler()
    handler.set_name(HANDLER_NAME)
    logger.addHandler(handler)
    return handler
