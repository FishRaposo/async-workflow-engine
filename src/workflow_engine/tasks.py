from typing import Dict

from loguru import logger


def parse_text(context: Dict[str, str] = None) -> str:
    logger.info("Task: Parsing input text metadata...")
    return "metadata_parsed"


def classify_with_llm(context: Dict[str, str] = None) -> str:
    logger.info("Task: Querying LLM for category classification...")
    return "category_business"


def send_notification(context: Dict[str, str] = None) -> str:
    logger.info("Task: Sending notification to administrator...")
    return "notification_sent"


TASK_REGISTRY = {
    "parse_text": parse_text,
    "classify_with_llm": classify_with_llm,
    "send_notification": send_notification,
}
