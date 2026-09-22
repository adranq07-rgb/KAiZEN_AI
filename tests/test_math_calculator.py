from core.math_calculator import DecimalCalculator, MathCalculationError


def test_math_calculator():
    calculator = DecimalCalculator()
    assert calculator.calculate("0,1 + 0,2") == calculator.calculate("0.3")
    assert calculator.calculate("(12.5 * 8) / 4") == 25
    assert calculator.percentage("1250.40", "20") == calculator.calculate("250.08")
    assert calculator.money("10.125") == calculator.calculate("10.13")

    for unsafe in ("__import__('os')", "open('x')", "2 ** 1.5"):
        try:
            calculator.calculate(unsafe)
        except MathCalculationError:
            pass
        else:
            raise AssertionError(f"Güvensiz ifade kabul edildi: {unsafe}")

    print("KAIZEN MATEMATIK HESAP MOTORU TESTI: BASARILI")
