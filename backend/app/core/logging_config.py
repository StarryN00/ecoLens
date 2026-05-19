import logging
import sys


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)

    try:
        from pythonjsonlogger import jsonlogger
        handler.setFormatter(
            jsonlogger.JsonFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
    except ImportError:
        # python-json-logger not installed; fall back to plain text
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    # Reduce noise from high-volume access logs in production
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
