import socket
import struct
import asyncio
from config import load_config, load_slaves
from utils.modbus_request_format import ModbusRequest
from request_builder import build_b2hv3_packet

# Функция отправки UDP с modbus - командой на arduino
# При успешной отправке, возвращается True; при ошибке - False
def send_modbus_command(request: ModbusRequest, settings:dict=None) -> bool:
    payload = b'h2ub.v3:'

    payload += struct.pack('<H', settings['CMD_MODBUS_REQUEST'])

    try:
        cmd = request['function']
    except KeyError:
        print('Error: "cmd" is required for modbus commands')
        return False
    
    if cmd == settings['CMD_WRITE_ONE'] or cmd == settings['CMD_READ_SEV']:
        try:
            slave_id = request['slave_id']
            register_address = request['register_address']
            value_to_pack = request['value']
        except KeyError:
            print('Error: "slave_id", "register_address", "value" are required for modbus commands')
            return False

        if slave_id <= 0 or slave_id > 255 or not isinstance(slave_id, int):
            print('Error: slave_id is incorrect. It must be between 1 and 255 and be integer')
            return False

        if value_to_pack < 0 or value_to_pack >= 65535 or not isinstance(value_to_pack, int):
            print('Error: value is incorrect. It must be between 1 and 65535 and be integer')
            return False

        if register_address < 0 or register_address >= 65535 or not isinstance(register_address, int):
            print('Error: value is incorrect. It must be between 1 and 65535 and be integer')
            return False

        payload += struct.pack('>BBHH', slave_id, cmd, register_address, value_to_pack)
    
    else:
        print(f'Error: Incorrect function code {cmd}')
        return False

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(payload, (settings['ARDUINO_IP'], settings['PORT_SEND']))
        sock.close()
        # print(f"UDP sent to {settings['ARDUINO_IP']}:{settings['PORT_SEND']}")
        print(f"Payload: {payload.hex()}")
        return True
    except socket.error as e:
        print(f"Error sending UDP packet: {e}")
        return False

# async def send_mbETA_1(config: dict, slaves: dict):
#     mbETA_2 = {
#             "function": config['CMD_READ_SEV'],
#             "slave_id": slaves[0]['slave_id'],
#             "register_address": 0x0C81,
#             "value": 1
#         }
#     send_modbus_command(mbETA_2, config)
#     print(slaves[0]['slave_id'])
#     await asyncio.sleep(0.01)
    
#     mbETA_3 = {
#             "function": config['CMD_READ_SEV'],
#             "slave_id": slaves[1]['slave_id'],
#             "register_address": 0x0C81,
#             "value": 1
#         }
#     send_modbus_command(mbETA_3, config)
#     print(slaves[1]['slave_id'])
#     await asyncio.sleep(0.01)

# Отправка codeETA[] каждому устройству
async def send_mbETA(config: dict, slaves: dict):
    for i in range(2):
        # print(slaves[i]['slave_id'])
        mbETA = {
            "function": config['CMD_READ_SEV'],
            "slave_id": slaves[i]['slave_id'],
            "register_address": 0x0C81,
            "value": 1
        }
        send_modbus_command(mbETA, config)
        await asyncio.sleep(0.5)

# Задать частоту = 0
async def setFreq_0(config: dict, slaves: dict):
    await send_mbETA(config, slaves)
    await asyncio.sleep(0.5)

    for i in range(2):
        request = {
            "function": config['CMD_WRITE_ONE'],
            "slave_id": slaves[i]['slave_id'],
            "register_address": 0x2136,
            "value": 0
            # "value": int(value) * 10 # 0.0 < float(value) <= 50
        }
        send_modbus_command(request, config)
        await asyncio.sleep(0.5)

