from pathlib import Path

from app import app
from data_models import db


# Determines the absolute project directory.
PROJECT_DIRECTORY = Path(__file__).resolve().parent

# Ensures that the directory for the SQLite database exists.
DATA_DIRECTORY = PROJECT_DIRECTORY / "data"
DATA_DIRECTORY.mkdir(exist_ok=True)


def initialize_database():
    """Creates all missing database tables."""

    # SQLAlchemy needs the Flask application context to access
    # the configured database connection.
    with app.app_context():
        # Creates every table defined by the imported models.
        #
        # Existing tables and their data remain unchanged.
        db.create_all()

    print("Database initialization completed.")
    print("Database tables are ready.")


if __name__ == "__main__":
    initialize_database()
