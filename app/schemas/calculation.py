# app/schemas/calculation.py
# defines the schemas that validate the data coming into and going out of your FastAPI app
# checks that the incoming data has the correct structure and values 

from enum import Enum # fixed set of allowed values
from pydantic import (
    BaseModel, # used to create schemas
    Field, # adds rules, descriptions, and examples to fields
    ConfigDict, # configs for how the model behaves
    model_validator, # validates multiple fields together
    field_validator # validates individual fields
)
from typing import List, Optional # represents list of values, a value can be None
from uuid import UUID # represents unique identifiers
from datetime import datetime # dates and times for objects 

# defines the calculation operations that the app can support
# currently restricted to 4 valid operations - what is recognized by the calculator
class CalculationType(str, Enum):
    # Enum establishes this fixed set of acceptable values
    # inherits both str and Enum because: 
    # str = makes the enum values behave like strings (e.g., can be serialized to JSON)
    # Enum = provides the benefits of an enumeration (fixed set of values, type safety,
    """
    Enumeration of valid calculation types.
    
    Using an Enum provides:
    1. Type safety: Only valid values can be used
    2. Auto-completion: IDEs can suggest valid values
    3. Documentation: Automatically appears in OpenAPI spec
    4. Validation: Pydantic automatically rejects invalid values
    
    Inheriting from str makes this a string enum, so values serialize
    naturally as strings in JSON.
    """
    ADDITION = "addition"
    SUBTRACTION = "subtraction"
    MULTIPLICATION = "multiplication"
    DIVISION = "division"

# IMPORTANT CLASS!!!
# defines the common fields that all calculation-related schemas need
# created once rather than being repeatedly used in Create and Response
class CalculationBase(BaseModel): # creates a pydantic model called CalculationBase that gives the class automatic features
    """
    Base schema for calculation data.
    
    This schema defines the common fields that all calculation requests share.
    It's used as a base for more specific schemas (Create, Update, Response).
    
    Design Pattern: This follows the DRY (Don't Repeat Yourself) principle by
    defining common fields once and reusing them in other schemas.
    """
    # defines the operaiton a user wants to perform
    type: CalculationType = Field( # field must be one of the operations defined in the Enum
        ..., # additional configs that are required 
        description="Type of calculation to perform", # provides documentation
        examples=["addition"] # provides example value for the documentation
    )
    # defines the numbers used in the calculation
    a: float = Field(
        ...,
        description="First numeric input for the calculation",
        examples=[10.5]
    )

    b: float = Field(
        ...,
        description="Second numeric input for the calculation",
        examples=[3]
    )

    @field_validator("type", mode="before") # validates the type field before normal Pydantic validation occurs
    @classmethod
    def validate_type(cls, v): # cls = CalculationBase, v = type field
        """
        Validate and normalize the calculation type.
        
        This validator ensures that the type is a string and converts it to
        lowercase for case-insensitive comparison. It runs BEFORE Pydantic's
        standard validation (mode="before").
        
        Args:
            v: The value to validate
            
        Returns:
            The normalized (lowercase) type value
            
        Raises:
            ValueError: If the type is not a valid calculation type
        """
        allowed = {e.value for e in CalculationType} # creates a set of all valid calculation types, sets make things efficient and avoid duplicates
        if not isinstance(v, str) or v.lower() not in allowed: # checks if the value is a string, then checks if it is part of the Enum set of allowed values
            raise ValueError(
                f"Type must be one of: {', '.join(sorted(allowed))}" # if neither condition is met, validation error is raised
            )
        return v.lower() # returns the lowercase version of the type to ensure consistency in how types are stored and compared

    # Validate division
    @model_validator(mode="after")
    def validate_division(self):
        if self.type == CalculationType.DIVIDE and self.b == 0:
            raise ValueError("Cannot divide by zero")

        return self

    model_config = ConfigDict(
        from_attributes=True
    )

# specialized schema for creating a new calculation
# inherits from CalculationBase to avoid repeating the common fields
class CalculationCreate(CalculationBase):
    """
    Schema for creating a new Calculation.
    
    This schema is used when a client wants to create a calculation.
    It includes the user_id to associate the calculation with a user.
    
    In a real application, the user_id would typically come from the
    authenticated user's session rather than the request body.
    
    Receives: 
    - a
    - b
    - type
    """
    user_id: UUID = Field( # additional field, adds user_id to associate the calculation with a specific user
        ...,
        description="UUID of the user who owns this calculation",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )

    # adds a complete example to the documentation
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "addition",
                "a": 10.5,
                "b": 3,
                "user_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    )
# because of inheritence, CalculationCreate effectively has 4 fields: 
# type, a, b, and user_id. The first three are inherited from CalculationBase, while user_id is specific to CalculationCreate.

class CalculationUpdate(BaseModel):
    """
    Schema used when updating an existing calculation.
    All fields are optional to support partial updates.
    """

    a: Optional[float] = None
    b: Optional[float] = None
    type: Optional[CalculationType] = None

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, value):
        if value is None:
            return value

        if not isinstance(value, str):
            raise ValueError("Calculation type must be a string")

        allowed = {item.value.lower() for item in CalculationType}

        if value.lower() not in allowed:
            raise ValueError(
                "Type must be one of: Add, Sub, Multiply, Divide"
            )

        return value.capitalize()

    model_config = ConfigDict(
        from_attributes=True
    )

class CalculationRead(CalculationBase):
    """
    Schema used when reading a calculation.

    Returns all calculation information, including
    database-generated fields and the calculated result.
    """

    id: UUID = Field(
        ...,
        description="Unique calculation identifier"
    )

    result: float = Field(
        ...,
        description="Result of the calculation"
    )

    created_at: datetime = Field(
        ...,
        description="Date and time calculation was created"
    )

    updated_at: datetime = Field(
        ...,
        description="Date and time calculation was last updated"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174999",
                "a": 10,
                "b": 5,
                "type": "Add",
                "result": 15,
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00"
            }
        }
    )

class CalculationResponse(CalculationBase): # also inherits from CalculationBase
    """
    Schema for reading a Calculation from the database.
    
    This schema includes all the fields that are returned when reading
    a calculation, including database-generated fields like id, created_at,
    and the computed result.
    
    The from_attributes=True config allows this schema to be populated from
    SQLAlchemy model instances using model.from_orm(db_calculation).
    """
    id: UUID = Field( # additional field for unique identifier of the calculation
        ..., # required
        description="Unique UUID of the calculation",
        examples=["123e4567-e89b-12d3-a456-426614174999"]
    )
    user_id: UUID = Field( # identifies which user owns the calculation, links the calculation to a specific user
        ..., # required
        description="UUID of the user who owns this calculation",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
    created_at: datetime = Field( # stores the date/time when the calcualtion was originall created
        ..., # required
        description="Time when the calculation was created"
    )
    updated_at: datetime = Field( # sotres the date/time when the calculation was last modified
        ..., # required
        description="Time when the calculation was last updated"
    )
    result: float = Field( # stores the computed result of the calculation
        ..., # required
        description="Result of the calculation",
        examples=[15.5]
    )

    model_config = ConfigDict(
        from_attributes=True, # Pydantic can read values directly from an obj's attributes
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174999",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "type": "addition",
                "a": 10.5,
                "b": 3,
                "result": 15.5,
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00"
            }
        }
    )