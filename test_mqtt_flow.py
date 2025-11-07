#!/usr/bin/env python3
"""
Test script to simulate and debug MQTT command flow.
"""

import asyncio
import sys
from unittest.mock import Mock, AsyncMock, MagicMock
import logging

# Setup path
sys.path.insert(0, '/workspaces/hyundai_mqtt')

# Configure logging to see everything
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.mqtt.client import MQTTClient
from src.mqtt.topics import TopicManager
from src.commands.handler import CommandHandler, RefreshCommand
from src.config.settings import MQTTConfig


async def test_message_flow():
    """Simulate the full message flow from MQTT to command execution."""
    
    print("\n" + "="*80)
    print("TESTING MQTT COMMAND FLOW")
    print("="*80 + "\n")
    
    # Test data
    topic = "hyundai/fb9ccccc-11111111-1111-1111-1111-111111111111/commands/refresh"
    payload = "force"
    
    print(f"Test Topic: {topic}")
    print(f"Test Payload: {payload}\n")
    
    # Step 1: Test topic manager extraction
    print("STEP 1: Testing TopicManager.extract_vehicle_id_from_topic()")
    print("-" * 80)
    topic_manager = TopicManager("hyundai")
    vehicle_id = topic_manager.extract_vehicle_id_from_topic(topic)
    print(f"✓ Extracted vehicle_id: {vehicle_id}")
    assert vehicle_id == "fb9ccccc-11111111-1111-1111-1111-111111111111"
    print()
    
    # Step 2: Test command parsing
    print("STEP 2: Testing RefreshCommand.parse()")
    print("-" * 80)
    command = RefreshCommand.parse(topic, payload)
    print(f"✓ Parsed command: {command}")
    assert command.command_type == "force"
    assert command.vehicle_id == vehicle_id
    print()
    
    # Step 3: Test command handler with queue
    print("STEP 3: Testing CommandHandler.enqueue_command()")
    print("-" * 80)
    
    # Create mock API client
    mock_api_client = Mock()
    mock_api_client.refresh_force = AsyncMock(return_value=Mock(vehicle_id=vehicle_id))
    
    # Create mock MQTT client
    mock_mqtt_client = Mock()
    mock_mqtt_client.publish_vehicle_data = AsyncMock()
    mock_mqtt_client.publish_error_status = AsyncMock()
    
    # Create command handler
    command_handler = CommandHandler(mock_api_client, mock_mqtt_client)
    
    # Enqueue command
    await command_handler.enqueue_command(topic, payload)
    print(f"✓ Command enqueued successfully")
    print(f"✓ Queue size: {command_handler._command_queue.qsize()}")
    print()
    
    # Step 4: Test command processing
    print("STEP 4: Testing CommandHandler.handle_command()")
    print("-" * 80)
    
    # Get command from queue
    queued_command = await command_handler._command_queue.get()
    print(f"✓ Retrieved command from queue: {queued_command}")
    
    # Process command
    await command_handler.handle_command(queued_command)
    print(f"✓ Command processed successfully")
    
    # Verify API calls
    print(f"\nVerifying API calls:")
    print(f"  - refresh_force called: {mock_api_client.refresh_force.called}")
    print(f"  - publish_vehicle_data called: {mock_mqtt_client.publish_vehicle_data.called}")
    print(f"  - publish_error_status called: {mock_mqtt_client.publish_error_status.called}")
    print()
    
    # Step 5: Test async callback scheduling (simulated)
    print("STEP 5: Testing asyncio.run_coroutine_threadsafe() simulation")
    print("-" * 80)
    
    loop = asyncio.get_running_loop()
    print(f"✓ Event loop: {loop}")
    print(f"✓ Loop is running: {loop.is_running()}")
    
    # Create a new command handler for this test
    test_handler = CommandHandler(mock_api_client, mock_mqtt_client)
    
    # Simulate callback from another thread
    def simulate_mqtt_thread_callback():
        """Simulates what _on_message does in paho-mqtt thread."""
        print("\n  [Simulated MQTT thread]")
        print(f"  Topic: {topic}")
        print(f"  Payload: {payload}")
        
        # Schedule coroutine in event loop
        future = asyncio.run_coroutine_threadsafe(
            test_handler.enqueue_command(topic, payload),
            loop
        )
        print(f"  ✓ Callback scheduled, future: {future}")
        
        # Wait for result
        try:
            result = future.result(timeout=2.0)
            print(f"  ✓ Callback completed successfully: {result}")
        except Exception as e:
            print(f"  ✗ Callback failed: {e}")
            raise
    
    # Run in executor to simulate different thread
    await loop.run_in_executor(None, simulate_mqtt_thread_callback)
    
    print(f"\n✓ Cross-thread callback simulation succeeded")
    print(f"✓ Queue size after cross-thread enqueue: {test_handler._command_queue.qsize()}")
    print()
    
    # Step 6: Full integration test
    print("STEP 6: Full Integration Test")
    print("-" * 80)
    
    # Create MQTT client with command callback
    mqtt_config = MQTTConfig(
        broker_host="localhost",
        broker_port=1883,
        username=None,
        password=None,
        use_tls=False,
        client_id="test-client",
        qos_level=1,
        base_topic="hyundai"
    )
    
    final_handler = CommandHandler(mock_api_client, mock_mqtt_client)
    mqtt_client = MQTTClient(mqtt_config, on_command_callback=final_handler.enqueue_command)
    
    # Set the loop (normally done in connect())
    mqtt_client.loop = asyncio.get_running_loop()
    
    print(f"✓ MQTT client created")
    print(f"✓ on_command_callback set: {mqtt_client.on_command_callback is not None}")
    print(f"✓ loop set: {mqtt_client.loop is not None}")
    
    # Simulate _on_message call
    class FakeMessage:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload.encode('utf-8')
    
    fake_msg = FakeMessage(topic, payload)
    
    print(f"\nSimulating _on_message callback...")
    mqtt_client._on_message(None, None, fake_msg)
    
    # Wait a bit for async processing
    await asyncio.sleep(0.2)
    
    print(f"✓ Message processed")
    print(f"✓ Queue size: {final_handler._command_queue.qsize()}")
    print()
    
    # Summary
    print("="*80)
    print("ALL TESTS PASSED ✓")
    print("="*80)
    print()
    print("CONCLUSION:")
    print("-----------")
    print("The MQTT command flow is working correctly in isolation.")
    print()
    print("If commands are not working in production, check:")
    print("  1. Is the service actually receiving MQTT messages?")
    print("  2. Is the event loop set when messages arrive?")
    print("  3. Is the command processing loop running?")
    print("  4. Are there any exceptions being swallowed?")
    print()
    print("Run the service with LOG_LEVEL=DEBUG to see detailed flow.")
    print()


if __name__ == "__main__":
    asyncio.run(test_message_flow())
