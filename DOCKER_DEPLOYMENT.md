# Docker Deployment Guide

This guide provides comprehensive instructions for deploying the Hyundai MQTT integration service using Docker containers.

## Quick Start

### 1. Using Pre-built Image (Recommended)

```bash
docker run -d \
  --name hyundai-mqtt \
  --restart unless-stopped \
  -e HYUNDAI_USERNAME=your_email@example.com \
  -e HYUNDAI_PASSWORD=your_password \
  -e HYUNDAI_PIN=your_pin \
  -e HYUNDAI_REGION=1 \
  -e HYUNDAI_BRAND=1 \
  -e MQTT_BROKER_HOST=your_mqtt_broker \
  -e MQTT_BROKER_PORT=1883 \
  ghcr.io/yourusername/hyundai-mqtt:latest
```

### 2. Docker Compose (Development)

```bash
# Clone repository
git clone https://github.com/yourusername/hyundai-mqtt.git
cd hyundai-mqtt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start services
docker-compose up -d

# Monitor logs
docker-compose logs -f hyundai-mqtt
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `HYUNDAI_USERNAME` | Hyundai/Kia/Genesis account email | `user@example.com` |
| `HYUNDAI_PASSWORD` | Account password | `your_password` |
| `HYUNDAI_PIN` | Vehicle PIN for control commands | `1234` |
| `MQTT_BROKER_HOST` | MQTT broker hostname/IP | `192.168.1.100` |

### Optional Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `HYUNDAI_REGION` | Geographic region | `1` | `1` (Europe) |
| `HYUNDAI_BRAND` | Vehicle brand | `1` | `1` (Hyundai) |
| `MQTT_BROKER_PORT` | MQTT broker port | `1883` | `1883` |
| `MQTT_USERNAME` | MQTT authentication | - | `mqtt_user` |
| `MQTT_PASSWORD` | MQTT password | - | `mqtt_pass` |
| `LOG_LEVEL` | Logging level | `INFO` | `DEBUG` |
| `INITIAL_REFRESH` | Load cached data on startup | `true` | `false` |
| `REFRESH_INTERVAL` | Default refresh interval (seconds) | `60` | `300` |

## Region and Brand Codes

### Region Codes
- `1` = Europe
- `2` = Canada  
- `3` = USA
- `4` = China
- `5` = Australia
- `6` = India
- `7` = New Zealand
- `8` = Brazil

### Brand Codes
- `1` = Hyundai
- `2` = Kia
- `3` = Genesis

## Production Deployment

### 1. Security Configuration

For production environments, consider these security measures:

#### Non-root User
The container runs as a non-root user (UID 1001) by default.

#### Environment Variable Security
```bash
# Use Docker secrets for sensitive data
docker run -d \
  --name hyundai-mqtt \
  --secret hyundai_username \
  --secret hyundai_password \
  --secret hyundai_pin \
  -e HYUNDAI_USERNAME_FILE=/run/secrets/hyundai_username \
  -e HYUNDAI_PASSWORD_FILE=/run/secrets/hyundai_password \
  -e HYUNDAI_PIN_FILE=/run/secrets/hyundai_pin \
  ghcr.io/yourusername/hyundai-mqtt:latest
```

#### Network Isolation
```bash
# Create dedicated network
docker network create hyundai-network

# Run with network isolation
docker run -d \
  --name hyundai-mqtt \
  --network hyundai-network \
  # ... other options
  ghcr.io/yourusername/hyundai-mqtt:latest
```

### 2. Resource Limits

```bash
docker run -d \
  --name hyundai-mqtt \
  --memory=512m \
  --cpus=0.5 \
  --restart unless-stopped \
  # ... other options
  ghcr.io/yourusername/hyundai-mqtt:latest
```

### 3. Health Monitoring

The container includes built-in health checks:

```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' hyundai-mqtt

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' hyundai-mqtt
```

### 4. Log Management

```bash
# Configure log rotation
docker run -d \
  --name hyundai-mqtt \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  # ... other options
  ghcr.io/yourusername/hyundai-mqtt:latest