# Задать частоту от 0 до 50
async def setFreq(config: dict, slaves: dict, value: float):
    if value > 50:
        value = 50
    
    await send_mbETA(config, slaves)
    await asyncio.sleep(0.5)

    # request = {
    #         "function": config['CMD_WRITE_ONE'],
    #         "slave_id": slaves[0]['slave_id'],
    #         "register_address": 0x2136,
    #         "value": int(value * 10)
    #         # "value": int(value) * 10 # 0.0 < float(value) <= 50
    #     }
    # send_modbus_command(request, config)
    # await asyncio.sleep(0.3)

    
    for i in range(2):
        request = {
            "function": config['CMD_WRITE_ONE'],
            "slave_id": slaves[i]['slave_id'],
            "register_address": 0x2136,
            "value": int(value * 10)
            # "value": int(value) * 10 # 0.0 < float(value) <= 50
        }
        send_modbus_command(request, config)
        await asyncio.sleep(0.5)

# Инициализация
async def send_init_commands(config: dict, slaves: dict):
    for i in range(2):
        for v in [0x0080, 0x0006, 0x0007, 0x000F]:
            request = {
                "function": config['CMD_WRITE_ONE'],
                "slave_id": slaves[i]['slave_id'],
                "register_address": 0x2135,
                "value": v
            }
            send_modbus_command(request, config)
            await asyncio.sleep(0.5)
        await asyncio.sleep(0.5)

async def send_b2hv3_packet(config: dict, slaves: dict):

    request = await build_b2hv3_packet(config, slaves)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(request, (config['ARDUINO_IP'], config['PORT_SEND']))
        sock.close()
        return True
    except socket.error as e:
        print(f"Error sending UDP packet: {e}")
        return False

if __name__ == "__main__":
    ini_file_path = 'lam.ini'
    CONFIG = load_config(ini_file_path)
    SLAVES = load_slaves(ini_file_path)

    if CONFIG is None:
        raise RuntimeError(f'No ini-file (path:{ini_file_path})')

    request_1 = {
        "function": CONFIG['CMD_WRITE_ONE'],
        "slave_id": SLAVES[0]['slave_id'],
        "register_address": SLAVES[0]['register_address_write'],
        "value": 0xABCD
    }

    request_2 = {
        "function":CONFIG['CMD_READ_SEV'],
        "slave_id": SLAVES[1]['slave_id'],
        "register_address": SLAVES[1]['register_address_read'],
        "value": 3
    }

    bad_request_no_value = {
        "function": CONFIG['CMD_READ_SEV'],
        "slave_id": SLAVES[1]['slave_id'],
        "register_address":SLAVES[1]['register_address_read']
    }

    bad_request_wrong_slave = {
        "function": CONFIG['CMD_READ_SEV'],
        "slave_id": 280,
        "register_address": 0xABCD,
        "value": 3
    }

    bad_request_wrong_register_address = {
        "function": CONFIG['CMD_READ_SEV'],
        "slave_id": 1,
        "register_address": 700000,
        "value": 3
    }

    bad_request_wrong_value = {
        "function": CONFIG['CMD_READ_SEV'],
        "slave_id": 1,
        "register_address": 0xABCD,
        "value": 79000
    }

    bad_request_wrong_cmd = {
        "function": 4,
        "slave_id": 1,
        "register_address": 0xABCD,
        "value": 3
    }

    # res_1 = send_modbus_command(request_1, CONFIG)
    # print(res_1)

    res_2 = send_modbus_command(request_2, CONFIG)
    print(res_2)

    res_3 = send_modbus_command(bad_request_no_value, CONFIG)
    print(res_3)

    res_4 = send_modbus_command(bad_request_wrong_slave, CONFIG)
    print(res_4)

    res_5 = send_modbus_command(bad_request_wrong_register_address, CONFIG)
    print(res_5)

    res_6 = send_modbus_command(bad_request_wrong_value, CONFIG)
    print(res_6)

    res_7 = send_modbus_command(bad_request_wrong_cmd, CONFIG)
    print(res_7)


