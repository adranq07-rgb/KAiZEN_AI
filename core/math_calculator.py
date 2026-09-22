import ast
from decimal import Decimal, ROUND_HALF_UP, localcontext


class MathCalculationError(ValueError):
    pass


class DecimalCalculator:
    """Restricted arithmetic evaluator that keeps decimal calculations exact."""

    _operators = {
        ast.Add: lambda left, right: left + right,
        ast.Sub: lambda left, right: left - right,
        ast.Mult: lambda left, right: left * right,
        ast.Div: lambda left, right: left / right,
        ast.Mod: lambda left, right: left % right,
        ast.Pow: lambda left, right: left ** int(right),
    }

    @classmethod
    def calculate(cls, expression, precision=28):
        expression = str(expression).strip().replace(",", ".")
        try:
            tree = ast.parse(expression, mode="eval")
            with localcontext() as context:
                context.prec = precision
                return cls._evaluate(tree.body)
        except (SyntaxError, ArithmeticError, ValueError, TypeError) as exc:
            raise MathCalculationError(f"Geçersiz hesaplama: {exc}") from exc

    @classmethod
    def _evaluate(cls, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Decimal(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = cls._evaluate(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in cls._operators:
            left = cls._evaluate(node.left)
            right = cls._evaluate(node.right)
            if isinstance(node.op, ast.Pow):
                if right != right.to_integral_value() or abs(right) > 1000:
                    raise MathCalculationError("Üs tam sayı ve güvenli aralıkta olmalı")
            return cls._operators[type(node.op)](left, right)
        raise MathCalculationError("Yalnızca sayılar ve temel aritmetik işlemler kullanılabilir")

    @staticmethod
    def percentage(amount, rate):
        return Decimal(str(amount)) * Decimal(str(rate)) / Decimal("100")

    @staticmethod
    def money(value, places="0.01"):
        return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)
