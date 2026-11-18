# app/models/calculation.py
# this model uses polymorphic inheritance to create a base calculation model and subclasses for each type of calculation (addition, subtraction, multiplication, division)
# creating, calculating, and storing operations in a single db table

# imports required to provide the functionality needed to define the models and interact with the database
from datetime import datetime # handles timestamps
import uuid # hanldes unique identifers

from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Float # handles database columns and types
from sqlalchemy.dialects.postgresql import UUID # handles PostgreSQL specific UUID type
from sqlalchemy.orm import relationship, declared_attr # handles relationships between models and allows for dynamic attribute definition

from app.database import Base # handles database connection and base class for models

# foundations for the calculation model
# defines what every calculation should have and how it should behave
class AbstractCalculation:
    """
    Abstract base class defining common attributes for all calculations.
    
    This class uses SQLAlchemy's @declared_attr decorator to define columns
    that will be shared across all calculation types. The @declared_attr
    decorator is necessary when defining columns in a mixin class.
    
    Design Pattern: This follows the Template Method pattern, where the
    abstract class defines the structure and subclasses provide specific
    implementations.
    """

    @declared_attr # SQLAlchemy decorator that allows dynamic attribute definition in mixins, useful for mixins and inheritence
    def __tablename__(cls):
        """All calculation types share the 'calculations' table"""
        return 'calculations'

# defines the primary key for the model
# shared db structure for all calculation types
    @declared_attr
    def id(cls):
        """Unique identifier for each calculation (UUID for distribution)"""
        return Column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            nullable=False
        )

    @declared_attr
    def user_id(cls): # connects the calculation to the user who created it
        """        
        CASCADE delete ensures calculations are deleted when user is deleted.
        Index improves query performance when filtering by user_id.
        """
        return Column(
            UUID(as_uuid=True),
            ForeignKey('users.id', ondelete='CASCADE'), # IMPORTANT: establishes foreign key relationship with the users table
            nullable=False,
            index=True # creates a database index to improve query performance when filtering by user_id
        )

    # this is a discriminator column
    # this tells SQLAlchemy what kind of calculation each database record represents
    # different calculations can be stored in the same table 
    @declared_attr
    def type(cls):
        """        
        This column tells SQLAlchemy which subclass to instantiate when
        loading records from the database. Values include: 'addition',
        'subtraction', 'multiplication', 'division'.
        """
        return Column(
            String(50),
            nullable=False,
            index=True
        )

    # stores numbers used in the calcultion 
    @declared_attr
    def a(cls):
        return Column(
            Float, 
            nullable=False
        )
    
    @declared_atr
    def b(cls):
        return Column(
            Float,
            nullable=False
        )

    # stores the calculated answer
    @declared_attr
    def result(cls):
        """
        The computed result of the calculation.
        
        Stored as Float to handle decimal values. Can be NULL initially
        and computed on-demand using get_result() method.
        """
        return Column(
            Float,
            nullable=True # nullable because a calculation might be created before it's result is technically computed 
        )
    # Note: the app must explicitly assign the result to this column after calling get_result() in order to store it in the database

    # records when the calculation was created
    @declared_attr
    def created_at(cls):
        """Timestamp when the calculation was created"""
        return Column(
            DateTime,
            default=datetime.utcnow,
            nullable=False
        )

    # records when the calculation was last updated
    @declared_attr
    def updated_at(cls):
        """Timestamp when the calculation was last updated"""
        return Column(
            DateTime,
            default=datetime.utcnow,
            onupdate=datetime.utcnow, # tells SQLAlchemy to automatically update this timestamp whenever the record is updated by the ORM
            nullable=False
        )

    # defines the relationship with the User model
    # bidirectional relationship - allows acess to the user from a calculation 
    # EX: calculation.user & user.calculations
    # in order for this to work correctly, the User model must also define the correspondng relationship with the Calculation model using back_populates
    @declared_attr
    def user(cls):
        """
        Relationship to the User model.
        
        back_populates creates a bidirectional relationship, allowing access
        to user.calculations and calculation.user.
        """
        return relationship(
            "User", 
            back_populates="calculations"
        )

    # the Factory Pattern: creates objects without requiring calling the code to know wich specific class needs to be instantiated
    # similar to our initial calculator project, this will allow us to extend the dictionary of operations and create new subclasses without significantly changing the app
    @classmethod
    def create(cls, calculation_type: str, user_id: uuid.UUID, a: float, b: float):
     
        # dictionary that maps calculation types to their corresponding classes in Python
        calculation_classes = {
            'addition': Addition, # EX: when someone requests an additional calculation, the factory will create an instance of the Addition class
            'subtraction': Subtraction,
            'multiplication': Multiplication,
            'division': Division,
        }

        if not isinstance(calcultion_type, str):
            raise ValueError("Calculation type must be in the list of operations")
        
        calculation_class = calculation_classes.get(
            calculation_type.lower()
        )

        if not calculation_class: 
            raise ValueError(f"Unsupported calculation type: {calculation_type}")

        calculation = calculation_class(
            user_id=user_id,
            a=a,
            b=b
        )

        calculation.result = calculation.get_result()

        return calculation

    def get_result(self) -> float:
        """
        Abstract method to compute the calculation result.
        
        Each subclass must implement this method with its specific logic.
        This follows the Template Method pattern where the interface is
        defined here but implementation is deferred to subclasses.
        
        Raises:
            NotImplementedError: If called on base class
        """
        raise NotImplementedError(
            "Subclasses must implement get_result() method"
        )

    def __repr__(self):
        return (
            f"<Calculation(type={self.type}, "
            f"a={self.a}, b={self.b}, result={self.result})>"
        )

