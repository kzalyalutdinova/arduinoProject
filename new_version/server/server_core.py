import asyncio
import time
import struct
import logging
import datetime
import tornado.websocket
from typing import Set, Dict, List, Optional, Any
from configparser import ConfigParser

from devices.arduino_board import ArduinoBoard
from devices.slave_device import SlaveDevice
from devices.dmrv import Sensor
from utils.modbus_request import ModbusRequest
from devices.pid import PID, ReleController
from utils.answer_parsing import answer_parsing

logger = logging.getLogger(__name__)

class Server:
    ini_path = 'lam.ini'
    log_file_path = 'new_version/logs/results.txt'
    server_ip = '192.168.5.100'
    timeout_requests_sec = 0.3
    timeout_periodic_update_sec = 0.3

    SLAVE_SECTION_PREFIX = "ModbusUDP.Slave "
    SECTION_PREFIX = 'ModbusUDP'
    RECIEVE_HEADER = b'ub2h.v3:'

    def __init__(self, if_thermo=False):
        # Конфиг
        self.config = ConfigParser()
        self.config.read(self.ini_path)

        # UDP порты
        self.udp_port_send = self.config.get(self.SECTION_PREFIX, 'port_send_udp')
        self.udp_port_listen = self.config.get(self.SECTION_PREFIX, 'port_listen_udp')
        
        # Флаг о том, нужно ли читать термопары
        self.if_thermo = if_thermo

        self.slaves: Dict[int, SlaveDevice] = self._load_slaves(self.if_thermo)         # Словарь {slave_id: SlaveDevice}
        self.arduino = ArduinoBoard(self.config, self.slaves)                           # Экземпляр платы
        self.dmrv = Sensor()                                                            # Экземпляр ДМРВ
        
        # Карта аналоговых пинов {pin_num: (slave_id, pin_type ('signal' or 'temp'))}
        self.pin_map = self.build_pin_map()                                             

        # Регулятор для ДМРВ и частотников
        self.pid_regulator: PID = PID(self.config)
        self._pid_task: Optional[asyncio.Task] = None
        
        # Регулятор для реле
        self.rele_regulator = ReleController(float(self.config.get(self.SECTION_PREFIX, 'rele_threshold')))

        self.ws_clients: Set[tornado.websocket.WebSocketHandler] = set()
        self._log_to_file_delay: int = 0
        self._log_last_update = datetime.datetime.now()

        self.is_initialized = False         # Флаг, была ли инициализирована плата (для отправки опросов состояния)
        self._udp_transport = None


    def _load_slaves(self, if_thermo=False) -> Dict[int, SlaveDevice]:
        slaves = {}
        for section in self.config.sections():
            if section.startswith(self.SLAVE_SECTION_PREFIX):
                slave_id = int(self.config.get(section, 'slave_id'), 0)
                slaves[slave_id] = SlaveDevice(self.config, section, if_thermo)
        return slaves
    
    @property
    def slave_ids(self) -> List[int]:
        return list(self.slaves.keys())
    
    def get_slave(self, slave_id: int) -> Optional[SlaveDevice]:
        if slave_id not in self.slave_ids:
            raise KeyError(f'No such slave id {slave_id}')
        
        return self.slaves.get(slave_id)
    
    def build_pin_map(self) -> dict:
        pin_map = {}

        for slave_id in self.slave_ids:
            slave = self.slaves[slave_id]
            s_pin = int(slave.analog_pin_signal[1:])
            t_pin = int(slave.analog_pin_temp[1:])

            pin_map[s_pin] = (slave_id, 'signal')
            pin_map[t_pin] = (slave_id, 'temp')
        
        return pin_map
    
    async def _send_request(self, request):
        self.arduino.send(request)
        await asyncio.sleep(self.timeout_requests_sec)
    
    async def _send_mbETA(self, slave_id):
        request_mbETA = self.arduino.build_mbETA_request(slave_id)
        await self._send_request(request_mbETA)
    
    async def _set_frequency(self, slave_id:int, freq:float):
        request_setFrequency = self.arduino.build_setFrequency_request(slave_id, freq)
        await self._send_request(request_setFrequency)
    
    async def _send_periodic_request(self):
        while True:
            for slave_id in self.slave_ids:
                request_mbETA = self.arduino.build_mbETA_request(slave_id)
                await self._send_request(request_mbETA)
            
            if self.pid_regulator.is_running:
                await self.pid_step()
            
            if self.rele_regulator.is_running:
                await self.releRegulator_step()
            
            b2hv3_request = self.arduino.build_b2hv3_packet(if_thermo=self.if_thermo)
            await self._send_request(b2hv3_request)
            print(f'Payload: {b2hv3_request}')
            await asyncio.sleep(self.timeout_periodic_update_sec)

    async def _cmd_init(self):
        print('INIT COMMAND START')
        for slave_id in self.slave_ids:
            await self._send_mbETA(slave_id)
            
        for slave_id in self.slave_ids:
            await self._set_frequency(slave_id, 0.0)

        for slave_id in self.slave_ids:
            payload_generator = self.arduino.build_init_request(slave_id)
            for payload in payload_generator:
                await self._send_request(payload)
            await asyncio.sleep(self.timeout_requests_sec)
        print('INIT COMMAND STOP')

        if not self.is_initialized:
            asyncio.create_task(self._send_periodic_request())
            self.is_initialized = True
    
    async def handle_user_command(self, user_command: str, params: Dict[str, Any]):
        if user_command == 'init':
            await self._cmd_init()
            self.pid_stop()
            self.releRegulator_stop()
        
        elif user_command == 'set_frequency':
            desired_frequency = float(params['value'])
            for slave_id in self.slave_ids:
                await self._set_frequency(slave_id, desired_frequency)
                self.pid_stop()
            
        elif user_command == 'modbus_request':
            registers = params['registers']
            for reg in registers:
                modbus_request = ModbusRequest(
                                    function=int(params['function']),
                                    slave_id=int(params['slave_id']),
                                    register_address=int(reg),
                                    value=int(params['value']))
                payload = self.arduino.build_modbus_request(modbus_request, if_header=True)
                await self._send_request(payload)
                self.pid_stop()
        
        elif user_command == 'set_dmrv':
            logger.info(f"[CMD] Received set_dmrv with params: {params}")
            desired_value = float(params['value'])
            self.pid_start(desired_value)
            self.releRegulator_stop()

        elif user_command == 'set_temp':
            logger.info(f"[CMD] Received set_temp with params: {params}")
            desired_value = float(params['value'])
            self.pid_stop()
            self.releRegulator_start(desired_value)
        
        elif user_command == 'toggle_rele':
            self.arduino.rele_position = 0 if self.arduino.rele_position == 1 else 1
            pos = 'On' if self.arduino.rele_position == 1 else 'Off'
            
            logger.info(f"[CMD] Received toggle_rele. Current rele position: {pos}")
            
            req = self.arduino.build_rele_toggle_request(if_header=True)
            await self._send_request(req)
        
        elif user_command == 'drw_pins':
            logger.info(f"[CMD] Received drw_pins with params: {params}")
            self.arduino.drw_mask = int(params['value'])

            req = self.arduino.build_drw_request(if_header=True)
            await self._send_request(req)
            print(req)
            
    def update_slaves(self, data: dict):
        # for i in range(len(self.slave_ids)):
        pins = sorted(self.pin_map.keys())
        for k in range(len(self.slave_ids)):
            # slave = self.get_slave(slave_id)
            slave_id = self.slave_ids[k]
            t_value, s_value = None, None
            for i in range(len(pins)):
                pin = pins[i]
                if self.pin_map[pin][0] == slave_id:
                    if self.pin_map[pin][1] == 'signal':
                        s_value = float(data['analog']['values'][i])
                    else:
                        t_value = float(data['analog']['values'][i])
                
                if s_value and t_value:
                    break
            
            if self.if_thermo:
                self.slaves[slave_id].update(
                        frequency = float(data['freqs'][k]), 
                        dmrv_value = float(data['dmrv_results'][k]),
                        current_temp_v = t_value,
                        current_flow_v = s_value,
                        thermo=data['thermo']
                    )
            else:
                self.slaves[slave_id].update(
                        frequency = float(data['freqs'][k]), 
                        dmrv_value = float(data['dmrv_results'][k]),
                        current_temp_v = float(data['analog']['values'][-k]),
                        current_flow_v = s_value,
                    )

            
    def parse_arduino_answer(self, recieved_message: bytes, ip_addr=None):
        print(f'Answer: {recieved_message}')
        parsed_answer = answer_parsing(recieved_message, self.arduino)
        try:
            ans = parsed_answer['drw']
        except KeyError:
            voltages = self._set_analog_values(parsed_answer['a_pins'])
            self.dmrv.update(voltages)
            self.arduino.thermo_couples_values = parsed_answer['thermo']

        print(parsed_answer)
        return parsed_answer
    
    def _set_analog_values(self, pin_values):
        voltages = {}
        pins = sorted(self.pin_map.keys())

        if len(pins) != len(pin_values):
            logger.warning(f'[SERVER] Pins amount != recieved a_pins! Recieved {pin_values}')

        for i in range(len(pins)):
            slave_id = self.pin_map[pins[i]][0]
            pin_type = self.pin_map[pins[i]][1]

            if pin_type == 'signal':
                if slave_id in voltages:
                    voltages[slave_id].insert(0, pin_values[i])
                else:
                    voltages[slave_id] = [pin_values[i]]
            elif pin_type == 'temp':
                if slave_id in voltages:
                    voltages[slave_id].append(pin_values[i])
                else:
                    voltages[slave_id] = [pin_values[i]]
        
        return voltages


    async def start_udp_listener(self, protocol_datagram: asyncio.DatagramProtocol):
        loop = asyncio.get_event_loop()
        try:
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: protocol_datagram,
                local_addr=(self.server_ip, self.udp_port_listen)  # IP сервера и порт для ответов
            )
        except Exception as e:
            pass
    
    def add_ws_client(self, client: tornado.websocket.WebSocketHandler):
        self.ws_clients.add(client)
    
    def remove_ws_client(self, client: tornado.websocket.WebSocketHandler):
        self.ws_clients.discard(client)
    
    def broadcast(self, data: str):
        for client in list(self.ws_clients):
            client.write_message(data)
    
    def _write_to_file(self, message: str):
        with open(self.log_file_path, 'a', encoding='utf-8') as file:
            file.write(message)

    def write_logs_to_file(self, message: str, delay_sec: int = 0):
        if delay_sec != 0:
            self._log_to_file_delay = delay_sec
        
        if self._log_last_update + datetime.timedelta(seconds=self._log_to_file_delay) < datetime.datetime.now():
            self._write_to_file(f'{self._log_last_update.strftime("%d-%m-%y %H:%M:%S")}: {message}')
            self._log_last_update = datetime.datetime.now()

    def pid_start(self, goal: float):
        if self.pid_regulator.is_running:
            self.pid_regulator.reset()
        
        self.pid_regulator.is_running = True
        self.pid_regulator.sample_time = self.timeout_periodic_update_sec
        self.pid_regulator.set_goal(goal)

        logger.info(f"[PID] Regulator started with goal {goal}")
    
    async def pid_step(self):
        if time.monotonic() - self.pid_regulator.last_time < self.pid_regulator.sample_time:
            return
        
        self.pid_regulator.set_real_value(self.dmrv.dmrv_results)
        output = self.pid_regulator.compute()

        if output is None:
            self.pid_regulator.is_running = False
            return
        
        s_id = self.slave_ids[0]
        result_frequency = self.slaves[s_id].frequency + output
        if result_frequency > self.pid_regulator.FREQUENCY_BORDERS[1]:
            result_frequency = self.pid_regulator.FREQUENCY_BORDERS[1]
        elif result_frequency < self.pid_regulator.FREQUENCY_BORDERS[0]:
            result_frequency = self.pid_regulator.FREQUENCY_BORDERS[0]
        
        for slave_id in self.slave_ids:
            await self._set_frequency(slave_id, result_frequency)
        
        self.pid_regulator.last_time = time.monotonic()
        
        logger.info(f"[PID] PID regulator set frequency {result_frequency}")

        await asyncio.sleep(0.1)
    
    def pid_stop(self):
        self.pid_regulator.is_running = False
        self.pid_regulator.reset()

    def releRegulator_start(self, desired_value):
        if self.rele_regulator.is_running:
            self.rele_regulator.reset()
        
        self.rele_regulator.is_running = True
        # self.pid_regulator.sample_time = self.timeout_periodic_update_sec
        self.rele_regulator.set_desired_value(float(desired_value))

        logger.info(f"[RELE] Regulator started with goal {desired_value}")
    
    async def releRegulator_step(self):
        self.rele_regulator.set_real_value(self.arduino.thermo_couples_values)
        output = self.rele_regulator.compute()
        logger.info(f"[RELE] Regulator computed step {output}")

        self.arduino.rele_position = output
        req = self.arduino.build_rele_toggle_request(if_header=True)
        await self._send_request(req)

    def releRegulator_stop(self):
        self.rele_regulator.is_running = False
        self.rele_regulator.reset()
