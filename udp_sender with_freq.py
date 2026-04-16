from server.udp_sender import send_modbus_command
import server.config as config
import time

frequency = 100                   # запрос в секунду
interval = 1.0 / frequency      # интервал между запросами
ini_file_path = 'lam.ini'
CONFIG = config.load_config(ini_file_path)
SLAVES = config.load_slaves(ini_file_path)
request_1 = {
        "function": CONFIG['CMD_WRITE_ONE'],
        "slave_id": SLAVES[0]['slave_id'],
        "register_address": SLAVES[0]['register_address_write'],
        "value": 0xABCD
    }


while True:
    start_time = time.time()
    success = send_modbus_command(request_1, CONFIG)

    # Если UDP-запрос не был отправлен, то пробуем отправить его еще раз
    if not success:
        print("Error: request wasn't sent\nTrying again")
        continue

    taken_time = time.time() - start_time
    sleep_time = interval - taken_time
    if sleep_time > 0:
        time.sleep(sleep_time)
    else:
        # Если обработка запроса заняла больше времени, чем интервал, предупреждение
        print(f"Warning: request processing took {taken_time:.4f}s > {interval:.4f}s.")