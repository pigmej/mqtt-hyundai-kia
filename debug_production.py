#!/usr/bin/env python3
"""
Production debugging script - runs the service with enhanced monitoring.
This script helps identify exactly where the command flow breaks.
"""

import asyncio
import logging
import sys
import time
from unittest.mock import Mock, AsyncMock, patch

# Setup path
sys.path.insert(0, '/workspaces/hyundai_mqtt')

# Configure extremely verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(levelname)8s] - %(name)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

from src.mqtt.client import MQTTClient
from src.commands.handler import CommandHandler
from src.config.settings import MQTTConfig
from src.hyundai.data_mapper import VehicleData

# Create mock API client
class MockAPIClient:
    def __init__(self):
        self.call_count = 0
    
    async def refresh_force(self, vehicle_id):
        self.call_count += 1
        logging.info(f"🔄 MockAPIClient.refresh_force called (call #{self.call_count}) for vehicle: {vehicle_id}")
        await asyncio.sleep(0.1)  # Simulate API call
        
        # Create mock vehicle data
        from datetime import datetime
        from dataclasses import dataclass
        
        @dataclass
        class MockStatus:
            last_updated: datetime = datetime.utcnow()
        
        mock_data = Mock(spec=VehicleData)
        mock_data.vehicle_id = vehicle_id
        mock_data.status = MockStatus()
        mock_data.to_mqtt_messages = Mock(return_value=[])
        
        logging.info(f"✅ MockAPIClient.refresh_force completed for vehicle: {vehicle_id}")
        return mock_data
    
    async def refresh_cached(self, vehicle_id):
        return await self.refresh_force(vehicle_id)
    
    async def refresh_smart(self, vehicle_id, max_age):
        return await self.refresh_force(vehicle_id)


