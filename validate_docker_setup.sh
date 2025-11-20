#!/bin/bash

# Docker and CI/CD Validation Script
# This script validates the Docker setup without requiring Docker to be installed

echo "=== Hyundai MQTT Docker Setup Validation ==="
echo

# Check if required files exist
echo "1. Checking required files..."
files=(
    "Dockerfile"
    ".dockerignore"
    "docker-compose.yml"
    "mosquitto.conf"
    ".github/workflows/docker.yml"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file missing"
    fi
done
echo

# Validate Dockerfile syntax
echo "2. Validating Dockerfile structure..."
if grep -qi "FROM python:3.10-slim as builder" Dockerfile; then
    echo "✅ Multi-stage build structure found"
else
    echo "❌ Multi-stage build structure missing"
fi

if grep -q "USER appuser" Dockerfile; then
    echo "✅ Non-root user configuration found"
else
    echo "❌ Non-root user configuration missing"
fi

if grep -q "HEALTHCHECK" Dockerfile; then
    echo "✅ Health check configuration found"
else
    echo "❌ Health check configuration missing"
fi
echo

# Validate .dockerignore
echo "3. Validating .dockerignore..."
if grep -q ".git" .dockerignore; then
    echo "✅ Git files excluded"
else
    echo "❌ Git files not excluded"
fi

if grep -q "__pycache__" .dockerignore; then
    echo "✅ Python cache excluded"
else
    echo "❌ Python cache not excluded"
fi
echo

# Validate docker-compose.yml
echo "4. Validating docker-compose.yml..."
if grep -q "hyundai-mqtt:" docker-compose.yml; then
    echo "✅ Main service defined"
else
    echo "❌ Main service not defined"
fi

if grep -q "mosquitto:" docker-compose.yml; then
    echo "✅ MQTT broker service defined"
else
    echo "❌ MQTT broker service not defined"
fi

if grep -q "depends_on:" docker-compose.yml; then
    echo "✅ Service dependencies defined"
else
    echo "❌ Service dependencies not defined"
fi
echo

# Validate GitHub Actions workflow
echo "5. Validating GitHub Actions workflow..."
if [ -f ".github/workflows/docker.yml" ]; then
    if grep -q "on:" .github/workflows/docker.yml; then
        echo "✅ Workflow triggers defined"
    else
        echo "❌ Workflow triggers not defined"
    fi
    
    if grep -q "test:" .github/workflows/docker.yml; then
        echo "✅ Test job found"
    else
        echo "❌ Test job not found"
    fi
    
    if grep -q "build:" .github/workflows/docker.yml; then
        echo "✅ Build job found"
    else
        echo "❌ Build job not found"
    fi
    
    if grep -q "ghcr.io" .github/workflows/docker.yml; then
        echo "✅ GHCR registry configured"
    else
        echo "❌ GHCR registry not configured"
    fi
else
    echo "❌ GitHub Actions workflow file missing"
fi
echo

# Validate mosquitto.conf
echo "6. Validating mosquitto.conf..."
if grep -q "listener 1883" mosquitto.conf; then
    echo "✅ MQTT listener configured"
else
    echo "❌ MQTT listener not configured"
fi

if grep -q "allow_anonymous true" mosquitto.conf; then
    echo "✅ Anonymous access configured (development)"
else
    echo "❌ Anonymous access not configured"
fi
echo

# Validate pyproject.toml updates
echo "7. Validating pyproject.toml..."
if grep -q "dev = \[" pyproject.toml; then
    echo "✅ Dev dependencies section found"
else
    echo "❌ Dev dependencies section missing"
fi

if grep -q "pytest" pyproject.toml; then
    echo "✅ Pytest dependency added"
else
    echo "❌ Pytest dependency missing"
fi
echo

# Check service readiness implementation
echo "8. Validating service readiness implementation..."
if grep -q "service-ready" src/main.py; then
    echo "✅ Service readiness file handling found"
else
    echo "❌ Service readiness file handling missing"
fi
echo

echo "=== Validation Complete ==="
echo "If all checks pass, the Docker setup is ready for deployment."