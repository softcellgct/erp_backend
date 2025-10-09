# Backend API

A robust FastAPI-based backend service for managing educational institutions, users, and related data. Built with asynchronous operations, JWT authentication, and role-based access control.

## Features

- **User Authentication**: Secure login and registration with JWT tokens
- **Role-Based Access Control**: Superadmin and user roles with middleware protection
- **Master Data Management**: CRUD operations for institutions, departments, courses, and classes
- **Asynchronous Database**: PostgreSQL with SQLAlchemy async support
- **API Documentation**: Auto-generated Swagger UI at `/docs`
- **Database Migrations**: Alembic for schema versioning
- **Environment Configuration**: Pydantic settings with .env support

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with asyncpg
- **ORM**: SQLAlchemy (async)
- **Authentication**: JWT (JSON Web Tokens)
- **Validation**: Pydantic
- **Migration Tool**: Alembic
- **Dependency Management**: Poetry
- **Logging**: Loguru

## Installation

### Prerequisites

- Python 3.12+
- PostgreSQL
- Poetry (for dependency management)

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd backend
   ```

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Set up environment variables**:
   Create a `.env` file in the `src/` directory with the following variables:
   ```env
   DATABASE_URL="postgresql+asyncpg://<username>:<password>@<db_url>:<db_port>/<database_name>"
   SECRET_KEY=your-secret-key-here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   ```

4. **Run database migrations**:
   ```bash
   cd src
   source ../.venv/bin/activate  # Activate virtual environment
   alembic upgrade head
   ```

## Usage

### Running the Application

1. **Activate virtual environment**:
   ```bash
   poetry shell
   ```

2. **Start the server**:
   ```bash
   cd src
   uvicorn main:app --reload
   ```

The API will be available at `http://localhost:8000`

### API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## API Endpoints

### Authentication
- `POST /api/v1/user/register` - Register a new user
- `POST /api/v1/user/login` - Login and get JWT token

### Master Data (Superadmin only)
- `GET/POST/PUT/DELETE /api/v1/master/institutions` - Manage institutions
- `GET/POST/PUT/DELETE /api/v1/master/departments` - Manage departments
- `GET/POST/PUT/DELETE /api/v1/master/courses` - Manage courses
- `GET/POST/PUT/DELETE /api/v1/master/classes` - Manage classes

### User Management
- `GET /api/v1/user` - Get current user info (authenticated users)

## Database Schema

The application uses the following main entities:
- **Users**: Authentication and user management
- **Roles**: User roles (superadmin, user)
- **Institutions**: Educational institutions
- **Departments**: Departments within institutions
- **Courses**: Courses offered by departments
- **Classes**: Class sections for courses

## Development

### Running Tests
```bash
poetry run pytest
```

### Code Formatting
```bash
poetry run ruff check .
poetry run ruff format .
```

### Database Migrations
```bash
cd src
alembic revision --autogenerate -m "Migration message"
alembic upgrade head
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `SECRET_KEY` | JWT secret key | Required |
| `ALGORITHM` | JWT algorithm | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time | 30 |

## Project Structure

```
backend/
├── src/
│   ├── main.py                 # FastAPI application entry point
│   ├── alembic/                # Database migrations
│   ├── apps/
│   │   ├── auth/               # Authentication routes and services
│   │   ├── gate/               # Gateway routes
│   │   └── master/             # Master data management
│   ├── common/
│   │   ├── models/             # SQLAlchemy models
│   │   └── schemas/            # Pydantic schemas
│   ├── components/
│   │   ├── db/                 # Database configuration
│   │   ├── middleware/         # Custom middleware
│   │   └── settings.py         # Application settings
│   └── logs/                   # Application logs
├── tests/                      # Unit tests
├── pyproject.toml              # Poetry configuration
├── poetry.lock                 # Poetry lock file
└── README.md                   # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For questions or issues, please open an issue on GitHub or contact the development team.