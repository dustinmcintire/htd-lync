"""
Home Theater Direct Lync interface for Lync6 & Lync12.  
Copyright (c) 2018 Dustin McIntire <https://github.com/dustinmcintire/

Based on documentation from SDK(3G) version 2.0d which defines the serial port protocol.  
The API's for web authentication and websocket interface to the (W)GW-SL1 were reverse engineered.
This code is based on the Russound RNT module from Neil Lathwood which core the copyright:

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.  Please see LICENSE.txt at the top level of
the source code distribution for details.
"""

import logging
import threading
import time
import requests
import websocket
import serial
import binascii

# lync serial header
LYNC_HEADER = b'\x02\x00'
# Seconds to wait for normal responses
LYNC_SOCKET_TIMEOUT = 1
# Seconds to wait for complete refresh response
LYNC_REFRESH_TIMEOUT = 3
# Intitial open timeout
LYNC_WS_CONNECT_TIMEOUT = 5
# Total number of zones supported per lync system
LYNC_MAX_ZONES = 16

_LOGGER = logging.getLogger(__name__)

# Commands to the Lync
# command, (id, length, args)
LYNC_TX_CMDS = {
    'repeat loop' : ( 0x01, 1, { 'on' : 0xff, 'off' : 0x00 } ),
    'zone'        : ( 0x04, 1, { 'all on' : 0x55, 
                             'all off' : 0x56, 
                             'power on' : 0x57, 
                             'power off' : 0x58, 
                             'mute on' : 0x1E, 
                             'mute off' : 0x1F,
                             'dnd on' : 0x59,
                             'dnd off' : 0x5a,
                             'input1' : 0x10,
                             'input2' : 0x11,
                             'input3' : 0x12,
                             'input4' : 0x13,
                             'input5' : 0x14,
                             'input6' : 0x15,
                             'input7' : 0x16,
                             'input8' : 0x17,
                             'input9' : 0x18,
                             'input10' : 0x19,
                             'input11' : 0x1A,
                             'input12' : 0x1B,
                             'input13' : 0x63,
                             'input14' : 0x64,
                             'input15' : 0x65,
                             'input16' : 0x66,
                             'input17' : 0x67,
                             'input18' : 0x68,
                             'intercom' : 0x69}),
    'query all zones' : (0x05, 1, { 'none' : 0 }), 
    'zone name' : (0x06, 12, { 'none' : 0 }),
    'source name' : (0x07, 12, { 'none' : 0 }),
    'query id' : (0x08, 1, { 'none' : 0 }),
    'query all zones' : (0x0C, 1, { 'none' : 0 }), # is this the same as 0x05?
    'query zone name' : (0x0D, 1, { 'none' : 0 }),
    'query zone source name' : (0x0E, 1, { 'none' : 0 }),
    'query host firmware version' : (0x0F, 1, { 'none' : 0 }),
    'query volume value' : (0x10, 1, { 'none' : 0 }),
    'volume setting control' : (0x15, 1, (0 , 0x80)),
    'balance setting control' : (0x16, 1, (18 , 0x92)),
    'treble setting control' : (0x17, 1, (10 , 0x8A)),
    'bass setting control' : (0x18, 1, (10 , 0x8A)),
    'set echo' : (0x19, 1, {'off' : 0, 'on' : 1 }),
    'set audio to default' : (0x1C, 1, { 'none' : 0 }),
    'set name to default' : (0x1D, 1, { 'none' : 0 })
    }

# Commands from the Lync
# id, (name, length, args)
LYNC_RX_CMDS = {
    0x02 : ('undefined', 1, { }),
    0x05 : ('zone status', 9, { 'power' : 1<<0, 
                                'mute' : 1<<1,
                                'dnd' : 1<<2,
                                'door' : 1<<5 } ),
    0x06 : ('keypad exists', 9, { }),
    0x09 : ('mp3 play end', 1, { }),
    0x0C : ('zone source name', 12, { }),
    0x0D : ('zone name', 13, { }),
    0x0E : ('source name', 13, { }),
    0x11 : ('mp3 file name', 64, { }),
    0x12 : ('mp3 artist name', 64, { }),
    0x13 : ('mp3 on', 1, { }),
    0x14 : ('mp3 off', 17, { }),
    0x1b : ('undefined', 9, { }),
    }

