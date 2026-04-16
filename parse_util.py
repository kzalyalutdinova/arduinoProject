import struct
from dmrvtemp_2 import dmrv_var2, dmrv_var1

def parse_data(recieved_msg: bytes, addr = None) -> dict:
    # Парсинг ub2h.v3
    if recieved_msg.startswith(b"ub2h.v3:"):
        offset = 8  # Пропускаем 8 байт сигнатуры
        temps = []
        freqs = []
        errors = []
        analog_values = []

        while offset < len(recieved_msg):
            # Читаем код команды
            if offset + 2 > len(recieved_msg):
                errors.append(f"Truncated command at offset {offset}")
                break
            cmd = struct.unpack_from("<h", recieved_msg, offset)[0]  # <h = little-endian signed short
            offset += 2

            # Обрабатываем блок в зависимости от команды
            # if cmd == 120:  # Температуры
            #     # Читаем количество элементов
            #     if offset + 2 > len(recieved_msg):
            #         errors.append(f"Truncated count after command {cmd}")
            #         break
            #     count = struct.unpack_from("<H", recieved_msg, offset)[0]  # <H = little-endian unsigned short
            #     offset += 2

            #     for i in range(count):
            #         if offset + 4 > len(recieved_msg):
            #             errors.append(f"Truncated temperature #{i} (need 4 bytes)")
            #             break
            #         temp = struct.unpack_from("<f", recieved_msg, offset)[0]  # <f = little-endian float
            #         temps.append(round(temp, 2))
            #         offset += 4

            # TODO: обработать температуру корректно
            if cmd == 130:  # Частоты
                # Читаем количество элементов
                if offset + 2 > len(recieved_msg):
                    errors.append(f"Truncated count after command {cmd}")
                    break
                count = struct.unpack_from("<H", recieved_msg, offset)[0]  # <H = little-endian unsigned short
                offset += 2

                for i in range(count):
                    if offset + 4 > len(recieved_msg):
                        errors.append(f"Truncated frequency #{i} (need 4 bytes)")
                        break
                    freq = struct.unpack_from("<f", recieved_msg, offset)[0]
                    freqs.append(round(freq, 2))
                    offset += 4

            elif cmd == 170:  # Аналоговые данные
                if offset + 2 > len(recieved_msg):
                    errors.append("Truncated analog byte count")
                    break
                byte_count = struct.unpack_from("<H", recieved_msg, offset)[0]
                offset += 2

                # Проверяем, что достаточно данных в буфере
                if offset + byte_count > len(recieved_msg):
                    errors.append(f"Truncated analog data (need {byte_count} bytes, got {len(recieved_msg) - offset})")
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
                    value = struct.unpack_from("<f", recieved_msg, offset + i * 4)[0]
                    analog_values.append(round(value, 3))

                offset = offset + byte_count

            else:
                errors.append(f"Unknown command {cmd} at offset {offset-4}, stopping parse")
                break
        analog_pins_count = int(len(analog_values))
        m_vals = analog_values[:int(analog_pins_count/2)]
        t_vals = analog_values[analog_pins_count - int(analog_pins_count/2):]
        
        # mas = [38.75 * val**2 - 89.25 * val + 53.75 - 2.3 for val in m_vals]
        temps = []
        
        for i in range(int(analog_pins_count/2)):
            res = dmrv_var2(m_vals[i], t_vals[-i])
            temps.append(res)

        parsed_data = {
            "temps": temps,
            "freqs": freqs,
            "analog": {
                "values": analog_values,      
                "count": len(analog_values),  # Количество прочитанных значений
                "raw_byte_count": byte_count if 'byte_count' in locals() else 0  # Для отладки
            },
            "success": len(errors) == 0,
            "errors": errors if errors else None,
            "packet_size": len(recieved_msg),
            "addr": addr
        }
    else:
        parsed_data = {
            "valid": bool(recieved_msg[0]),
            "slave_id": recieved_msg[1],
            "func_code": recieved_msg[2],
            "reg_addr": (recieved_msg[3] << 8) | recieved_msg[4],
            "value_or_quantity": (recieved_msg[5] << 8) | recieved_msg[6]
        }
    
    return parsed_data