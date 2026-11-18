# tests/conftest.py

import subprocess
import time
import logging
from typing import Generator, Dict, List
from contextlib import contextmanager

import os
import pytest
import requests
from faker import Faker
from playwright.sync_api import sync_playwright, Browser, Page
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.database import Base, get_engine, get_sessionmaker
from app.models.user import User
from app.models.calculation import Calculation
from app.config import settings
from app.database_init import init_db, drop_db



# ======================================================================================
# Logging Configuration
# ======================================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ======================================================================================
# Database Configuration
# ======================================================================================
fake = Faker()
Faker.seed(12345)

# Use the dedicated test database URL when provided.
# Otherwise, fall back to the application database URL.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    settings.DATABASE_URL
)

logger.info("Configuring test database connection.")

test_engine = get_engine(database_url=TEST_DATABASE_URL)
TestingSessionLocal = get_sessionmaker(engine=test_engine)
# ======================================================================================
# Helper Functions
# ======================================================================================
def create_fake_user() -> Dict[str, str]:
    """
    Generate a dictionary of fake user data for testing.

    Returns:
        A dict containing user fields with fake data.
    """
    return {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": fake.unique.email(),  # Ensure uniqueness where necessary
        "username": fake.unique.user_name(),
        "password": fake.password(length=12)
    }

@contextmanager
def managed_db_session():
    """
    Context manager for safe database session handling.
    Automatically handles rollback and cleanup.

    Example:
        with managed_db_session() as session:
            user = session.query(User).first()
    """
    session = TestingSessionLocal()
    try:
        yield session
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()

# ======================================================================================
# Server Startup / Healthcheck
# ======================================================================================
def wait_for_server(url: str, timeout: int = 30) -> bool:
    """
    Wait for server to be ready, raising an error if it never becomes available.
    """
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    return False

class ServerStartupError(Exception):
    """Raised when the test server fails to start properly"""
    pass

# ======================================================================================
# Primary Database Fixtures
# ======================================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_database(request):
    """
    Initialize the test database once per session.

    - Drop existing tables.
    - Create tables using the shared SQLAlchemy Base.
    - Clean up after tests unless --preserve-db is enabled.
    """

    logger.info("Setting up test database...")

    # Ensure both User and Calculation models are registered.
    from app.models.user import User
    from app.models.calculation import Calculation

    # Create tables using the dedicated test engine.
    Base.metadata.drop_all(bind=test_engine)
    logger.info("Dropped existing test tables.")

    Base.metadata.create_all(bind=test_engine)
    logger.info("Created test tables.")

    yield

    preserve_db = request.config.getoption("--preserve-db")

    if preserve_db:
        logger.info("Preserving test database.")
    else:
        logger.info("Cleaning up test database.")
        Base.metadata.drop_all(bind=test_engine)
        logger.info("Dropped test tables.")

@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """
    Provide an isolated database session for each test.
    All database changes are rolled back after the test,
    regardless of whether it passes or fails.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(
        bind=connection,
        join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()

# ======================================================================================
# Test Data Fixtures
# ======================================================================================
@pytest.fixture
def fake_user_data() -> Dict[str, str]:
    """Provide a dictionary of fake user data."""
    return create_fake_user()

@pytest.fixture
def test_user(db_session: Session) -> User:
    """
    Create and return a single test user.
    """
    user_data = create_fake_user()
    user = User(
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        email=user_data["email"],
        username=user_data["username"],
        password_hash=User.hash_password(user_data["password"])
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    logger.info(f"Created test user with ID: {user.id}")
    return user

@pytest.fixture
def seed_users(db_session: Session, request) -> List[User]:
    """
    Create multiple test users with hashed passwords.
    """
    try:
        num_users = request.param
    except AttributeError:
        num_users = 5

    users = []

    for _ in range(num_users):
        user_data = create_fake_user()

        user = User(
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            email=user_data["email"],
            username=user_data["username"],
            password_hash=User.hash_password(user_data["password"])
        )

        users.append(user)
        db_session.add(user)

    db_session.flush()
    logger.info(f"Seeded {len(users)} users into the test database.")
    return users

# ======================================================================================
# FastAPI Server Fixture (Optional)
# ======================================================================================
@pytest.fixture(scope="session")
def fastapi_server():
    """
    Start and manage a FastAPI test server, if needed for integration tests.
    """
    server_url = 'http://127.0.0.1:8000/'
    logger.info("Starting test server...")

    try:
        process = subprocess.Popen(
            ['python', 'main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if not wait_for_server(server_url, timeout=30):
            raise ServerStartupError("Failed to start test server")

        logger.info("Test server started successfully.")
        yield  # Run all tests that depend on this fixture

    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise
    finally:
        logger.info("Terminating test server...")
        process.terminate()
        try:
            process.wait(timeout=5)
            logger.info("Test server terminated gracefully.")
        except subprocess.TimeoutExpired:
            logger.warning("Test server did not terminate in time; killing it.")
            process.kill()

# ======================================================================================
# Browser and Page Fixtures (Optional)
# ======================================================================================
@pytest.fixture(scope="session")
def browser_context():
    """
    Provide a Playwright browser context for UI tests.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        logger.info("Playwright browser launched.")
        try:
            yield browser
        finally:
            logger.info("Closing Playwright browser.")
            browser.close()

@pytest.fixture
def page(browser_context: Browser):
    """
    Provide a new browser page for each test.
    """
    context = browser_context.new_context(
        viewport={'width': 1920, 'height': 1080},
        ignore_https_errors=True
    )
    page = context.new_page()
    logger.info("Created new browser page.")
    try:
        yield page
    finally:
        logger.info("Closing browser page and context.")
        page.close()
        context.close()

# ======================================================================================
# Pytest Command-Line Options and Test Collection
# ======================================================================================
def pytest_addoption(parser):
    """
    Add command line options like --preserve-db or --run-slow, if needed.
    """
    parser.addoption(
        "--preserve-db",
        action="store_true",
        default=False,
        help="Keep test database after tests, and skip table truncation."
    )
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run tests marked as slow"
    )

def pytest_collection_modifyitems(config, items):
    """
    Automatically skip slow tests unless --run-slow is specified.
    """
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="use --run-slow to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)