class LyncBase:
    '''class providing basic processing for HTD Lync commands'''
    def __init__(self):
        # Default initializations
        self.zone_info = [{ 'name' : 'unknown' ,
                            'source' : 'unknown',
                            'source_list' : {},
                            'exists' : 'no',
                            'keypad' : 'no',
                            'power' : 'off',
                            'mute' : 'off',
                            'dnd' : 'off',
                            'volume' : 0,
                            'treble' : 0,
                            'bass' : 0,
                            'balance' : 0 } for x in range(LYNC_MAX_ZONES) ] 
        self.zone_lookup = { 'all' : 0 }
        self.source_info =  [dict() for x in range(LYNC_MAX_ZONES)]
        self.mp3_status = { 'state' : 'off',
                            'file' : 'unknown',
                            'artist' : 'unkown' }

    def __signed_byte(self, c):
        unsigned = ord(c.to_bytes(1,byteorder='little'))
        signed = unsigned - 256 if unsigned > 127 else unsigned
        return signed

    def __parse_command(self, zone, cmd, arg_info, data):
        if cmd == 'keypad exists':
            # this is zone 0 with all zone data
            # second byte is zone 0-7
            for i in range(8):
                if data[1] & (1<<i):
                    self.zone_info[i]['exists'] = 'yes'
                else:
                    self.zone_info[i]['exists'] = 'no'
            # third byte is keypad 0-7
            for i in range(8):
                if data[2] & (1<<i):
                    self.zone_info[i]['keypad'] = 'yes'
                else:
                    self.zone_info[i]['keypad'] = 'no'
            # third byte is keypad 0-7
            # fourth byte is zone 8-15 
            for i in range(8):
                if data[3] & (1<<i):
                    self.zone_info[i+8]['exists'] = 'yes'
                else:
                    self.zone_info[i+8]['exists'] = 'no'
            # fifth byte is keypad 8-15 
            for i in range(8):
                if data[4] & (1<<i):
                    self.zone_info[i+8]['keypad'] = 'yes'
                else:
                    self.zone_info[i+8]['keypad'] = 'no'
        elif cmd == 'zone status':
            # first byte is status bits
            if data[0] & arg_info['power']:
                self.zone_info[zone]['power'] = 'on'
            else:
                self.zone_info[zone]['power'] = 'off'
            if data[0] & arg_info['mute']:
                self.zone_info[zone]['mute'] = 'on'
            else:
                self.zone_info[zone]['mute'] = 'off'
            if data[0] & arg_info['dnd']:
                self.zone_info[zone]['dnd'] = 'on'
            else:
                self.zone_info[zone]['dnd'] = 'off'
            # fifth byte is input
            self.zone_info[zone]['source'] = data[4]
            # sixth byte is volume
            self.zone_info[zone]['volume'] = self.__signed_byte(data[5])
            # seventh byte is treble
            self.zone_info[zone]['treble'] = self.__signed_byte(data[6])
            # eigth byte is bass
            self.zone_info[zone]['bass'] = self.__signed_byte(data[7])
            # ninth byte is balance
            self.zone_info[zone]['balance'] = self.__signed_byte(data[8])
        elif cmd == 'zone source name':
            # remove the extra null bytes
            self.source_info[zone] = data[0:11].decode().rstrip('\0')
        elif cmd == 'zone name':
            name=data[0:11].decode().rstrip('\0')
            self.zone_info[zone]['name'] = name
            self.zone_lookup[name] = zone
        elif cmd == 'source name':
            source = data[11]
            name = data[0:10].decode().rstrip('\0')
            self.zone_info[zone]['source_list'][source] = name
            self.source_info[zone][name] = source
        elif cmd == 'mp3 on':
            self.mp3_status['state'] = 'on'
        elif cmd == 'mp3 off':
            self.mp3_status['state'] = 'off'
        elif cmd == 'mp3 file name':
            self.mp3_status['file'] = data.decode().rstrip('\0')
        elif cmd == 'mp3 artist name':
            self.mp3_status['artist'] = data.decode().rstrip('\0')
        else:
            _LOGGER.info("Not processing packet type: %s", cmd)
    
    def process_command(self, c):
        """ Process the lync frame data.  Search for the frame sync bytes and process one 
            frame from the buffer.  Return the start of the next frame. """
        # start with search for command header and Id the command
        global LYNC_HEADER
        # not enough data
        if(len(c) < len(LYNC_HEADER) + 4):
            return 0
        start = c.find(LYNC_HEADER)
        if start < 0:
            return len(c)
        if start != 0:
            _LOGGER.debug("Bad sync buffer: %s", str(binascii.hexlify(c)))
        # offsets to packet data
        zone_idx = start + len(LYNC_HEADER)
        cmd_idx = zone_idx + 1
        data_idx = cmd_idx + 1
        # not enough data, wait for more
        if(len(c) < data_idx):
            return 0
        # Skip over bad command
        # return the minimum packet size for resync
        if c[cmd_idx] not in LYNC_RX_CMDS:
            _LOGGER.error("Invalid command value 0x%x", c[cmd_idx])
            #_LOGGER.debug("Packet buffer: %s", str(binascii.hexlify(c[0:20])))
            return start + len(LYNC_HEADER)
        zone = int(c[zone_idx])
        cmd_info = LYNC_RX_CMDS[c[cmd_idx]]
        cmd_name = cmd_info[0]
        if cmd_name is 'unknown':
            _LOGGER.info("Unknown packet command: %02x", int(c[cmd_idx]))
            #_LOGGER.debug("Packet buffer: %s", str(binascii.hexlify(c[0:20])))
            return start + len(LYNC_HEADER)
        cmd_length = cmd_info[1]
        # not enough data, wait for more
        if(len(c) < data_idx+cmd_length):
            return 0
        # process the content to the current state
        frame=c[start:start + len(LYNC_HEADER) + 2 + cmd_length]
        csum=c[start + len(LYNC_HEADER) + 2 + cmd_length]
        fsum = sum(frame) & 0xff
        if fsum != csum:
            _LOGGER.info("Bad checksum %02x != %02x", fsum, csum)
            #_LOGGER.debug("Frame buffer: %s", str(binascii.hexlify(frame)))
            #_LOGGER.debug("Packet buffer: %s", str(binascii.hexlify(c[0:20])))
        self.__parse_command(zone, cmd_name, cmd_info[2], c[data_idx:data_idx+cmd_length])
        return start + len(LYNC_HEADER) + 2 + cmd_length + 1

    def create_send_message(self, cmd, zone_name, val=None):
        """ send a single command """
        def gen_frame(cmd=0, zone=0, args=b'\x00'):
            cmd_id=LYNC_TX_CMDS[cmd][0]
            frame = bytearray()
            frame.extend(LYNC_HEADER)
            frame.extend(zone.to_bytes(1,byteorder='little'))
            frame.extend(cmd_id.to_bytes(1,byteorder='little'))
            frame.extend(args)
            # fill
            s = sum(frame)
            frame.extend(s.to_bytes(1,byteorder='little'))
            _LOGGER.debug("Sending %s", str(binascii.hexlify(frame)))
            return frame
        
        # Verify the command name
        if not cmd in LYNC_TX_CMDS:
            _LOGGER.info("Invalid command name %s", cmd)
            return
        # Find the zone number from name
        if not zone_name in self.zone_lookup:
            _LOGGER.info("Zone %s does not exist in the list", zone_name)
            return
        else:
            zone_number = self.zone_lookup[zone_name]
        arg=b'\x00'
        # Generate the arguments
        if LYNC_TX_CMDS[cmd][1] > 1:
            # insert string with zero pad of proper size
            arg=bytearray(LYNC_TX_CMDS[cmd][1])
            arg[0:len(val)]=val
        elif 'none' in LYNC_TX_CMDS[cmd][2]:
            # no arguments
            pass
        elif isinstance(val,int):
            # add the key to the argument and use the value as the offset
            (offset, scale) = LYNC_TX_CMDS[cmd][2]
            arg=(val - offset + scale).to_bytes(1,byteorder='little')
        elif isinstance(val,str): 
            if not val in LYNC_TX_CMDS[cmd][2]:
                _LOGGER.error("Command argument is not valid %s", val)
                return
            else:
                # Convert string to command byte value
                arg=LYNC_TX_CMDS[cmd][2][val].to_bytes(1,byteorder='little') 
        else:
            _LOGGER.error("Unknown argument type %s for command %s", type(arg), cmd)
            return
        return gen_frame(cmd, zone_number, arg)

    def zone_to_num(self, zone):
        """ return the zone number from name or id
            :param zone: The zone id as a 1 based number or zone name.
        """
        #if zone is given by string name then convert to the number
        if isinstance(zone,str):
            if not zone in self.zone_lookup:
                # assume string integer
                return int(zone)
            else:
                return self.zone_lookup[zone]
        else:
            return zone

    def zone_to_name(self, zone):
        """ return the zone name from number or id
            :param zone: The zone id as a 1 based number or zone name.
        """
        #if zone is given by string name then convert to the number
        if isinstance(zone,str):
            if not zone in self.zone_lookup:
                # try again as string integer
                return self.zone_info[int(zone)]['name']
            else:
                return zone
        else:
            return self.zone_info[zone]['name']

    def source_to_num(self, zone, source):
        """ return the zone information from the state cache
            :param zone: The zone id as a 1 based number or zone string name.
            :param source: The source name as a 0 based number or source string name.
        """
        zn = self.zone_to_num(zone)
        if isinstance(source,str):
            if not source in self.source_info[zn]:
                # try again as string integer
                return int(source)
            return self.source_info[zn][source]
        else:
            return source

    def get_zone_info(self, zone='all'):
        """ return the zone information from the state cache
            :param zone: The zone id as a 1 based number or zone name.
        """
        if self.zone_to_name(zone) == 'all':
            return self.zone_info[1:]
        else:
            return self.zone_info[self.zone_to_num(zone)]

    def get_source_info(self, zone='all'):
        """ return the sources list for a zone from the state cache
            :param zone: The zone id as a 0 based number or zone name.
        """
        if self.zone_to_name(zone) == 'all':
            return self.source_info
        else:
            return self.zone_info[self.zone_to_num(zone)]['source_list']

    def set_power(self, zone, state):
        """ Switch power on/off to a zone
        :param zone: The zone to be controlled. Expect a 1 based number.
        :param power: off or on
        """
        _LOGGER.debug("zone=%s, change power to %s", zone, state)
        power_state = 'power ' + state
        return self.create_send_message('zone', self.zone_to_name(zone), power_state)

    def set_volume(self, zone, volume):
        """ Set volume for zone to specific value.
        :param zone: The zone to be controlled. Expect a 1 based number or zone name.
        :param volume: The volume as a 0-100 decimal.
        Converts 0 to 100 to a -60 to 0 scale for lync
        """
        scaled = int(((60/100) * volume) - 60)
        _LOGGER.debug("zone= %s, change volume to %s (%s)", zone, volume, scaled)
        return self.create_send_message('volume setting control', 
                                        self.zone_to_name(zone), scaled)

    def set_source(self, zone, source):
        """ Set source for a zone - 0 based value for source or name """
        _LOGGER.debug("zone= %s change source to %s.", zone, source)
        # generate the inputx argument value as a string
        arg = 'input' + str(self.source_to_num(zone, source))
        return self.create_send_message('zone', self.zone_to_name(zone), arg)

    def all_on_off(self, state):
        """ Turn all zones on or off
        :param power: off or on
        """
        _LOGGER.debug("All on/off to %s.", state)
        power_state = 'all ' + state
        return self.create_send_message('zone', 'all', power_state)

    def set_mute(self, zone, state):
        """ Set mute on/off for a zone
        :param mute: 0 = off, 1 = on
        """
        _LOGGER.debug("mute on/off to %s.", state)
        mute_state = 'mute ' + state
        return self.create_send_message('zone', self.zone_to_name(zone), mute_state)

    def get_power(self, zone):
        """ Gets the power status as on or off """
        return self.get_zone_info(zone)['power']

    def get_source(self, zone):
        """ Gets the selected source as a name and number
        :param return a list (name, number)
        """
        source = self.get_zone_info(zone)['source']
        name = self.get_zone_info(zone)['source_list'][source]
        return (name, source)

    def get_volume(self, zone):
        """ Gets the volume level which needs to be scaled to the range of 0..100 -
        """
        volume_level = self.get_zone_info(zone)['volume']
        if volume_level is not None:
            volume_level = ((volume_level/-60) * 100)
        return volume_level

    def print_state(self):
        print("zone status")
        print(self.zone_info)
        print("zone names")
        print(self.zone_lookup)
        print("source info")
        print(self.source_info)

