""" Used for adhoc testing.  in time can create formal tests. """

import logging
import time
from lync import LyncRemote

from pynodered import node_red, NodeProperty

logging.basicConfig(filename='lync_debugging.log', level=logging.DEBUG,
                    format='%(asctime)s:%(name)s:%(levelname)s:%(funcName)s():%(message)s')
_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = '8000'
#DEFAULT_IP = '192.168.1.27'
DEFAULT_IP = 'HTD-GW-SL1'

server = LyncRemote(DEFAULT_IP)

@node_red(category="pyfuncs",
          properties=dict(address=NodeProperty("IP Address", value=DEFAULT_IP)))
def connect(node, msg):
    _LOGGER.debug("node_red connect called")
    if not server.is_connected():
        server.connect(node.address.value)
    if server.is_connected():
        # Update the states
        server.init()
        msg['payload'] = 'connected'
    else:
        msg['payload'] = 'not connected'

    return msg

@node_red(category="pyfuncs",
          properties=dict(address=NodeProperty("IP Address", value=DEFAULT_IP)))
def set_power(node, msg):
    _LOGGER.debug("node_red set_power called")
    # Topic is the zone name
    zone = msg['topic']
    if zone is None:
        _LOGGER.error("No topic name in message")
        return None
    payload = str(msg['payload'])
    if payload is '1':
        state = 'on'
    elif payload is '0':
        state = 'off'
    else:
        state = payload
    # Try to connect to the server
    tries = 3
    while not server.is_connected() and tries > 0:
        server.connect(node.address.value)
        if server.is_connected():
            server.update(zone)
        else:
            time.sleep(3)
            tries -= 1

    if not server.is_connected():
        _LOGGER.error("Can't connected to server at %s", node.address.value)
        msg['payload'] = 'not connected'
        return msg
    # Set the power state
    server.set_power(zone, state)
    # Shutdown the connection
    server.close(delay=30)
    return msg

@node_red(category="pyfuncs",
          properties=dict(address=NodeProperty("IP Address", value=DEFAULT_IP)))
def set_volume(node, msg):
    _LOGGER.debug("node_red set_volume called")
    # Topic is the zone name
    zone = msg['topic']
    if zone is None:
        _LOGGER.error("No topic name in message")
        return None
    vol = int(msg['payload'])
    if vol < 0 or vol > 100:
        _LOGGER.error("Invalid message payload %s", str(vol))
        return None
    # Try to connect to the server
    tries = 3
    while not server.is_connected() and tries > 0:
        server.connect(node.address.value)
        if server.is_connected():
            server.update(zone)
        else:
            time.sleep(3)
            tries -= 1

    if not server.is_connected():
        _LOGGER.error("Can't connected to server at %s", node.address.value)
        msg['payload'] = 'not connected'
        return msg

    # Set the volume
    server.set_volume(zone, vol)
    # Shutdown the connection
    server.close(delay=30)
    return msg
    
