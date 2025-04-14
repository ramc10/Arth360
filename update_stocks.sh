#!/bin/bash

# Source environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Build the stocks container
docker build -t arth360-stocks -f stocks/Dockerfile .

# Run the stocks container
docker run --rm \
  --name arth360-stocks \
  --network arth360_arth360-network \
  -e DB_HOST=mysql \
  -e DB_USER=${DB_USER} \
  -e DB_PASSWORD=${DB_PASSWORD} \
  -e DB_NAME=${DB_NAME} \
  arth360-stocks 