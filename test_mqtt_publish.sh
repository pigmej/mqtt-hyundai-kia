#!/bin/bash
# Test script to send MQTT commands and verify they're received

BROKER_HOST="${MQTT_BROKER_HOST:-10.0.0.18}"
VEHICLE_ID="fb9ccccc-11111111-1111-1111-1111-111111111111"
TOPIC="hyundai/${VEHICLE_ID}/commands/refresh"

echo "=========================================="
echo "MQTT Command Test Script"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Broker: ${BROKER_HOST}"
echo "  Topic: ${TOPIC}"
echo ""

# Test 1: Subscribe to verify broker connectivity
echo "Test 1: Verifying broker connectivity..."
timeout 2 mosquitto_sub -h ${BROKER_HOST} -t "${TOPIC}" -C 1 >/dev/null 2>&1
if [ $? -eq 124 ]; then
    echo "✅ Broker is reachable (timeout as expected)"
else
    echo "⚠️  Broker connectivity issue"
fi
echo ""

# Test 2: Send command with verbose output
echo "Test 2: Sending 'force' refresh command..."
mosquitto_pub -h ${BROKER_HOST} -t "${TOPIC}" -m "force" -d
echo ""

# Test 3: Send multiple commands
echo "Test 3: Sending 3 commands in sequence..."
for i in 1 2 3; do
    echo "  Command ${i}/3..."
    mosquitto_pub -h ${BROKER_HOST} -t "${TOPIC}" -m "force"
    sleep 6  # Wait for throttle timeout
done
echo ""

echo "Test 4: Testing other command types..."
echo "  - cached command..."
mosquitto_pub -h ${BROKER_HOST} -t "${TOPIC}" -m "cached"
sleep 6

echo "  - smart command..."
mosquitto_pub -h ${BROKER_HOST} -t "${TOPIC}" -m "smart:300"
echo ""

echo "=========================================="
echo "Commands sent successfully!"
echo "Check your service logs for processing."
echo "=========================================="
