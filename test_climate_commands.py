#!/usr/bin/env python3
"""Test script to send climate control commands via MQTT."""

import paho.mqtt.client as mqtt
import json
import time

# Configuration
BROKER_HOST = "10.0.0.18"
VEHICLE_ID = "fb9ccccc-11111111-1111-1111-1111-111111111111"

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")

def on_publish(client, userdata, mid):
    print(f"Message {mid} published")

def main():
    # Create MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_publish = on_publish
    
    # Connect to broker
    print(f"Connecting to MQTT broker at {BROKER_HOST}...")
    client.connect(BROKER_HOST, 1883, 60)
    
    # Start network loop
    client.loop_start()
    
    try:
        # Test 1: Stop climate command
        print("\n=== Test 1: Stop Climate Command ===")
        climate_topic = f"hyundai/{VEHICLE_ID}/commands/climate"
        stop_payload = json.dumps({"action": "stop_climate"})
        
        result = client.publish(climate_topic, stop_payload, qos=1)
        print(f"Published stop_climate command to {climate_topic}")
        print(f"Message ID: {result.mid}")
        
        # Wait for processing
        time.sleep(10)
        
        # Test 2: Start climate command (minimal)
        print("\n=== Test 2: Start Climate Command ===")
        start_payload = json.dumps({"action": "start_climate", "set_temp": 21, "duration": 10})
        
        result = client.publish(climate_topic, start_payload, qos=1)
        print(f"Published start_climate command to {climate_topic}")
        print(f"Message ID: {result.mid}")
        
        # Wait for processing
        time.sleep(15)
        
        print("\n=== Test Complete ===")
        print("Check service logs for detailed verification process")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()