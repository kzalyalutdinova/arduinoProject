import asyncio
import json
import logging
import tornado

from server.server_core import Server

# ===== Настройка логирования =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt=r'%d-%m-%Y %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ===== Глобальный экземпляр сервера =====
app_server: Server = None

# ===== HTTP Handlers =====
# Слушаем UDP от arduino (port 5276)
class ArduinoUdpProtocol(asyncio.DatagramProtocol):

    def datagram_received(self, data: bytes, addr):
        global app_server
        # print(data)

        parsed_data = app_server.parse_arduino_answer(data, addr)
        print(parsed_data)
        if parsed_data:
            logger.info(f'[UDP] Recieved message:\n{parsed_data}')
            
            # if app_server.pid_regulator.is_running:
            #     asyncio.create_task(app_server.pid_step())
            
            app_server.broadcast(json.dumps(parsed_data))
            app_server.write_logs_to_file(parsed_data, 300)
        else:
            print(data)
            logger.info(f'[UDP] Recieved wrong message format:\n{data}')
        
    def error_received(self, exc):
        print(exc)

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


class GetUserRequest(tornado.web.RequestHandler):  
    async def post(self):
        global app_server
        
        try:
            data = json.loads(self.request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            self.set_status(400)
            self.write({"status": "error", "message": "Invalid JSON"})
            return
        
        # Извлекаем user_command для логирования
        user_command = data.get('user_command')
        logger.info(f"[HTTP] user_command={user_command}")
        
        # Обрабатываем команду через Server
        await app_server.handle_user_command(user_command, data)


class GetRegistersHandler(tornado.web.RequestHandler):    
    def get(self):
        global app_server
        try:
            slave_id = int(self.get_argument('slave_id', 0))
            modbus_cmd = int(self.get_argument('function', 0))
        except ValueError as e:
            logger.error(f"Invalid arguments: {e}")
            self.write({'registers': []})
            return
        
        slave = app_server.get_slave(slave_id)
        
        if slave:
            # Определяем, read или write регистры нужны
            if modbus_cmd == app_server.arduino.MODBUS_WRITE:
                regs = slave.write_regs
            else:
                regs = slave.read_regs
            self.write({'registers': [f"0x{r:04X}" for r in regs]})
        else:
            logger.warning(f"Slave {slave_id} not found")
            self.write({'registers': []})


class ArduinoWebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        global app_server
        app_server.add_ws_client(self)
        logger.info(f"[WS] Client connected. Total: {len(app_server.ws_clients)}")
    
    def on_close(self):
        global app_server
        app_server.remove_ws_client(self)
        logger.info(f"[WS] Client disconnected. Total: {len(app_server.ws_clients)}")
    
    def on_message(self, message):
        logger.debug(f"[WS] Received (ignored): {message}")


# ===== Создание приложения =====
def make_app() -> tornado.web.Application:
    return tornado.web.Application(
        [
            (r'/', MainHandler),
            (r'/user_request', GetUserRequest),
            (r'/get_registers', GetRegistersHandler),
            (r'/ws', ArduinoWebSocketHandler),
        ],
        template_path='templates',
        static_path='static',
        debug=True  # Отключить в продакшене
    )


# ===== Точка входа =====
async def main():
    global app_server
    
    logger.info("=" * 60)
    logger.info("Starting ModbusUDP Server")
    logger.info("=" * 60)
    
    # 4. Создаём экземпляр Server
    app_server = Server(True)
    
    # 5. Создаём и запускаем Tornado-приложение
    app = make_app()
    app.listen(8282, address='localhost')  # 0.0.0.0 для доступа из сети
    logger.info("✓ HTTP server running on http://localhost:8282/")
    
    # 6. Запускаем UDP-слушатель
    await app_server.start_udp_listener(ArduinoUdpProtocol())
    logger.info(f"UDP listener running on {app_server.server_ip}:{app_server.udp_port_listen}")
    
    
    # 8. Запускаем main loop
    logger.info("=" * 60)
    logger.info("Server is ready!")
    logger.info("=" * 60)
    
    # tornado.ioloop.IOLoop.current().start()
    stop_event = asyncio.Event()
    await stop_event.wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n[SERVER] Shutdown requested by user")
        logger.info("[SERVER] Goodbye!")
    except Exception as e:
        logger.error(f"[SERVER] Fatal error: {e}")
        raise