class LyncSerial(LyncBase):
    """class to operate the HTD lync serial API directly using the UART control port.
       This does not require the (W)GW-SL1 Valet capability"""
    def __init__(self, port='/dev/ttyUSB0', baud=38400):
        self._tty=port
        self._baud=baud
        self._buf = bytearray() # initialized empty buffer
        super().__init__()

    def connect(self, tty=None, baud=None):
        """ Connect to the serial port """
        self._tty = tty if tty is not None else self._tty
        self._baud = baud if baud is not None else self._baud
        self._ser = serial.Serial(self._tty, self._baud)  # open serial port
        self._ser.open()
        if not self._ser.is_open:
            _LOGGER.error("Error trying to open serial port %s", self._tty)
            return False
        self._wst = threading.Thread(target=self.__ser_run_forever)
        self._wst.daemon = True
        self._wst_run = True
        self._wst.start()
        _LOGGER.info("Successfully opened serial port %s", self._tty)
        return True

    def is_connected(self):
        """ Check we are connected """
        return self._ser.is_open

    def set_power(self, zone, power):
        self._ser.write(super().set_power(zone,power))

    def set_volume(self, zone, volume):
        self._ser.write(super().set_volume(zone,volume))

    def set_source(self, zone, source):
        self._ser.write(super().set_source(zone,source))

    def all_on_off(self, power):
        self._ser.write(super().all_on_off(power))

    def set_mute(self, zone, mute):
        self._ser.write(super().set_mute(zone,mute))

    def __send_command(self, cmd, zone_name, val=None):
        """ send a single command """
        self._ser.write(super().send_command(cmd, zone_name, val))

    def __ser_run_forever(self):
        self._buf = bytearray()
        while True:
            self._buf = self._ser.read()
        _LOGGER.error("Exiting reader thread...")

    def __exit__(self, exception_type, exception_value, traceback):
        """ Close connection to port """
        try:
            self._ser.close()
            _LOGGER.info("Closed connection to Lync %s", self._tty)
        except self._ser.is_open:
            _LOGGER.error("Couldn't disconnect serial port")

