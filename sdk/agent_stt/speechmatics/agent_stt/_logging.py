import logging


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger that stays silent unless the application configures logging.

    Args:
        name: Logger name, typically __name__ from the calling module.

    Returns:
        Logger with a NullHandler attached.

    Examples:
        >>> import logging
        >>> logging.getLogger("speechmatics.agent_stt").setLevel(logging.DEBUG)
    """
    logger = logging.getLogger(name)
    logger.addHandler(logging.NullHandler())
    return logger


__all__ = ["get_logger"]
