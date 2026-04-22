#include "modbus.h"
#include <SoftwareSerial.h>

// SoftwareSerial modbusSerial(MODBUS_RX_PIN, MODBUS_TX_PIN);

// Подсчет контрольной суммы
uint16_t calculateCRC(uint8_t* data, uint8_t len) {
    uint16_t crc = 0xFFFF;
    for (uint8_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x0001) {
                crc >>= 1;
                crc ^= 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc;
}

bool write(byte *buf, int s) {
    delay(10);
    int wr;

    if (SOFT) {
        delay(10);
        // wr = modbusSerial.write(buf, s);
        wr = Serial.write(buf, s);
    } else {
        wr = Serial.write(buf, s);
    };

    // Serial.print("DEBUG: Tried to send ");
    // Serial.print(s);
    // Serial.print(" bytes, actually sent: ");
    // Serial.println(wr);
    return (wr == s);
}

bool writeRegister(byte slaveAddr,      // Адрес ведомого устройства
                   uint16_t regAddr,    // Адрес регистра, на который нужно записать значение
                   uint16_t value)      // Значение, которое нужно записать в регистр
{
    byte buf[8];                        // Буфер для хранения пакета Modbus

    // Формирование пакета данных
    buf[0] = slaveAddr;          // Адрес ведомого устройства
    buf[1] = CMD_WRITE_ONE;      // Функция записи одного регистра
    buf[2] = highByte(regAddr);  // Старший байт адреса регистра (извлекает старшие 8 бит из 16-битного числа)
    buf[3] = lowByte(regAddr);   // Младший байт адреса регистра
    buf[4] = highByte(value);    // Старший байт значения
    buf[5] = lowByte(value);     // Младший байт значения

    // Расчет CRC
    uint16_t crc = calculateCRC(buf, 6);
    buf[6] = lowByte(crc);
    buf[7] = highByte(crc);

    return write(buf, 8);  // Отправка запроса
}

bool readRegisters(byte slaveAddr,      // Адрес ведомого устройства
                   uint16_t startAddr,  // Адрес первого регистра, с которого начинается чтение
                   uint16_t quantity)   // Количество последовательно идущих регистров, которые нужно прочитать
{
    byte buf[8];

    // Формирование пакета данных
    buf[0] = slaveAddr;
    buf[1] = CMD_READ_SEV;              // Функция чтения регистров
    buf[2] = highByte(startAddr);
    buf[3] = lowByte(startAddr);
    buf[4] = highByte(quantity);
    buf[5] = lowByte(quantity);

    // Расчет CRC
    uint16_t crc = calculateCRC(buf, 6);
    buf[6] = lowByte(crc);
    buf[7] = highByte(crc);

    return write(buf, 8);
}

float readFrequency(byte slaveAddr, uint16_t startAddr,  uint16_t quantity) {
    while (Serial.available()) Serial.read();
    
    readRegisters(slaveAddr, startAddr, quantity);
    
    byte response[15];
    int i = 0;
    
    unsigned long start = millis();
    while ((millis() - start) < 200) {
        if (Serial.available()) {
            if (i < sizeof(response)) {
                response[i++] = Serial.read();
            }
        }
        delay(1);
    }
    
    for (int pos = 0; pos <= i - 7; pos++) {
        if (response[pos] == slaveAddr && response[pos + 1] == 0x03 && response[pos + 2] == 0x02) {
            uint16_t freq = (uint16_t(response[pos + 3]) << 8) | response[pos + 4];
            return freq / 10.0;
        }
    }
    
    //Serial.println("No valid response found");
    return -1;
}


void modbus_init() {
   Serial.begin(19200);
}
