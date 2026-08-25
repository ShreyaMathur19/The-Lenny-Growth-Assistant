import re


def detect_mode(message: str) -> str:
    text = message.lower()
    artifact_terms = [
        r"\bhtml\b", r"\bmarkdown\b", r"artifact", r"dashboard", r"render", r"web page", r"landing page"
    ]
    ship_terms = [r"ship\s*30", r"30 for 30", r"essay", r"long[- ]form"]
    if any(re.search(p, text) for p in artifact_terms):
        return "artifact"
    if any(re.search(p, text) for p in ship_terms):
        return "ship30"
    return "qa"
