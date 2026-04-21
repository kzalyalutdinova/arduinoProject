import socket
import struct
# import asyncio
from typing import List, Optional, Dict
from configparser import ConfigParser
from devices.slave_device import SlaveDevice
from utils.modbus_request import ModbusRequest

class ArduinoBoard:
    HEADER = b'h2ub.v3:'
    SECTION_PREFIX = 'ModbusUDP'

    def __init__(self, config: ConfigParser, slaves: Dict[int, SlaveDevice]):
        if not config.has_section(self.SECTION_PREFIX):
            raise ValueError(f"Section '{self.SECTION_PREFIX}' not found in config")
        
        self.arduino_ip = config.get(self.SECTION_PREFIX, 'arduino_ip')
        self.udp_port_send = int(config.get(self.SECTION_PREFIX, 'port_send_udp'))
        self.udp_port_listen = int(config.get(self.SECTION_PREFIX, 'port_listen_udp'))
        self.name = config.get(self.SECTION_PREFIX, 'device')
        
        self.slaves = slaves

        self.mask = self._read_analog_pins()
        self.drw_mask = 0

        self.thermo_couples_values: List[float] = []
        self.rele_position: int = 0         # Состояния реле: 0 - выключено, 1 -включено


        # analog_pins = config.get(self.SECTION_PREFIX, 'analog_pins').strip().upper()
        # self.mask = self._parse_analog_pins(analog_pins.split('A')[1:])

        # modbus команды
        self.MODBUS_READ = int(config.get(self.SECTION_PREFIX, 'cmd_read_sev'), 0)
        self.MODBUS_WRITE = int(config.get(self.SECTION_PREFIX, 'cmd_write_one'), 0)

        # команды для управления реле
        self.CMD_TOGGLE_RELE = int(config.get(self.SECTION_PREFIX, 'cmd_toggle_rele'))

        # команда для управления ДРВ
        self.CMD_DRW = int(config.get(self.SECTION_PREFIX, 'cmd_drw'))

        # дополнительные команды
        self.CMD_READ_ANALOG_PINS = int(config.get(self.SECTION_PREFIX, 'cmd_read_analog_pins'))
        self.CMD_READ_TEMPERATURES = int(config.get(self.SECTION_PREFIX, 'cmd_read_temps'))
        self.CMD_READ_FREQUENCES = int(config.get(self.SECTION_PREFIX, 'cmd_read_freqs'))
        self.CMD_MODBUS_REQUEST = int(config.get(self.SECTION_PREFIX, 'cmd_modbus_command'))
        self.CMD_READ_THERMO = int(config.get(self.SECTION_PREFIX, 'cmd_read_thermo'))
        self.CMD_CHECK_RELE = int(config.get(self.SECTION_PREFIX, 'cmd_check_rele'))

    def _read_analog_pins(self):
        analog_pins = []
        for slave_id in self.slave_ids:
            s = self.slaves[slave_id].analog_pin_signal[1:]
            t = self.slaves[slave_id].analog_pin_temp[1:]
            analog_pins.append(s)
            analog_pins.append(t)
        
        mask = self._parse_analog_pins(analog_pins)
        return mask
    
    def _parse_analog_pins(self, analog_pins: List[str]):
        mask = 0
        for i in analog_pins:
            try: 
                pin = int(i)
                if 0 <= pin <= 7:
                    mask |= (1 << pin)  # Устанавливаем соответствующий бит в 1
                else:
                    raise ValueError
            except ValueError:
                print(f"Warning: Invalid pin value '{i}', skipped")
        # print(bytearray(mask))
        return mask
    
    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock

    def _custom_commands_to_list(self):
        custom_commands = [self.CMD_READ_ANALOG_PINS,
                           self.CMD_READ_TEMPERATURES, 
                           self.CMD_READ_FREQUENCES,
                           self.CMD_MODBUS_REQUEST,
                           self.CMD_READ_THERMO,
                           self.CMD_CHECK_RELE
                        ]
        
        return custom_commands
    
    @property
    def slave_ids(self) -> List[int]:
        return list(self.slaves.keys())
    
    def get_slave(self, slave_id: int) -> Optional[SlaveDevice]:
        if slave_id not in self.slave_ids:
            raise KeyError(f'No such slave id {slave_id}')
        
        return self.slaves.get(slave_id)
    
    def send(self, payload: bytes) -> bool:
        try:
            sock = self._create_socket()
            sock.sendto(payload, (self.arduino_ip, self.udp_port_send))
            # print(f"[UDP→] {payload.hex()}")
            return True
        except socket.error as e:
            print(f"[UDP ERROR] {e}")
            return False
        finally:
            sock.close()
    
    def build_modbus_request(self, request: ModbusRequest, if_header=False):
        payload = self.HEADER if if_header else b''

        payload += struct.pack('<H', self.CMD_MODBUS_REQUEST)
        payload += request.to_bytes()

        return payload
    
    def build_custom_request(self, cmd, if_header=False):
        if cmd not in self._custom_commands_to_list():
            raise ValueError(f'Command {cmd} is not in the list ({self._custom_commands_to_list()})')
        
        if not self.slaves:
            raise ValueError(f'Arduino Board does not have any slaves')
        
        payload = self.HEADER if if_header else b''
        
        payload += struct.pack('<HH', cmd, len(self.slaves))
        for slave_id in self.slave_ids:
            payload += struct.pack('<B', slave_id)
        
        return payload

    def build_apins_read_request(self, if_header=False):
        payload = self.HEADER if if_header else b''

        payload += struct.pack('<H', self.CMD_READ_ANALOG_PINS)
        payload += struct.pack('<B', self.mask)

        return payload
    
    def build_drw_request(self, if_header=False):
        payload = self.HEADER if if_header else b''

        payload += struct.pack('<H', self.CMD_DRW)
        payload += struct.pack('<B', self.drw_mask)

        return payload
    
    def build_read_thermo_request(self, if_header=False):
        payload = self.HEADER if if_header else b''
        payload += struct.pack('<H', self.CMD_READ_THERMO)

        return payload
    
    def build_rele_toggle_request(self, if_header=False):
        # self.rele_position = 0 if self.rele_position == 1 else 1

        payload = self.HEADER if if_header else b''
        payload += struct.pack('<H', self.CMD_TOGGLE_RELE)
        payload += struct.pack('<B', self.rele_position)

        return payload
    
    def build_rele_check_request(self, if_header=False):
        payload = self.HEADER if if_header else b''
        payload += struct.pack('<H', self.CMD_CHECK_RELE)

        return payload

    def build_b2hv3_packet(self, if_thermo=False):
        payload = self.build_custom_request(self.CMD_READ_FREQUENCES, if_header=True)

        if if_thermo:
            payload += self.build_read_thermo_request()
            payload += self.build_rele_check_request()
        
        payload += self.build_apins_read_request()

        return payload
    
    def build_mbETA_request(self, slave_id:int) -> bytes:
        reg = self.get_slave(slave_id).read_regs[0]

        modbus_request = ModbusRequest(
                                function=self.MODBUS_READ,
                                slave_id=slave_id,
                                register_address=reg,
                                value=1)
        
        payload = self.build_modbus_request(modbus_request, if_header=True)
        return payload
    
    def build_setFrequency_request(self, slave_id:int, freq_value:float) -> bytes:
        if freq_value > 50:
            freq_value = 50
        
        reg = self.get_slave(slave_id).write_regs[1]

        modbus_request = ModbusRequest(
                                function=self.MODBUS_WRITE,
                                slave_id=slave_id,
                                register_address=reg,
                                value=int(freq_value*10))
        
        payload = self.build_modbus_request(modbus_request, if_header=True)
        return payload
    
    def build_init_request(self, slave_id: int):
        reg = self.get_slave(slave_id).write_regs[0]
        init_values = [0x0080, 0x0006, 0x0007, 0x000F]
        for v in init_values:
            modbus_request = ModbusRequest(
                                function=self.MODBUS_WRITE,
                                slave_id=slave_id,
                                register_address=reg,
                                value=v)
            payload = self.build_modbus_request(modbus_request, if_header=True)
            yield payload
    
    

            



    
    
            
