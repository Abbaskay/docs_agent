import datetime
import math


def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    allowed = set("0123456789+-*/().% ")
    if not all(c in allowed for c in expression):
        return "Error: Expression contains disallowed characters."
    try:
        result = eval(expression, {"__builtins__": {}}, {"math": math})
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error evaluating expression: {e}"


def get_current_time() -> str:
    return datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")


def search_web(query: str) -> str:
    return f"Web search is not available in this environment. Query was: '{query}'"
