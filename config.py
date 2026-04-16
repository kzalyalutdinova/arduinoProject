from configparser import ConfigParser
import os

def parse_analog_pins(analog_pins: list):
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
    print(bytearray(mask))
    return mask


def load_config(ini_path: str): #-> dict|None
    if not os.path.exists(ini_path):
        return

    config = ConfigParser()
    config.read(ini_path)


    analog_pins_str = config['ModbusUDP']['analog_pins'].strip().upper()
    # analog_pins = analog_pins_str.split('A')[1:]
    mask = parse_analog_pins(analog_pins_str.split('A')[1:])
    print(mask)
    

    info = {
        'ARDUINO_IP': config['ModbusUDP']['arduino_ip'],
        'PORT_SEND': int(config['ModbusUDP']['port_send_udp']),
        'PORT_LISTEN': int(config['ModbusUDP']['port_listen_udp']),
        'ANALOG_PINS': mask,
        'CMD_READ_SEV': int(config['ModbusUDP']['cmd_read_sev'], 16),  # 16-теричное число
        'CMD_WRITE_ONE': int(config['ModbusUDP']['cmd_write_one'], 16),
        'CMD_READ_ANALOG_PINS': int(config['ModbusUDP']['cmd_read_analog_pins']),
        'CMD_READ_TEMPERATURES': int(config['ModbusUDP']['cmd_read_temps']),
        'CMD_READ_FREQUESNCIES': int(config['ModbusUDP']['cmd_read_freqs']),
        'CMD_MODBUS_REQUEST': int(config['ModbusUDP']['cmd_modbus_command'])
    }

    return info

def load_slaves(ini_path: str): # -> list|None
    if not os.path.exists(ini_path):
        return

    config = ConfigParser()
    config.read(ini_path)

    slaves = []
    for section_name in config.sections():
        if section_name.startswith('ModbusUDP.Slave '):

            slave_info = {
                'name': config[section_name]['name'],
                'slave_id': int(config[section_name]['slave_id'], 0),
                'read_regs': [],
                'write_regs': []
                }
            
            for key in config[section_name]:
                if key.startswith('register_address_read'):
                    slave_info['read_regs'].append(int(config[section_name][key], 0))
                elif key.startswith('register_address_write'):
                    slave_info['write_regs'].append(int(config[section_name][key], 0))

            slaves.append(slave_info)

    return slaves

def load_pid(ini_path: str):
    if not os.path.exists(ini_path):
        return
    
    config = ConfigParser()
    config.read(ini_path)

    pid_coefs = {
        'PID_I_P': config['ModbusUDP']['pid_i_p'],
        'PID_I_I': config['ModbusUDP']['pid_i_i'],
        'PID_I_D': config['ModbusUDP']['pid_i_d'],
        'PID_I_DEADBAND': config['ModbusUDP']['pid_i_deadband']
    }

    return pid_coefs



