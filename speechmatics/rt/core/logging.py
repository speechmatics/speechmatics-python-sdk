import logging
import sys
from typing import Any
from typing import Optional

import structlog
from structlog.types import Processor


def setup_logging(log_level: str = "WARNING") -> None:
    """
    Configure structlog with reasonable defaults.

    :param log_level: Minimum log level to show (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    :type log_level: str
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if sys.stderr.isatty():
        # Development: pretty console output
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True, sort_keys=False)]
    else:
        # Production: JSON logs
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str, request_id: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a structured logger with context.

    :param name: Logger name (typically the module name)
    :type name: str
    :param request_id: Optional request ID to include in all logs
    :type request_id: str, optional
    :return: Configured structlog logger
    :rtype: structlog.BoundLogger
    """
    logger = structlog.get_logger(name)

    if request_id:
        logger = logger.bind(request_id=request_id)

    return logger  # type: ignore[no-any-return]


def bind_context(logger: structlog.BoundLogger, **kwargs: Any) -> structlog.BoundLogger:
    """
    Bind additional context to an existing logger.

    :param logger: The logger to bind context to
    :type logger: structlog.BoundLogger
    :param kwargs: Key-value pairs to add to the log context
    :type kwargs: Any
    :return: Logger with the new context bound
    :rtype: structlog.BoundLogger
    """
    return logger.bind(**kwargs)


setup_logging()
