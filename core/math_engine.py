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

def safe_eval(expr):
    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.n

        elif isinstance(node, ast.BinOp):
            return SAFE_OPERATORS[type(node.op)](
                _eval(node.left),
                _eval(node.right)
            )

        elif isinstance(node, ast.UnaryOp):
            return SAFE_OPERATORS[type(node.op)](
                _eval(node.operand)
            )

        raise TypeError(node)

    tree = ast.parse(expr, mode="eval")
    return _eval(tree.body)

# =========================
# 🧠 DETECT MATH QUERY (SAFE)
# =========================
def is_math_query(text: str):
    text = text.lower()

    numbers = re.findall(r'\d+', text)

    math_words = [
        "+", "-", "*", "/",
        "add", "adding",
        "subtract", "subtracting",
        "multiply", "multiplied", "multiplying",
        "divide", "divided", "dividing",
        "times", "plus", "minus"
    ]

    # ✅ SAFE "it" handling (only if math intent present)
    has_it_math = (
        "it" in text
        and last_result is not None
        and any(word in text for word in [
            "add", "subtract", "multiply", "divide",
            "plus", "minus", "times"
        ])
    )

    return (
        any(word in text for word in math_words)
        or len(numbers) >= 2
        or has_it_math
    )


# =========================
# 🧮 MAIN SOLVER
# =========================
def solve_math(text: str):
    global last_result

    text = text.lower().strip()

    try:
        # =========================
        # 🔥 SPECIAL PATTERNS (HIGHEST PRIORITY)
        # =========================

        # multiply X by Y
        match = re.search(r'(multiply|multiplied)\s+(\d+)\s+by\s+(\d+)', text)
        if match:
            a, b = match.groups()[1:]
            result = float(a) * float(b)
            last_result = result
            return int(result) if result.is_integer() else result

        # divide X by Y
        match = re.search(r'(divide|divided)\s+(\d+)\s+by\s+(\d+)', text)
        if match:
            a, b = match.groups()[1:]
            result = float(a) / float(b)
            last_result = result
            return int(result) if result.is_integer() else result

        # =========================
        # 🔁 FOLLOW-UP USING LAST RESULT
        # =========================

        if last_result is not None:

            # add
            if "add" in text or "plus" in text:
                nums = re.findall(r'\d+', text)
                if nums:
                    last_result += float(nums[0])
                    return int(last_result) if last_result.is_integer() else last_result

            # subtract
            if "subtract" in text or "minus" in text:
                nums = re.findall(r'\d+', text)
                if nums:
                    last_result -= float(nums[0])
                    return int(last_result) if last_result.is_integer() else last_result

            # multiply
            if "multiply" in text or "multiplied" in text or "times" in text:
                nums = re.findall(r'\d+', text)
                if nums:
                    last_result *= float(nums[0])
                    return int(last_result) if last_result.is_integer() else last_result

            # divide
            if "divide" in text or "divided" in text:
                nums = re.findall(r'\d+', text)
                if nums:
                    last_result /= float(nums[0])
                    return int(last_result) if last_result.is_integer() else last_result

        # =========================
        # 🧠 NORMALIZE TEXT
        # =========================

        text = text.replace(" x ", " * ")
        text = text.replace("x", "*")

        text = text.replace("plus", "+")
        text = text.replace("minus", "-")
        text = text.replace("times", "*")

        text = text.replace("add", "+")
        text = text.replace("subtract", "-")
        text = text.replace("multiply", "*")
        text = text.replace("multiplied", "*")
        text = text.replace("divide", "/")
        text = text.replace("divided", "/")

        text = text.replace("and", "")
        text = text.replace("by", "")
        text = text.replace("the answer", "")
        text = text.replace("result", "")
        text = text.replace("it", "")

        # =========================
        # 🧠 HANDLE PARTIAL INPUT
        # =========================

        if text.startswith(("+", "-", "*", "/")) and last_result is not None:
            text = str(last_result) + text

        # =========================
        # 🧹 CLEAN INPUT
        # =========================

        text = re.sub(r'[^0-9+\-*/(). ]', '', text)

        if not text.strip():
            return None

        # =========================
        # 🧮 FINAL EVAL
        # =========================

        result = safe_eval(text)

        last_result = result

        return int(result) if result.is_integer() else result

    except Exception:
        return None
