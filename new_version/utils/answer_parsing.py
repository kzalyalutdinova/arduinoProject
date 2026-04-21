import struct
from devices.arduino_board import ArduinoBoard


def answer_parsing(message: bytes, arduino: ArduinoBoard, RECIEVE_HEADER=b'ub2h.v3:'):
    parsed_answer = {}
    if message.startswith(RECIEVE_HEADER):
        offset = 8
        freqs = []
        errors = []
        analog_values = []
        thermos = []

        while offset < len(message):
        # Читаем код команды
            if offset + 2 > len(message):
                errors.append(f"Truncated command at offset {offset}")
                break
            cmd = struct.unpack_from("<H", message, offset)[0]
            offset += 2

            if cmd == arduino.CMD_READ_FREQUENCES:
                if offset + 2 > len(message):
                    errors.append(f"Truncated count after command {cmd}")
                    break
                count = struct.unpack_from("<H", message, offset)[0]
                offset += 2

                for i in range(count):
                    if offset + 4 > len(message):
                        errors.append(f"Truncated frequency #{i} (need 4 bytes)")
                        break
                    freq = struct.unpack_from("<f", message, offset)[0]
                    freqs.append(round(freq, 2))
                    offset += 4

                parsed_answer["freqs"] = freqs

            elif cmd == arduino.CMD_READ_THERMO:
                if offset + 2 > len(message):
                    errors.append(f"Truncated count after command {cmd}")
                    break
                count = struct.unpack_from("<H", message, offset)[0]
                offset += 2

                for i in range(count):
                    if offset + 4 > len(message):
                        errors.append(f"Truncated frequency #{i} (need 4 bytes)")
                        break
                    temp = struct.unpack_from("<f", message, offset)[0]
                    thermos.append(round(temp, 2))
                    offset += 4
                
                # error_code = struct.unpack_from("<H", message, offset)[0]
                # offset += 2

                # parsed_answer['thermo_error'] = error_code
                
                parsed_answer["thermo"] = thermos
            
            elif cmd == arduino.CMD_READ_ANALOG_PINS:  # Аналоговые данные
                if offset + 2 > len(message):
                    errors.append("Truncated analog byte count")
                    break
                byte_count = struct.unpack_from("<H", message, offset)[0]
                offset += 2

                # Проверяем, что достаточно данных в буфере
                if offset + byte_count > len(message):
                    errors.append(f"Truncated analog data (need {byte_count} bytes, got {len(message) - offset})")
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
                    value = struct.unpack_from("<f", message, offset + i * 4)[0]
                    analog_values.append(round(value, 3))

                offset = offset + byte_count
                parsed_answer['a_pins'] = analog_values

            elif cmd == arduino.CMD_CHECK_RELE:
                if offset + 1 > len(message):
                    errors.append(f"Truncated count after command {cmd}")
                    break
                count = struct.unpack_from("<B", message, offset)[0]  # <B = unsigned char = 1 байт
                offset += 1
                parsed_answer['rele_on'] = 'On' if count == 1 else 'Off'
            
            elif cmd == arduino.CMD_DRW:
                if offset + 1 > len(message):
                    errors.append(f"Truncated count after command {cmd}")
                    break
                ans = struct.unpack_from("<B", message, offset)[0]  # <B = unsigned char = 1 байт
                offset += 1
                parsed_answer['drw'] = f"{ans:08b}"
            else:
                errors.append(f"Unknown command {cmd} at offset {offset-4}, stopping parse")
                break
        
        parsed_answer['errors'] = errors if errors else None
        parsed_answer['packet_size'] = len(message)

        if len(thermos) == 0:
            thermos = ['No_thermo']

    return parsed_answer

            
        