class LyncRemote(LyncBase):
    """class to operate the HTD lync serial API using the ethernet/wifi gateway
       this uses a websocket interface to forward serial data to and from the UART"""

    def __init__(self, hostname, port='8000', username='admin', password='lev3s'):
        self._hostname=hostname
        self._port=int(port)
        self._username=username
        self._password=password
        self._timeout = LYNC_SOCKET_TIMEOUT
        self._lock = threading.Lock()   # Used to ensure only one thread sends commands
        self._buf = bytearray() # initialized empty buffer
        super().__init__()

    def connect(self, host=None, port=None):
        """ Connect to the GW-SL1 gatway """
        self._hostname = host if host is not None else self._hostname
        self._port = port if port is not None else self._port
        # Do the http basic auth
        r = requests.get('http://' + self._hostname + '/login.cgi', 
                              auth=requests.auth.HTTPBasicAuth(self._username, self._password))
        if r.status_code != requests.codes.ok:
            _LOGGER.error("Error trying to authenticate to HTD controller.")
            _LOGGER.error(r.status_code)
            return False
        _LOGGER.info("Successfully authenticated to HTD Lync at %s", self._hostname)

        # open the websocket and run in a thread
        self._ws = websocket.WebSocketApp('ws://' + self._hostname + ':' + str(self._port) + '/',
                              on_message = self.__on_message,
                              on_error = self.__on_error,
                              on_close = self.__on_close)
        self._wst = threading.Thread(target=self.__ws_run_forever)
        self._wst.daemon = True
        self._wst_run = True
        self._wst.start()

        timeout = LYNC_WS_CONNECT_TIMEOUT
        while not self._ws.sock.connected and timeout:
            time.sleep(1)
            timeout -= 1

        if not self._ws.sock.connected:
            _LOGGER.error("Error trying to connect to Lync websocket.")
            _LOGGER.error(self._ws.sock.status)
            self._wst_run = False
            return False
        _LOGGER.info("Successfully connected to HTD Lync on %s:%s", self._hostname, self._port)

        # Get the latest status
        self.update()
        return True

    def is_connected(self):
        """ Check we are connected """
        return self._ws.sock.connected

        # Call a thread to refresh the state
    def refresh_zone(self, zone=0):
        # Set longer timeout for multiple responses
        zn = super().zone_to_name(zone)
        if zn is 'all':
            orig = self._timeout
            self._timeout = LYNC_REFRESH_TIMEOUT;
            self.__send_command('query all zones', zn)
            self._timeout = orig
        else:
            self.send('query all zones', zn)

    def update(self):
        self.refresh_zone('all')

    def set_power(self, zone, power):
        self._ws.send(super().set_power(zone,power))

    def set_volume(self, zone, volume):
        self._ws.send(super().set_volume(zone,volume))

    def set_source(self, zone, source):
        self._ws.send(super().set_source(zone,source))

    def all_on_off(self, power):
        self._ws.send(super().all_on_off(power))

    def set_mute(self, zone, mute):
        self._ws.send(super().set_mute(zone,mute))

    # Websocket command handlers
    def __on_message(self, message):
        self._buf.extend(message)
        while True:
            # process one command from the byte stream and pop it off
            frame_len = super().process_command(self._buf)
            if frame_len <= 0:
                break
            del self._buf[0:frame_len]

    def __on_error(self, error):
        _LOGGER.info("WS error %s", error)
    
    def __on_close(self):
        _LOGGER.info("WS closed")

    def __ws_run_forever(self):
        while self._wst_run:
            self._ws.run_forever()
        _LOGGER.error("Exiting WS thread...")

    def __send_command(self, cmd, zone_name, val=None):
        """ send a single command """
        self._ws.send(super().create_send_message(cmd, zone_name, val))

    def __exit__(self, exception_type, exception_value, traceback):
        """ Close connection to gateway """
        try:
            self._wst_run = False
            self._ws.close()
            _LOGGER.info("Closed connection to Lync GW on %s:%s", self._hostname, self._port)
        except self._ws.socket.error as msg:
            _LOGGER.error("Couldn't disconnect")
            _LOGGER.error(msg)