async def test_production_flow():
    """Simulate production environment to debug command flow."""
    
    print("\n" + "="*80)
    print("🔍 PRODUCTION DEBUGGING - MQTT COMMAND FLOW")
    print("="*80 + "\n")
    
    # Test configuration
    test_vehicle_id = "fb9ccccc-11111111-1111-1111-1111-111111111111"
    test_topic = f"hyundai/{test_vehicle_id}/commands/refresh"
    test_payload = "force"
    
    print(f"Configuration:")
    print(f"  - Vehicle ID: {test_vehicle_id}")
    print(f"  - Topic: {test_topic}")
    print(f"  - Payload: {test_payload}")
    print()
    
    # Create mock API client
    mock_api = MockAPIClient()
    
    # Create mock MQTT client (for publishing)
    mock_mqtt_publish = Mock()
    mock_mqtt_publish.publish_vehicle_data = AsyncMock()
    mock_mqtt_publish.publish_error_status = AsyncMock()
    
    # Create command handler
    command_handler = CommandHandler(mock_api, mock_mqtt_publish)  # type: ignore
    
    # Create MQTT config
    mqtt_config = MQTTConfig(
        broker_host="10.0.0.18",  # Your broker
        broker_port=1883,
        username=None,
        password=None,
        use_tls=False,
        client_id="hyundai_mqtt_debug",
        qos_level=1,
        base_topic="hyundai"
    )
    
    # Create MQTT client with command callback
    mqtt_client = MQTTClient(
        mqtt_config,
        on_command_callback=command_handler.enqueue_command
    )
    
    print("📊 Component Status:")
    print(f"  - MQTT Client created: ✅")
    print(f"  - Command callback set: {'✅' if mqtt_client.on_command_callback else '❌'}")
    print(f"  - Event loop set: {'❌ (will be set on connect)' if not mqtt_client.loop else '✅'}")
    print()
    
    # Start command processing loop
    print("🚀 Starting command processing loop...")
    command_task = asyncio.create_task(command_handler.process_commands())
    print("  ✅ Command processing loop started")
    print()
    
    # Wait a moment to ensure loop is running
    await asyncio.sleep(0.2)
    
    # Try to connect to MQTT broker
    print("🔌 Attempting to connect to MQTT broker...")
    try:
        await asyncio.wait_for(mqtt_client.connect(), timeout=10.0)
        print("  ✅ Connected to MQTT broker")
        print(f"  ✅ Event loop now set: {mqtt_client.loop is not None}")
    except asyncio.TimeoutError:
        print("  ⚠️  Connection timeout - will test with simulated connection")
        mqtt_client.loop = asyncio.get_running_loop()
        mqtt_client.connected = True
    except Exception as e:
        print(f"  ⚠️  Connection failed: {e}")
        print("  📝 Testing with simulated connection...")
        mqtt_client.loop = asyncio.get_running_loop()
        mqtt_client.connected = True
    print()
    
    # Simulate receiving MQTT message
    print("📨 Simulating MQTT message arrival...")
    print(f"  Topic: {test_topic}")
    print(f"  Payload: {test_payload}")
    
    class FakeMessage:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload.encode('utf-8')
    
    fake_msg = FakeMessage(test_topic, test_payload)
    
    # Call the _on_message handler (this simulates what paho-mqtt does)
    print("  🔄 Calling _on_message handler...")
    mqtt_client._on_message(None, None, fake_msg)
    print("  ✅ _on_message handler called")
    print()
    
    # Wait for command processing
    print("⏳ Waiting for command to be processed...")
    print(f"  Queue size before wait: {command_handler._command_queue.qsize()}")
    
    # Wait up to 5 seconds for command to be processed
    max_wait = 5.0
    start_time = time.time()
    initial_call_count = mock_api.call_count
    
    while time.time() - start_time < max_wait:
        await asyncio.sleep(0.1)
        if mock_api.call_count > initial_call_count:
            break
    
    elapsed = time.time() - start_time
    
    print(f"  ⏱️  Waited {elapsed:.2f} seconds")
    print()
    
    # Check results
    print("📊 RESULTS:")
    print("="*80)
    print(f"API refresh_force called: {mock_api.call_count > initial_call_count}")
    print(f"Total API calls: {mock_api.call_count}")
    print(f"Queue size after processing: {command_handler._command_queue.qsize()}")
    print(f"publish_vehicle_data called: {mock_mqtt_publish.publish_vehicle_data.called}")
    print(f"publish_error_status called: {mock_mqtt_publish.publish_error_status.called}")
    print()
    
    # Diagnosis
    if mock_api.call_count > initial_call_count:
        print("✅ SUCCESS - Command was processed correctly!")
        print("   The fixes have resolved the issue.")
    else:
        print("❌ FAILURE - Command was NOT processed")
        print()
        print("📋 Diagnostic Checklist:")
        print(f"  1. Event loop set: {mqtt_client.loop is not None}")
        print(f"  2. Command callback set: {mqtt_client.on_command_callback is not None}")
        print(f"  3. MQTT connected: {mqtt_client.connected}")
        print(f"  4. Command processing loop running: {not command_task.done()}")
        print(f"  5. Queue size: {command_handler._command_queue.qsize()}")
        
        if command_task.done():
            print()
            print("⚠️  Command processing loop has stopped!")
            try:
                command_task.result()
            except Exception as e:
                print(f"   Exception: {e}")
    
    print()
    print("="*80)
    
    # Cleanup
    command_task.cancel()
    try:
        await command_task
    except asyncio.CancelledError:
        pass
    
    if mqtt_client.connected:
        mqtt_client.disconnect()
    
    print("\n✅ Test completed\n")


if __name__ == "__main__":
    print("\n⚙️  Starting production debugging session...")
    print("This script will test the MQTT command flow with enhanced logging.\n")
    
    try:
        asyncio.run(test_production_flow())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user\n")
    except Exception as e:
        print(f"\n\n❌ Test failed with exception: {e}\n")
        import traceback
        traceback.print_exc()
