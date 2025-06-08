FROM python:3.12.7-slim AS base

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    git \
    && apt-get clean

RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="/root/.local/bin:$PATH"
RUN poetry self add poetry-plugin-export
RUN poetry config warnings.export false

WORKDIR /app

COPY pyproject.toml poetry.lock ./

# Install production dependencies
RUN poetry install --no-root --no-interaction

# Copy source code
COPY . .

# Generate environment file
RUN poetry run dump-env --template=/app/config/.env.template --prefix='SECRET_' > /app/config/.env

# For codecov-cli
RUN git config --global --add safe.directory /app
