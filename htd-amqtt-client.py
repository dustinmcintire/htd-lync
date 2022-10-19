import logging
import asyncio
import json
import sys
import time

from lync import LyncRemote

from amqtt.client import MQTTClient, ClientException
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2


#
# This sample shows how to subscbribe a topic and receive data from incoming messages
# It subscribes to '$SYS/broker/uptime' topic and displays the first ten values returned
# by the broker.
#

_LOGGER = logging.getLogger(__name__)

config = {
    'keep_alive': 60,
    'ping_delay': 1,
    'default_qos': 0,
    'default_retain': False,
    'auto_reconnect': False,
    'reconnect_max_interval': 30,
    'reconnect_retries': 10000,
}

DEFAULT_PORT = '8000'
DEFAULT_IP = '192.168.1.11'
#DEFAULT_IP = 'HTD-GW-SL1'

MQTT_BROKER_NAME = "eclipse-mosquitto"
MQTT_TOPIC_PREFIX = "home/speakers/"
MQTT_STATE_TOPIC = "state"
MQTT_REFRESH_TOPIC = "+/get"
MQTT_COMMAND_TOPIC = "+/set"

def state_to_json():
    return json.dumps(status)

async def update_state(client, zone, state):
    '''Post the current state'''
    json_state = json.dumps(state)
    pkt = bytearray()
    pkt.extend(json_state.encode())
    topic = MQTT_TOPIC_PREFIX + zone + "/" + MQTT_STATE_TOPIC
    await client.publish(topic, pkt, qos=QOS_2)
    _LOGGER.info("Update Sent to Topic: %s", topic)

def lync_update(lync, zone):
    # Try to connect to the lync
    tries = 3
    while not lync.is_connected() and tries > 0:
        lync.connect()
        if lync.is_connected():
            lync.update(zone)
        else:
            time.sleep(3)
            tries -= 1


def set_power(lync, zone, state):
    # Topic is the zone name
    if state == '1':
        state = 'on'
    elif state == '0':
        state = 'off'
    # Try to connect to the lync
    lync_update(lync, zone.lower())

    if not lync.is_connected():
        _LOGGER.error("Can't connected to lync")
        return
    # Set the power state
    lync.set_power(zone.lower(), state.lower())
    # Shutdown the connection
    lync.close(delay=30)

def set_volume(lync, zone, volume):
    vol = int(volume)
    if vol < 0 or vol > 100:
        _LOGGER.error("Invalid message payload %s", str(vol))
        return None
    # Try to connect to the lync
    lync_update(lync, zone)

    if not lync.is_connected():
        _LOGGER.error("Can't connected to lync")
        return 

    # Set the volume
    lync.set_volume(zone.lower(), vol)
    # Shutdown the connection
    lync.close(delay=30)

def set_mute(lync, zone, state):
    # Topic is the zone name
    if state == True or state == 1:
        state = 'on'
    elif state == False or state == 0:
        state = 'off'
    mute = str(state)
    if mute != 'on' and mute != 'off':
        _LOGGER.error("Invalid mute message payload %s state %s", mute, str(state))
        return None
    # Try to connect to the lync
    lync_update(lync, zone)

    if not lync.is_connected():
        _LOGGER.error("Can't connected to lync")
        return 

    # Set the mute value
    lync.set_mute(zone.lower(), mute.lower())
    # Shutdown the connection
    lync.close(delay=30)

async def mqtt_coro():
    # Create websocket lync connection
    lync = LyncRemote(DEFAULT_IP)
    # Connect to the Lync
    lync.connect()
    if not lync.is_connected():
        _LOGGER.warning("Can't connect to the Lync server")
        return
    else:
        lync.init()
    # Connect to MQTT Broker
    try:
        C = MQTTClient(config=config)
        await C.connect(uri='mqtt://' + MQTT_BROKER_NAME + '/', cleansession=False)
        await C.subscribe([
            (MQTT_TOPIC_PREFIX + MQTT_COMMAND_TOPIC, QOS_0),
            (MQTT_TOPIC_PREFIX + MQTT_REFRESH_TOPIC, QOS_0),
        ])
        _LOGGER.info("Subscribed")
    except ClientException as ce:
        _LOGGER.error("Connection failed: %s" % ce)
    # Post the current state
    #json_state = state_to_json()
    #pkt = bytearray()
    #pkt.extend(json_state.encode())
    #message = await C.publish(MQTT_STATE_TOPIC, pkt, qos=QOS_0)
    _LOGGER.info("Update Sent")
    while True:
        try:
            # Get next command packet
            message = await C.deliver_message()
            packet = message.publish_packet
            data = json.loads(packet.payload.data.decode())
            _LOGGER.info("%s => %s" % (packet.variable_header.topic_name, data))
            # Take action
            for item in data:
                if not 'zone' in item:
                    _LOGGER.warning("No name in item")
                else:
                    # Look up the name as a speaker identifier
                    _LOGGER.debug("Found zone: %s" % item['zone'])
                    # Check for command types directives 
                    if not 'directive' in item:
                        _LOGGER.warning("No directive in the message")
                    else:
                        # Parse directive types
                        if item['directive'] == "TurnOn":
                            set_power(lync, item['zone'], item['powerState'])
                        if item['directive'] == "TurnOff":
                            set_power(lync, item['zone'], item['powerState'])
                        if item['directive'] == "SetVolume":
                            set_volume(lync, item['zone'], item['volume'])
                        if item['directive'] == "SetMute":
                            set_mute(lync, item['zone'], item['muted'])
                        if item['directive'] == "SelectInput":
                            _LOGGER.info("Input select not implemented")

            # Wait for update to apply
            time.sleep(1)
            # Refetch the state and end it back
            for item in data:
                if 'zone' in item:
                    state = lync.get_zone_info(item['zone'])
                    _LOGGER.debug("Update state %s" % state)
                    #update_state(C, item['zone'], state)
                    json_state = json.dumps(state)
                    pkt = bytearray()
                    pkt.extend(json_state.encode())
                    topic = MQTT_TOPIC_PREFIX + item['zone'] + "/" + MQTT_STATE_TOPIC
                    await C.publish(topic, pkt, qos=QOS_2)
                    _LOGGER.info("Update Sent to Topic: %s", topic)

        except ClientException as ce:
            _LOGGER.error("Client exception: %s" % ce)
            time.sleep(TIMEOUT_DELAY)


if __name__ == '__main__':

    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    #logging.basicConfig(level=logging.DEBUG, format=formatter)
    asyncio.get_event_loop().run_until_complete(mqtt_coro())
    pi.stop() # Disconnect from local Pi.
