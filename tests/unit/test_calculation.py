import pytest

from app.models.calculation import (
    Calculation,
    Addition,
    Subtraction,
    Multiplication,
    Division
)

def test_addition():
    calculation = Addition(a=10, b=5)
    assert calculation.get_result() == 15

def test_subtraction():
    calculation = Subtraction(a=10, b=5)
    assert calculation.get_result() == 5

def test_multiplication():
    calculation = Multiplication(a=10, b=5)
    assert calculation.get_result() == 50

def test_division():
    calculation = Division(a=10, b=5)
    assert calculation.get_result() == 2

def test_division_by_zero():
    calculation = Division(a=10, b=0)
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        calculation.get_result()

def test_create_addition():
    calculation = Calculation.create(
        calculation_type="add",
        user_id=None,
        a=10,
        b=5
    )
    assert isinstance(calculation, Addition)
    assert calculation.get_result() == 15

@pytest.mark.parametrize(
    "calculation_type, expected_class, expected_result",
    [
        ("add", Addition, 15),
        ("sub", Subtraction, 5),
        ("multiply", Multiplication, 50),
        ("divide", Division, 2),
    ]
)
def test_calculation_factory(
    calculation_type,
    expected_class,
    expected_result
):
    calculation = Calculation.create(
        calculation_type=calculation_type,
        user_id=None,
        a=10,
        b=5
    )
    assert isinstance(calculation, expected_class)
    assert calculation.get_result() == expected_result

def test_invalid_calculation_type():
    with pytest.raises(ValueError, match="Unsupported calculation type"):
        Calculation.create(
            calculation_type="exponent",
            user_id=None,
            a=10,
            b=5
        )
