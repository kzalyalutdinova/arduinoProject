import struct

async def build_b2hv3_packet(config: dict, slaves: dict):
    packet = b''

    heading = b'h2ub.v3:'
    packet += heading

    # request_temp = build_request(slaves, config['CMD_READ_TEMPERATURES'])
    # if request_temp:
    #     packet += request_temp

    request_freq = build_request(slaves, config['CMD_READ_FREQUESNCIES'])
    if request_freq:
        packet += request_freq

    request_analog = build_analog_request(cmd=config['CMD_READ_ANALOG_PINS'],
                                          mask=config['ANALOG_PINS'])
    packet += request_analog

    return packet

def build_request(slaves: dict, cmd: int):
    # cmd = config['CMD_READ_TEMPERATURES']

    slave_ids = []
    for slave in slaves:  
        try:
            slave_ids.append(slave['slave_id'])
        except KeyError:
            print('Error: Slave {slave} has no key "slave_id"')
            continue
    
    slave_count = len(slave_ids)
    if slave_count == 0:
        return None
    
    request = struct.pack('<HH', cmd, slave_count)
    for sl_id in slave_ids:
        request += struct.pack('<B', sl_id)

    return request

def build_analog_request(cmd, mask):
    packet = struct.pack('<H', cmd)
    packet += struct.pack('<B', mask)
    return packet