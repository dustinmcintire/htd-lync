""" Used for adhoc testing.  in time can create formal tests. """

import logging
from lync import LyncRemote
import time

IP_ADDRESS = '192.168.1.9'
PORT = '8000'
logging.basicConfig(filename='lync_debugging.log', level=logging.DEBUG,
                    format='%(asctime)s:%(name)s:%(levelname)s:%(funcName)s():%(message)s')
_LOGGER = logging.getLogger(__name__)


def test1():
    """ Test with int zone ID"""
    x = LyncRemote(IP_ADDRESS, PORT)
    x.connect()
    time.sleep(3)
    zone = 'Office'
    print("Turn off zone", zone)
    x.set_power(zone, 'off')
    x.update()
    time.sleep(3)
    print("Power status zone", str(zone), "=", x.get_power(zone))

    print("Turn on zone", zone)
    x.set_power(zone, 'on')
    x.update()
    time.sleep(3)
    print("Power status zone", str(zone), "=", x.get_power(zone))

    print("Source on zone", str(zone), "is", x.get_source(zone)[0])
    x.set_source(zone, 15)
    x.update()
    time.sleep(3)
    print("Source on zone", str(zone), "is", x.get_source(zone)[0])
    x.set_source(zone, 16)
    x.update()
    time.sleep(3)
    print("Source on zone", str(zone), "is", x.get_source(zone)[0])

    print("Volume on zone", str(zone), "is", x.get_volume(zone))
    x.set_volume(zone, 20)
    x.update()
    time.sleep(3)
    print("Volume on zone", str(zone), "is", x.get_volume(zone))

def test2():
    """ Test with string zone ID"""
    x = LyncRemote(IP_ADDRESS, PORT)
    x.connect()
    zone = '1'
    print("Turn off zone", zone)
    x.set_power(zone, 'off')
    print("Power status zone", str(zone), "=", x.get_power(zone))

    print("Turn on zone", zone)
    x.set_power(zone, 'on')
    print("Power status zone", str(zone), "=", x.get_power(zone))

    print("Source on zone", str(zone), "is", x.get_source(zone))
    x.set_source(zone, 16)
    print("Source on zone", str(zone), "is", x.get_source(zone))

    print("Volume on zone", str(zone), "is", x.get_volume(zone))
    x.set_volume(zone, 20)
    print("Volume on zone", str(zone), "is", x.get_volume(zone))

def test3():
    """ All zones on, change sound and then all off """

    x = LyncRemote(IP_ADDRESS, PORT)
    x.connect()
    x.is_connected()
    for zone in range(1, 5):
        x.set_power(zone, 'on')
        print("Power status zone", str(zone), "is", x.get_power(zone))

    for zone in range(1,5):
        x.set_volume(zone, 34)
        print("Volume on zone", str(zone), "is", x.get_volume(zone))

    time.sleep(5)
    for zone in range(1,5):
        x.set_power(zone, 'off')


def test4():
    x = LyncRemote(IP_ADDRESS, PORT)
    x.connect()
    x.is_connected()
    zone = 1

    print("For zone 1, read power status, turn zone on and read volume and source")
    _LOGGER.debug("Zone %s power status=%s", str(zone), x.get_power('1', zone))
    x.set_power('1', zone, '1')
    _LOGGER.debug("Zone %s power status=%s", str(zone), x.get_power('1', zone))
    _LOGGER.debug("Zone %s source=%s", str(zone), x.get_source('1',zone))
    _LOGGER.debug("Zone %s volume=%s", str(zone), x.get_volume('1',zone))

    print("Set volume to 35 and source to 2nd source")
    x.set_volume('1', zone, 35)
    x.set_source('1', zone, 1)

    print("Read the source and volume levels from the controller")
    _LOGGER.debug("Zone %s source=%s", zone, x.get_source('1',zone))
    _LOGGER.debug("Zone %s volume=%s", zone, x.get_volume('1',zone))

    time.sleep(2)
    x.set_power('1', zone, '0')
    _LOGGER.debug("Zone %s source=%s", zone, x.get_source('1',zone))


#Run test 1...
test1()