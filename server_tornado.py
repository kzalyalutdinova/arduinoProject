import tornado
from tornado import websocket
import json
import os
import asyncio
from config import load_config, load_slaves
from udp_sender import send_modbus_command, send_mbETA, send_init_commands, setFreq_0, setFreq, send_b2hv3_packet
from parse_util import parse_data
import datetime

############ Настройки ############
# Формирование пути до ini-файла
current_dir = os.path.dirname(os.path.abspath(__file__))
ini_file_path = os.path.join(current_dir, 'lam.ini')

CONFIG = load_config(ini_file_path)     # Общая информация
SLAVES = load_slaves(ini_file_path)     # Информация об устройствах

if CONFIG is None:
    raise RuntimeError(f'No ini-file (path:{ini_file_path})')

# буфер для хранения UDP-ответов от Arduino
latest_arduino_response = None
websocket_clients = set()
is_initialized = False

last_update = datetime.datetime.now() - datetime.timedelta(minutes=30)

# Отправляем codeETA[] раз в N секунд
async def periodic_send_mbETA(config: dict, slaves: dict, n: float = 3):
    while True:
        await send_mbETA(config, slaves)
        await send_b2hv3_packet(config, slaves)

        await asyncio.sleep(n)

# Асинхронный UDP-слушатель
async def start_udp_listener():
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ArduinoUdpProtocol(),
        local_addr=('192.168.5.100', 5277)  # IP сервера и порт для ответов
    )

# Слушаем UDP от arduino (port 5276)
class ArduinoUdpProtocol(asyncio.DatagramProtocol):
    def send_to_websockets(self, data):
        global websocket_clients
        
        # Отправляем каждому клиенту
        for client in list(websocket_clients):
            client.write_message(json.dumps(data))
            
    def datagram_received(self, data: bytes, addr):
        global latest_arduino_response, last_update
        # print(data)

        parsed_data = parse_data(data, addr)
        if parsed_data:
            print(parsed_data)
        else:
            print(data)

        latest_arduino_response = parsed_data
        self.send_to_websockets(parsed_data)

        # if last_update + datetime.timedelta(minutes=5) < datetime.datetime.now():
        #     last_update = datetime.datetime.now()
            
        with open('results_dif_freq_2.txt', 'a', encoding='utf-8') as f:
            msg = f'{last_update.strftime("%d-%m-%y %H:%M:%S")}: {parsed_data}\n'
            f.write(msg)

    def error_received(self, exc):
        print(exc)

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")

# Обрабатывает команды от пользователя (HTTP) и отправляет запрос на Arduino (UDP)
class GetUserRequest(tornado.web.RequestHandler):
    async def post(self):
        global is_initialized
        data = json.loads(self.request.body)

        cmd = data["user_command"]
        # print(data)
        
        # Инициализация
        if cmd == 'init':
            print('INIT COMMAND START')
            await send_mbETA(CONFIG, SLAVES)
            await setFreq_0(CONFIG, SLAVES)
            await send_init_commands(CONFIG, SLAVES)
            
            if not is_initialized:
                asyncio.create_task(
                    periodic_send_mbETA(CONFIG, SLAVES, 2)
                )
                is_initialized = True
            # await setFreq_0(CONFIG, SLAVES)
            print('INIT COMMAND STOP')
            return
        
        
        # Установка частоты
        if cmd == 'set_frequency':
            # await send_mbETA(CONFIG, SLAVES)
            await setFreq(CONFIG, SLAVES, float(data['value']))
            return

        # Отправка modbus-запроса, составленного пользователем
        cmd = int(data["function"])
        slave_id = int(data["slave_id"])
        value = int(data["value"])
        registers = data['registers']
        
        for i in range(len(registers)):
            request = {
                'function': cmd,
                'slave_id': slave_id,
                'register_address': int(registers[i]),
                'value': value
            }
        
            # Отправка UDP-запроса на Arduino
            send_modbus_command(request, CONFIG)
            await asyncio.sleep(0.3)

# class GetArduinoAnswer(tornado.web.RequestHandler):
#     def get(self):
#         global latest_arduino_response
#         if latest_arduino_response is None:
#             self.write({"success": False, "error": "No response from Arduino"})
#         else:
#             self.write(latest_arduino_response)

# Отправляем указанные в ini-файле регистры
class GetRegistersHandler(tornado.web.RequestHandler):
    def get(self):
        slave_id = int(self.get_argument('slave_id', 0))
        command = int(self.get_argument('function', 0))

        # print(f'slave_id: {slave_id}, command: {command}')

        for slave in SLAVES:
            if slave['slave_id'] == slave_id:
                if command == CONFIG['CMD_WRITE_ONE']:
                    registers = slave['write_regs']
                elif command == CONFIG['CMD_READ_SEV']:
                    registers = slave['read_regs']
                self.write({'registers': registers})
                return
        
        # если такого slave_id нет
        self.write({'registers': []})

class ArduinoWebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        global websocket_clients
        websocket_clients.add(self)
    
    def on_close(self):
        global websocket_clients
        websocket_clients.discard(self)


def make_app():
    return tornado.web.Application(
        [
            (r'/', MainHandler),
            (r'/user_request', GetUserRequest),
            # (r'/get_response', GetArduinoAnswer),
            (r'/get_registers', GetRegistersHandler),
            (r'/ws', ArduinoWebSocketHandler),
        ],
        template_path='templates',
        static_path='static'
    )

if __name__ == "__main__":
    app = make_app()
    app.listen(8282, address='localhost')
    print("Сервер запущен на http://localhost:8282/")
    asyncio.ensure_future(start_udp_listener())
    tornado.ioloop.IOLoop.current().start()