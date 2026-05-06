import logging
from collections.abc import Iterator

import pytest

from daedalus.telemetry.logging import HANDLER_NAME, LOGGER_NAME, configure_logging


@pytest.fixture(autouse=True)
def reset_daedalus_logging_handler() -> Iterator[None]:
    logger = logging.getLogger(LOGGER_NAME)
    _remove_daedalus_handlers(logger)

    yield

    _remove_daedalus_handlers(logger)


def test_configure_logging_can_be_called_more_than_once_safely() -> None:
    logger = logging.getLogger(LOGGER_NAME)

    configure_logging("INFO")
    configure_logging("DEBUG")

    daedalus_handlers = _daedalus_handlers(logger)
    assert len(daedalus_handlers) == 1


def test_configure_logging_accepts_debug_log_level() -> None:
    logger = logging.getLogger(LOGGER_NAME)

    configure_logging("DEBUG")

    daedalus_handlers = _daedalus_handlers(logger)
    assert logger.level == logging.DEBUG
    assert daedalus_handlers[0].level == logging.DEBUG


def test_configure_logging_rejects_invalid_log_level() -> None:
    with pytest.raises(ValueError, match="Invalid log level"):
        configure_logging("NOPE")


def _daedalus_handlers(logger: logging.Logger) -> list[logging.Handler]:
    return [handler for handler in logger.handlers if handler.get_name() == HANDLER_NAME]


def _remove_daedalus_handlers(logger: logging.Logger) -> None:
    for handler in _daedalus_handlers(logger):
        logger.removeHandler(handler)
