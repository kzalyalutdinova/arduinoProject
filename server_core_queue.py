import asyncio
import struct
import logging
import datetime
import time
import tornado.websocket
# import tornado.ioloop

from typing import Set, Dict, List, Optional, Any
from configparser import ConfigParser

from devices.arduino_board import ArduinoBoard
from devices.slave_device import SlaveDevice
from devices.dmrv import Sensor
from utils.modbus_request import ModbusRequest
from devices.pid import PID

logger = logging.getLogger(__name__)

class Server:
    ini_path = 'lam.ini'
    log_file_path = 'new_version/logs/results.txt'
    server_ip = '192.168.5.100'
    timeout_requests_sec = 0.2
    timeout_periodic_update_sec = 2

    SLAVE_SECTION_PREFIX = "ModbusUDP.Slave "
    SECTION_PREFIX = 'ModbusUDP'
    RECIEVE_HEADER = b'ub2h.v3:'

    
    def __init__(self):
        self.config = ConfigParser()
        self.config.read(self.ini_path)

        self.udp_port_send = self.config.get(self.SECTION_PREFIX, 'port_send_udp')
        self.udp_port_listen = self.config.get(self.SECTION_PREFIX, 'port_listen_udp')
        
        self.slaves = self._load_slaves()
        self.arduino = ArduinoBoard(self.config, self.slaves)
        self.dmrv = Sensor()

        self.pid_regulator: PID = PID(self.config)
        self._pid_task: Optional[asyncio.Task] = None

        self.ws_clients: Set[tornado.websocket.WebSocketHandler] = set()
        self._log_to_file_delay: int = 0
        self._log_last_update = datetime.datetime.now()

        self.is_initialized = False
        self._udp_transport = None

        # Две очереди для высоко и низко приоритетных задач
        self._high_priority_queue = asyncio.Queue()   # команды пользователя
        self._low_priority_queue = asyncio.Queue()    # ПИД, фоновые задачи
        self._udp_sender_task = asyncio.create_task(self._udp_sender_worker())

    def _load_slaves(self) -> Dict[int, SlaveDevice]:
        slaves = {}
        for section in self.config.sections():
            if section.startswith(self.SLAVE_SECTION_PREFIX):
                slave_id = int(self.config.get(section, 'slave_id'), 0)
                slaves[slave_id] = SlaveDevice(self.config, section)
        return slaves
    
    @property
    def slave_ids(self) -> List[int]:
        return list(self.slaves.keys())
    
    def get_slave(self, slave_id: int) -> Optional[SlaveDevice]:
        if slave_id not in self.slave_ids():
            raise KeyError(f'No such slave id {slave_id}')
        
        return self.slaves.get(slave_id)

    async def _udp_sender_worker(self):
        """
        Единый воркер для отправки UDP-пакетов на Arduino.
        Приоритет: HIGH > LOW (сначала обрабатывает всю высокую очередь)
        """
        
        while True:
            try:
                # 1. Сначала опустошаем высокую очередь (без блокировки)
                while not self._high_priority_queue.empty():
                    request = await self._high_priority_queue.get()
                    self.arduino.send(request)
                    await asyncio.sleep(self.timeout_requests_sec)
                    self._high_priority_queue.task_done()
                
                # 2. Если высокой нет — берём из низкой (с таймаутом)
                try:
                    request = await asyncio.wait_for(self._low_priority_queue.get(), timeout=0.1)
                    self.arduino.send(request)
                    await asyncio.sleep(self.timeout_requests_sec)
                    self._low_priority_queue.task_done()
                except asyncio.TimeoutError as e:
                    # Обе очереди пусты — небольшая пауза перед новым циклом
                    await asyncio.sleep(0.01)
                    continue
                    
            except Exception as e:
                logger.error(f"[UDP] Sender worker error: {e}", exc_info=True)
                await asyncio.sleep(0.01)
    
    async def _send_request(self, request, priority: str = 'low'):
        if priority == 'high':
            await self._high_priority_queue.put(request)
        else:
            await self._low_priority_queue.put(request)
    
    async def _send_mbETA(self, slave_id: int, priority: str = 'low'):
        request_mbETA = self.arduino.build_mbETA_request(slave_id)
        await self._send_request(request_mbETA, priority)
    
    async def _set_frequency(self, slave_id:int, freq:float, priority: str = 'low'):
        request_setFrequency = self.arduino.build_setFrequency_request(slave_id, freq)
        await self._send_request(request_setFrequency, priority)
    
    async def _send_periodic_request(self):
        while True:
            for slave_id in self.slave_ids:
                request_mbETA = self.arduino.build_mbETA_request(slave_id)
                await self._send_request(request_mbETA, 'high')
            b2hv3_request = self.arduino.build_b2hv3_packet()
            await self._send_request(b2hv3_request, 'high')
            await asyncio.sleep(self.timeout_periodic_update_sec)

    async def _cmd_init(self):
        print('INIT COMMAND START')
        for slave_id in self.slave_ids:
            await self._send_mbETA(slave_id, 'high')
            
        for slave_id in self.slave_ids:
            await self._set_frequency(slave_id, 0.0, 'high')

        for slave_id in self.slave_ids:
            payload_generator = self.arduino.build_init_request(slave_id)
            for payload in payload_generator:
                await self._send_request(payload, 'high')
            await asyncio.sleep(self.timeout_requests_sec)
        print('INIT COMMAND STOP')

        if not self.is_initialized:
            asyncio.create_task(self._send_periodic_request())
            self.is_initialized = True
    
    async def handle_user_command(self, user_command: str, params: Dict[str, Any]):
        if user_command == 'init':
            await self._cmd_init()
        elif user_command == 'set_frequency':
            desired_frequency = float(params['value'])
            for slave_id in self.slave_ids:
                await self._set_frequency(slave_id, desired_frequency, 'high')
        elif user_command == 'modbus_request':
            registers = params['registers']
            for reg in registers:
                modbus_request = ModbusRequest(
                                    function=int(params['function']),
                                    slave_id=int(params['slave_id']),
                                    register_address=int(reg),
                                    value=int(params['value']))
                payload = self.arduino.build_modbus_request(modbus_request, if_header=True)
                await self._send_request(payload, 'high')
        elif user_command == 'set_dmrv':
            logger.info(f"[CMD] Received set_dmrv with params: {params}")
            desired_value = float(params['value'])
            await self.pid_start(desired_value)
            
    def update_slaves(self, data: dict):
        for i in range(len(self.slave_ids)):
            slave_id = self.slave_ids[i]
            self.slaves[slave_id].update(
                    frequency = float(data['freqs'][i]), 
                    dmrv_value = float(data['dmrv_results'][i]),
                    current_temp_v = float(data['analog']['values'][-i]),
                    current_flow_v = float(data['analog']['values'][i])
                )
            
    def parse_arduino_answer(self, recieved_message: bytes, ip_addr=None):
        if recieved_message.startswith(self.RECIEVE_HEADER):
            offset = 8
            freqs = []
            errors = []
            analog_values = []
            while offset < len(recieved_message):
            # Читаем код команды
                if offset + 2 > len(recieved_message):
                    errors.append(f"Truncated command at offset {offset}")
                    break
                cmd = struct.unpack_from("<h", recieved_message, offset)[0]  # <h = little-endian signed short
                offset += 2

                if cmd == self.arduino.CMD_READ_FREQUENCES:
                    if offset + 2 > len(recieved_message):
                        errors.append(f"Truncated count after command {cmd}")
                        break
                    count = struct.unpack_from("<H", recieved_message, offset)[0]  # <H = little-endian unsigned short
                    offset += 2

                    for i in range(count):
                        if offset + 4 > len(recieved_message):
                            errors.append(f"Truncated frequency #{i} (need 4 bytes)")
                            break
                        freq = struct.unpack_from("<f", recieved_message, offset)[0]
                        freqs.append(round(freq, 2))
                        offset += 4
                
                elif cmd == self.arduino.CMD_READ_ANALOG_PINS:  # Аналоговые данные
                    if offset + 2 > len(recieved_message):
                        errors.append("Truncated analog byte count")
                        break
                    byte_count = struct.unpack_from("<H", recieved_message, offset)[0]
                    offset += 2

                    # Проверяем, что достаточно данных в буфере
                    if offset + byte_count > len(recieved_message):
                        errors.append(f"Truncated analog data (need {byte_count} bytes, got {len(recieved_message) - offset})")
                        break

                    # Проверяем, что кол-во байт соответствует кол-ву значений в формате float
                    # 8 байт = 2 (кол-во пинов) * 4 (размер одного значения в байтах); 12 байт = 3 (кол-во пинов) * 4 (размер одного значения в байтах) и тд
                    if byte_count % 4 != 0:
                        errors.append(f"Warning: analog byte count {byte_count} not multiple of 4 (float size). Using {byte_count // 4 * 4} bytes.")
                        
                        # Если есть неполные байты (% 4 != 0), то читаем только норм кол-во значений (% 4 == 0)
                        usable_bytes = (byte_count // 4) * 4
                    else:
                        usable_bytes = byte_count

                    # 4. Читаем ВСЕ значения как float
                    for i in range(usable_bytes // 4):
                        value = struct.unpack_from("<f", recieved_message, offset + i * 4)[0]
                        analog_values.append(round(value, 3))

                    offset = offset + byte_count

                else:
                    errors.append(f"Unknown command {cmd} at offset {offset-4}, stopping parse")
                    break
            self.dmrv.update(analog_values)

            parsed_data = {
                "dmrv_results": self.dmrv.dmrv_results,
                "freqs": freqs,
                "analog": {
                    "values": analog_values,      
                    "count": len(analog_values),  # Количество прочитанных значений
                    "raw_byte_count": byte_count if 'byte_count' in locals() else 0  # Для отладки
                },
                "success": len(errors) == 0,
                "errors": errors if errors else None,
                "packet_size": len(recieved_message),
                "addr": ip_addr
            }
            # self.dmrv.update(analog_values)
            self.update_slaves(parsed_data)
            logger.info(f"[SERVER] DMRV updated {self.dmrv.dmrv_results}")
        else:
            parsed_data = {
                "valid": bool(recieved_message[0]),
                "slave_id": recieved_message[1],
                "func_code": recieved_message[2],
                "reg_addr": (recieved_message[3] << 8) | recieved_message[4],
                "value_or_quantity": (recieved_message[5] << 8) | recieved_message[6]
            }
    
        return parsed_data

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
        
    async def _pid_control_loop(self):
        while self.pid_regulator.is_running:
            try:
                if not self.dmrv.dmrv_results:
                    await asyncio.sleep(self.pid_regulator.sample_time)
                    continue
                
                if time.monotonic() - self.pid_regulator.last_time < self.pid_regulator.sample_time:
                    await asyncio.sleep(0.1)
                    continue
            
                self.pid_regulator.set_real_value(self.dmrv.dmrv_results)
                output = self.pid_regulator.compute()
                
                if output is None:
                    self.pid_regulator.is_running = False
                    break

                s_id = self.slave_ids[0]
                result_frequency = self.slaves[s_id].frequency + output   # 
                # self.slaves[s_id].frequency = result_frequency
                for slave_id in self.slave_ids:
                    await self._set_frequency(slave_id, result_frequency*10)
                
                self.pid_regulator.last_time = time.monotonic()
                # b2hv3_request = self.arduino.build_b2hv3_packet()
                # await self._send_request(b2hv3_request)
                logger.info(f"[PID] Error: {self.pid_regulator.last_error}. Output: {self.pid_regulator.output}. Result frequency: {result_frequency}")
                await asyncio.sleep(0)
            except Exception as e:
                logger.error(f"[PID] ERROR in control loop: {e}", exc_info=True)  # ← Лог ошибки!
                await asyncio.sleep(self.pid_regulator.sample_time)
    
    async def pid_start(self, goal: float, sample_time: float = None):
        try:
            if self.pid_regulator.is_running:
                await self.pid_stop()
            
            if sample_time:
                self.pid_regulator.sample_time = sample_time
            
            self.pid_regulator.set_goal(goal)
            self.pid_regulator.is_running = True
            self._pid_task = asyncio.create_task(self._pid_control_loop())
            logger.info(f"[PID] PID regulator started. Sample time: {self.pid_regulator.sample_time}, goal: {self.pid_regulator._desired_value}")
        except Exception as e:
            logger.error(f"[PID] Failed to start: {e}", exc_info=True)
            raise

    async def pid_stop(self):
        if not self.pid_regulator.is_running:
            return
        
        self.pid_regulator.is_running = False
        if self._pid_task:
            self._pid_task.cancel()
            try:
                await self._pid_task
            except asyncio.CancelledError:
                pass
            finally:
                self._pid_task = None
        
        self.pid_regulator.reset()

        logger.info(f"[PID] PID regulator was stopped")
    
    

