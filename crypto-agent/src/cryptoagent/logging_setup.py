import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    # ccxt y httpx son muy verbosos en DEBUG/INFO
    for noisy in ("ccxt", "httpx", "httpx2", "apscheduler.executors"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
