
# tests/test_calculation_integration.py

import pytest

from uuid import uuid4
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from app.models.calculation import (
    Calculation,
    Addition,
    Subtraction,
    Multiplication,
    Division
)

from app.schemas.calculation import (
    CalculationCreate,
    CalculationResponse
)

def test_database_is_postgresql(db_session):
    database_type = db_session.get_bind().dialect.name

    assert database_type == "postgresql", (
        f"Expected PostgreSQL, but connected to {database_type}"
    )

def test_create_addition_calculation(db_session, test_user):

    calculation = Calculation.create(
        calculation_type="add",
        user_id=test_user.id,
        a=10,
        b=5
    )

    db_session.add(calculation)
    db_session.commit()
    db_session.refresh(calculation)

    # Confirm the database generated an ID
    assert calculation.id is not None

    # Confirm calculation fields
    assert calculation.a == 10
    assert calculation.b == 5
    assert calculation.type == "add"

    # Confirm result was calculated and stored
    assert calculation.result == 15

    # Confirm foreign key
    assert calculation.user_id == test_user.id

def test_read_calculation(db_session, test_user):

    calculation = Calculation.create(
        calculation_type="sub",
        user_id=test_user.id,
        a=20,
        b=8
    )

    db_session.add(calculation)
    db_session.commit()

    calculation_id = calculation.id

    # Retrieve calculation from the database
    retrieved = db_session.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()

    assert retrieved is not None
    assert retrieved.id == calculation_id
    assert retrieved.a == 20
    assert retrieved.b == 8
    assert retrieved.type == "sub"
    assert retrieved.result == 12
    assert retrieved.user_id == test_user.id


@pytest.mark.parametrize(
    "calculation_type, expected_class, expected_result",
    [
        ("add", Addition, 15),
        ("sub", Subtraction, 5),
        ("multiply", Multiplication, 50),
        ("divide", Division, 2),
    ]
)
def test_calculation_operations_in_database(
    db_session,
    test_user,
    calculation_type,
    expected_class,
    expected_result
):

    calculation = Calculation.create(
        calculation_type=calculation_type,
        user_id=test_user.id,
        a=10,
        b=5
    )

    db_session.add(calculation)
    db_session.commit()

    calculation_id = calculation.id

    # Retrieve from PostgreSQL
    retrieved = db_session.query(Calculation).filter(
        Calculation.id == calculation_id
    ).first()

    assert isinstance(retrieved, expected_class)
    assert retrieved.get_result() == expected_result
    assert retrieved.result == expected_result

def test_calculation_timestamps(db_session, test_user):

    calculation = Calculation.create(
        calculation_type="add",
        user_id=test_user.id,
        a=10,
        b=5
    )

    db_session.add(calculation)
    db_session.commit()
    db_session.refresh(calculation)

    assert calculation.created_at is not None
    assert calculation.updated_at is not None

    assert isinstance(calculation.created_at, datetime)
    assert isinstance(calculation.updated_at, datetime)

def test_invalid_calculation_type_schema():

    with pytest.raises(ValidationError):

        CalculationCreate(
            a=10,
            b=5,
            type="exponent"
        )

def test_division_by_zero_schema():

    with pytest.raises(ValidationError):

        CalculationCreate(
            a=10,
            b=0,
            type="divide"
        )

def test_division_by_zero_model_get_result(test_user):
    with pytest.raises(
        ValueError,
        match="Cannot divide by zero"
    ):
        Calculation.create(
            calculation_type="divide",
            user_id=test_user.id,
            a=10,
            b=0
        )

@pytest.mark.parametrize(
    "invalid_a, invalid_b",
    [
        ("hello", 5),
        (10, "world"),
        (None, 5),
        (10, None),
    ]
)
def test_invalid_operands_schema(invalid_a, invalid_b):

    with pytest.raises(ValidationError):

        CalculationCreate(
            a=invalid_a,
            b=invalid_b,
            type="add"
        )


def test_missing_operands_schema():

    with pytest.raises(ValidationError):

        CalculationCreate(
            a=10,
            type="add"
        )


def test_invalid_user_foreign_key(db_session):

    calculation = Calculation.create(
        calculation_type="add",
        user_id=uuid4(),
        a=10,
        b=5
    )

    db_session.add(calculation)

    # PostgreSQL should reject a user_id
    # that does not reference an existing user.
    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_calculation_response_schema(db_session, test_user):

    calculation = Calculation.create(
        calculation_type="multiply",
        user_id=test_user.id,
        a=10,
        b=5
    )

    db_session.add(calculation)
    db_session.commit()
    db_session.refresh(calculation)

    response = CalculationResponse.model_validate(calculation)

    assert response.id == calculation.id
    assert response.user_id == test_user.id
    assert response.a == 10
    assert response.b == 5
    assert response.type == "multiply"
    assert response.result == 50

def test_division_by_zero_model_create(test_user):
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        Calculation.create(
            calculation_type="divide",
            user_id=test_user.id,
            a=10,
            b=0
        )

def test_invalid_calculation_type_model(test_user):
    with pytest.raises(ValueError):
        Calculation.create(
            calculation_type="exponent",
            user_id=test_user.id,
            a=10,
            b=5
        )