```

## Docker Compose Production

### Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  hyundai-mqtt:
    image: ghcr.io/yourusername/hyundai-mqtt:latest
    container_name: hyundai-mqtt
    restart: unless-stopped
    environment:
      - HYUNDAI_USERNAME=${HYUNDAI_USERNAME}
      - HYUNDAI_PASSWORD=${HYUNDAI_PASSWORD}
      - HYUNDAI_PIN=${HYUNDAI_PIN}
      - HYUNDAI_REGION=${HYUNDAI_REGION:-1}
      - HYUNDAI_BRAND=${HYUNDAI_BRAND:-1}
      - MQTT_BROKER_HOST=${MQTT_BROKER_HOST}
      - MQTT_BROKER_PORT=${MQTT_BROKER_PORT:-1883}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    networks:
      - app-network
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
    healthcheck:
      test: ["CMD", "python", "-c", "import os; from pathlib import Path; p = Path('/tmp/service-ready'); exit(0 if p.exists() else 1)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    logging:
      driver: json-file
      options:
        max-size: 10m
        max-file: 3

networks:
  app-network:
    driver: bridge
```

### Deployment Commands

```bash
# Deploy with production compose file
docker-compose -f docker-compose.prod.yml up -d

# Scale the service (if needed)
docker-compose -f docker-compose.prod.yml up -d --scale hyundai-mqtt=2

# Update to latest image
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

## Kubernetes Deployment

### 1. ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hyundai-mqtt-config
data:
  HYUNDAI_REGION: "1"
  HYUNDAI_BRAND: "1"
  MQTT_BROKER_HOST: "mosquitto-service"
  MQTT_BROKER_PORT: "1883"
  LOG_LEVEL: "INFO"
```

### 2. Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: hyundai-mqtt-secrets
type: Opaque
data:
  HYUNDAI_USERNAME: <base64-encoded-email>
  HYUNDAI_PASSWORD: <base64-encoded-password>
  HYUNDAI_PIN: <base64-encoded-pin>
```

### 3. Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hyundai-mqtt
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hyundai-mqtt
  template:
    metadata:
      labels:
        app: hyundai-mqtt
    spec:
      containers:
      - name: hyundai-mqtt
        image: ghcr.io/yourusername/hyundai-mqtt:latest
        ports:
        - containerPort: 8080
        envFrom:
        - configMapRef:
            name: hyundai-mqtt-config
        - secretRef:
            name: hyundai-mqtt-secrets
        resources:
          requests:
            memory: 256Mi
            cpu: 250m
          limits:
            memory: 512Mi
            cpu: 500m
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - "import os; from pathlib import Path; p = Path('/tmp/service-ready'); exit(0 if p.exists() else 1)"
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          exec:
            command:
            - python
            - -c
            - "import os; from pathlib import Path; p = Path('/tmp/service-ready'); exit(0 if p.exists() else 1)"
          initialDelaySeconds: 5
          periodSeconds: 10
```

## Troubleshooting

### Container Issues

```bash
# Check container status
docker ps -a

# View logs
docker logs hyundai-mqtt

# Debug container
docker exec -it hyundai-mqtt /bin/bash

# Check health status
docker inspect --format='{{.State.Health.Status}}' hyundai-mqtt
```

### Common Issues

1. **Container exits immediately**
   - Check environment variables are set correctly
   - Verify MQTT broker is accessible
   - Review logs for specific error messages

2. **Health check fails**
   - Service may not be initializing correctly
   - Check if `/tmp/service-ready` file is created
   - Verify all dependencies are configured

3. **MQTT connection issues**
   - Verify broker hostname and port
   - Check network connectivity
   - Validate authentication credentials

### Performance Monitoring

```bash
# Monitor resource usage
docker stats hyundai-mqtt

# Monitor container size
docker images hyundai-mqtt

# Check image layers
docker history ghcr.io/yourusername/hyundai-mqtt:latest
```

## Updates and Maintenance

### Automated Updates

```bash
# Watch for image updates
docker run -d \
  --name watchtower \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower \
  --interval 3600 \
  hyundai-mqtt
```

### Backup and Restore

```bash
# Export container configuration
docker inspect hyundai-mqtt > hyundai-mqtt-config.json

# Backup environment variables
docker inspect hyundai-mqtt | jq '.[0].Config.Env' > env-backup.txt
```

## Support

For issues related to:
- **Docker deployment**: Check this guide and Docker documentation
- **Application functionality**: Review the main README.md
- **API issues**: Check Hyundai/Kia API status and credentials

## Security Considerations

1. **Never commit credentials to version control**
2. **Use Docker secrets or Kubernetes secrets for sensitive data**
3. **Run containers with minimal privileges**
4. **Regularly update base images**
5. **Monitor container logs for security events**
6. **Implement network segmentation in production**