# where the actual SQLAchemy polymorphic inheritance is defined and happens
class Calculation(Base, AbstractCalculation):
    """
    Base calculation model with polymorphic configuration.
    
    This class combines SQLAlchemy's Base with our AbstractCalculation mixin
    and configures polymorphic inheritance through __mapper_args__.
    
    Polymorphic Configuration:
    - polymorphic_on: Specifies the discriminator column (type)
    - polymorphic_identity: The value stored for this base class
    
    When querying Calculation, SQLAlchemy automatically:
    1. Reads the 'type' column value
    2. Determines the appropriate subclass
    3. Returns an instance of that subclass
    """
    # these settings are critical!!!
    __mapper_args__ = {
        "polymorphic_on": "type", # tells SQLAlchmy to use the type column to determine which class shoul dbe instantiated
        "polymorphic_identity": "calculation", # defines the identify of the base Calculation class
    }

    # each subclass will have its own identify as well
    # this is how SQLAlchemy will know which calculation class to return when querying the database
    # each operation subclass inherits from the Calculation class - receives all the shared db cols and functionality 
    # BUT each subclass implements it's own version of get_result(), example of polymorphism

# handles addition calculations
class Addition(Calculation):
    """
    Addition calculation subclass.
    
    Polymorphic Identity: 'addition'
    Operation: Sums all numbers in the inputs list
    
    Example:
        add = Addition(user_id=user_id, inputs=[1, 2, 3])
        result = add.get_result()  # Returns 6
    """
    __mapper_args__ = {"polymorphic_identity": "addition"} # tells SQLAlchemy that records with this type should be represented as Addition objects

    # calculation method
    def get_result(self) -> float:
        """
        Calculate the sum of all input numbers.
        
        Returns:
            The sum of all inputs
            
        Raises:
            ValueError: If inputs is not a list or has fewer than 2 numbers
        """
        return self.a + self.b

# handles subtraction calculations
class Subtraction(Calculation):
    """
    Subtraction calculation subclass.
    
    Polymorphic Identity: 'subtraction'
    Operation: Subtracts subsequent numbers from the first number
    
    Example:
        sub = Subtraction(user_id=user_id, inputs=[10, 3, 2])
        result = sub.get_result()  # Returns 5 (10 - 3 - 2)
    """
    __mapper_args__ = {"polymorphic_identity": "subtraction"} # tells SQLAlchemy that records with this type should be represented as Subtraction objects

    # calculation method
    def get_result(self) -> float:
        """
        Subtract all subsequent numbers from the first number.
        
        Returns:
            The result of sequential subtraction
            
        Raises:
            ValueError: If inputs is not a list or has fewer than 2 numbers
        """
        return self.a - self.b

# handles multiplication calculations
class Multiplication(Calculation):
    """
    Multiplication calculation subclass.
    
    Polymorphic Identity: 'multiplication'
    Operation: Multiplies all numbers in the inputs list
    
    Example:
        mult = Multiplication(user_id=user_id, inputs=[2, 3, 4])
        result = mult.get_result()  # Returns 24
    """
    __mapper_args__ = {"polymorphic_identity": "multiplication"} # tells SQLAlchemy that records with this type should be represented as Multiplication objects

    # calculation method
    def get_result(self) -> float:
        """
        Calculate the product of all input numbers.
        
        Returns:
            The product of all inputs
            
        Raises:
            ValueError: If inputs is not a list or has fewer than 2 numbers
        """
        return self.a * self.b

# handles division calculations
class Division(Calculation):
    """
    Division calculation subclass.
    
    Polymorphic Identity: 'division'
    Operation: Divides the first number by subsequent numbers sequentially
    
    Example:
        div = Division(user_id=user_id, inputs=[100, 2, 5])
        result = div.get_result()  # Returns 10 (100 / 2 / 5)
        
    Note: This implementation uses EAFP (Easier to Ask for Forgiveness than
    Permission) by checking for zero during calculation rather than before.
    """
    __mapper_args__ = {"polymorphic_identity": "division"} # tells SQLAlchemy that records with this type should be represented as Division objects

    # calculation method
    def get_result(self) -> float:
        """
        Divide the first number by all subsequent numbers sequentially.
        
        Returns:
            The result of sequential division
            
        Raises:
            ValueError: If inputs is not a list, has fewer than 2 numbers,
                       or if attempting to divide by zero
        """
        if self.b == 0: 
            raise ValueError("Cannot divide by zero.")
        return self.a / self.b