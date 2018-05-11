# HTD Lync6/12 Python API
Implements a Python API for selected commands to the HTD Lync system using the serial protocol predominantly developed to provide Lync support within home-assistant.io.
The class is designed to maintain a connection to the Lync controller, and reads the state directly 
from the controller using both the websocket interface through the GW-SL1 using the LyncRemote class
and the direct serial port connection using the LyncSerial class.
Function to control capabilities implemented are:

####For a zone:
* set_power
* set_volume
* set_source
* set_mute
* get_power
* get_volume
* get_source

####Controller level
* all_on_off

test_harness.py shows some examples of usage.