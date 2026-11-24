import datetime
import re
import ast
import operator

last_result = None
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}

def _safe_eval(expr):
    def evaluate(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise TypeError
            return node.value
        if isinstance(node, ast.BinOp):
            operation = SAFE_OPERATORS.get(type(node.op))
            if operation is None:
                raise TypeError
            return operation(evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -evaluate(node.operand)
        raise TypeError
    value = evaluate(ast.parse(expr, mode="eval").body)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError
    return value

def is_math_query(text: str):
    text = text.lower()
    numbers = re.findall(r"\d+", text)
    math_words = ("+", "-", "*", "/", "add", "subtract", "multiply", "divide", "times", "plus", "minus")
    return any(word in text for word in math_words) or len(numbers) >= 2

def solve_math(text: str):
    global last_result
    text = text.lower().strip()
    try:
        match = re.search(r"(multiply|multiplied)\s+(\d+)\s+by\s+(\d+)", text)
        if match:
            result = float(match.group(2)) * float(match.group(3))
        else:
            match = re.search(r"(divide|divided)\s+(\d+)\s+by\s+(\d+)", text)
            if match:
                result = float(match.group(2)) / float(match.group(3))
            else:
                replacements = {
                    " x ": "*", "x": "*", "plus": "+", "minus": "-", "times": "*",
                    "add": "+", "subtract": "-", "multiply": "*", "divide": "/",
                    "and": "", "by": "", "the answer": "", "result": "", "it": "",
                }
                for source, target in replacements.items():
                    text = text.replace(source, target)
                if text.startswith(("+", "-", "*", "/")) and last_result is not None:
                    text = str(last_result) + text
                text = re.sub(r"[^0-9+\-*/(). ]", "", text).strip()
                if not text:
                    return None
                result = _safe_eval(text)
        last_result = result
        return int(result) if isinstance(result, float) and result.is_integer() else result
    except (ArithmeticError, SyntaxError, TypeError, ValueError, ZeroDivisionError, KeyError):
        return None

# =========================
# 🧠 QUICK-ANSWER SKILL ROUTER
#
# Handles fast, deterministic replies that don't need the LLM:
# math, time, date. Desktop/app control (open/close/volume/etc.)
# lives in core/desktop_control.py and is routed directly from
# brain.py instead of being duplicated here.
# =========================


def handle_skills(text: str):
    text = text.lower()

    # 🧮 MATH
    if is_math_query(text):
        result = solve_math(text)
        if result is not None:
            return f"{result}"
        return None

    # ⏰ TIME
    if "time" in text:
        now = datetime.datetime.now().strftime("%I:%M %p")
        return f"It's {now}"

    # 📅 DATE
    if "date" in text or "what day" in text:
        today = datetime.datetime.now().strftime("%A, %d %B %Y")
        return f"Today is {today}"

    return None
