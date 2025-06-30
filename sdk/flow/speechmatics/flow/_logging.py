import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger that stays silent by default.

    The logger uses Python's standard logging module and includes NullHandler
    by default to avoid unwanted output. Users can configure logging levels
    and handlers as needed.

    Args:
        name: Logger name, typically __name__ from the calling module.

    Returns:
        Configured logger instance.

    Examples:
        Basic usage in SDK modules:
            logger = get_logger(__name__)
            logger.debug("Connection established (session_id=%s)", session_id)
            logger.info("Recognition started (request_id=%s)", request_id)
            logger.warning("Connection issue: %s", error_message)
            logger.error("Failed to connect: %s", e)

        Enable debug logging in user code:
            import logging
            logging.basicConfig(level=logging.DEBUG)
            # Now all SDK debug messages will be visible

        Custom logging configuration:
            import logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

            # Or for specific components:
            logging.getLogger('speechmatics.rt').setLevel(logging.DEBUG)
    """
    module_logger = logging.getLogger(name)
    module_logger.addHandler(logging.NullHandler())
    return module_logger


__all__ = ["get_logger"]
