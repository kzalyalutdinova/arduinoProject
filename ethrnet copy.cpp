#include <EthernetENC.h>
#include <EthernetUdp.h>
#include <Adafruit_MAX31856.h>

#include "modbus.h"
// #include "rele.h"
#include "ethernet.h"

#define B2HV3_PACKET_MAXSIZE 256

// #define MAX_SCK  9
// #define MAX_MISO 8
// #define MAX_MOSI 7

// #define CS1 A4  
// #define CS2 A3
// #define CS3 A2
// #define CS4 A5

#define CS1 A2  
#define CS2 A3
#define CS3 A4
#define CS4 A5


byte mac[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress ip(192, 168, 5, 140);
static IPAddress last_remote_ip(0, 0, 0, 0);        // ip-адрес последнего клиента, отправившего команду

unsigned int localPort = 5276;
unsigned int sendPort = 5277;

EthernetUDP Udp;

struct SensorData {

    float freqs[20];
    uint8_t freq_count;

    float analog_values[8];
    uint8_t analog_count;

    float temps[4];
    uint8_t temps_count;
    uint8_t fault;

    // bool check_rele;
    // bool is_rele_on;

     void reset() {
        temps_count = 0;
        freq_count = 0;
        analog_count = 0;
        // check_rele = false;
    };
};

SensorData data;
uint8_t packetBuffer[B2HV3_PACKET_MAXSIZE];


const unsigned long PUSH_INTERVAL = 5000; // 5 секунд
const unsigned long PUSH_INTERVAL_2 = 3100; // 3 секунд

// Создаём 4 экземпляра датчиков
Adafruit_MAX31856 thermo1 = Adafruit_MAX31856(CS1);
Adafruit_MAX31856 thermo2 = Adafruit_MAX31856(CS2);
Adafruit_MAX31856 thermo3 = Adafruit_MAX31856(CS3);
Adafruit_MAX31856 thermo4 = Adafruit_MAX31856(CS4);

Adafruit_MAX31856* thermos[] = {&thermo1, &thermo2, &thermo3, &thermo4};

void thermo_init() {
    for (int i = 0; i < 4; i++) {
        thermos[i]->begin();
        thermos[i]->setThermocoupleType(MAX31856_TCTYPE_K);
        thermos[i]->setConversionMode(MAX31856_CONTINUOUS);
        delay(50);
    }
};

void ethernet_init() {
    Ethernet.init(5);
    Ethernet.begin(mac, ip);
    Udp.begin(localPort); 
};

void process_Ub2hV3Packet(uint8_t* buffer, int len) {
    const int HEADER_LEN = 8;
    
    int offset = HEADER_LEN;
    
    // Сбрасываем счетчики перед заполнением
    data.reset();

    while (offset < len) {
        if (offset + 2 > len) break;

        uint16_t cmdCode;
        memcpy(&cmdCode, &buffer[offset], 2);
        offset += 2;

        if (cmdCode == CMD_READ_FREQUENCIES) {
            if (offset + 2 > len) break;
            uint16_t count;
            memcpy(&count, &buffer[offset], 2);
            offset += 2;

            for (int i = 0; i < count && data.freq_count < 20; i++) {
                if (offset >= len) break;
                uint8_t slaveId = buffer[offset];
                offset++; 
                data.freqs[data.freq_count++] = readFrequency(slaveId, 0x0C82, 1);
            };
        } 
        else if (cmdCode == CMD_READ_ANALOG_PINS) {
            if (offset >= len) break;
            uint8_t mask = buffer[offset];
            offset++;

            for (int i = 0; i < 8; i++) {
                if (mask & (1 << i)) {
                    float voltage = analogRead(i) * (5.0f / 1024.0f);
                    // float MAS = 38.75 * voltage * voltage - 89.25 * voltage + 53.75 - 2.3;
                    
                    if (data.analog_count <= 4) {
                        data.analog_values[data.analog_count++] = voltage;
                    };
                };
            };
        }
        else if (cmdCode == CMD_READ_THERMO) {
            for (int i = 0; i < 4; i++) {
                float t = thermos[i]->readThermocoupleTemperature();
                data.temps[i] = t;

                if (i == 2) {
                    data.fault = thermos[i]->readFault();
                };

                delay(1);
            };
            data.temps_count = 4;
        }
        // else if (cmdCode == CMD_CHECK_RELE) {
        //     data.check_rele = true;
        //     data.is_rele_on = releOn;
        // }
    };
};

void process_ModbusCMD(uint8_t* buffer, int len) {
    const int HEADER_LEN = 8;

    int offset = HEADER_LEN;

    while (offset < len) {

        if (offset + 6 > len) break;
        
        uint16_t cmdCode;
        memcpy(&cmdCode, &buffer[offset], 2);
        offset += 2;

        if (cmdCode == CMD_MODBUS) {
            uint8_t slave_id = buffer[offset++];
            uint8_t cmd = buffer[offset++];
            uint16_t reg = (buffer[offset] << 8) | buffer[offset + 1];
            offset += 2;
            uint16_t value = (buffer[offset] << 8) | buffer[offset + 1];

            if (cmd == CMD_READ_SEV) {
                readRegisters(slave_id, reg, value);
            } 
            else if (cmd == CMD_WRITE_ONE) {
                writeRegister(slave_id, reg, value);
            };
        };
    };
};



// void process_ReleToggleCMD(uint8_t* buffer, int len) {
//     const int HEADER_LEN = 8;
//     int offset = HEADER_LEN;

//     while (offset < len) {
        
//         uint16_t cmdCode;
//         memcpy(&cmdCode, &buffer[offset], 2);
//         offset += 2;

//         if (cmdCode == CMD_TOGGLE_RELE) {
//             rele_toggle();
//         }
//     }
// }

uint16_t buildUb2hV3Packet(uint8_t* buffer, size_t buffer_size) {
    uint16_t packet_size = 8;
    uint16_t offset = 0;
    
    if (data.freq_count > 0) {
        packet_size += 2 + 2 + 4 * data.freq_count;
    }
    
    if (data.analog_count > 0) {
        packet_size += 2 + 2 + 4 * data.analog_count;
    }
    
    if (data.temps_count > 0) {
        packet_size += 2 + 2 + 4 * data.temps_count;
    }

    if (packet_size > buffer_size) return 0;

    memcpy(&buffer[offset], "ub2h.v3:", 8);
    offset += 8;

    if (data.freq_count > 0) {
        uint16_t cmd = CMD_READ_FREQUENCIES;
        memcpy(&buffer[offset], &cmd, 2);
        offset += 2;

        uint16_t fc_count = data.freq_count;
        memcpy(&buffer[offset], &fc_count, 2);
        offset += 2;

        for (uint8_t i = 0; i < fc_count; i++) {
            memcpy(&buffer[offset], &data.freqs[i], 4);
            offset += 4;
        };
    };

    if (data.analog_count > 0) {
        uint16_t cmd = CMD_READ_ANALOG_PINS;
        memcpy(&buffer[offset], &cmd, 2);
        offset += 2;

        uint16_t byte_count = data.analog_count * 4;
        memcpy(&buffer[offset], &byte_count, 2);
        offset += 2;

        memcpy(&buffer[offset], data.analog_values, byte_count);
        offset += byte_count;
    }

    if (data.temps_count > 0) {
        uint16_t cmd = CMD_READ_THERMO;
        memcpy(&buffer[offset], &cmd, 2);
        offset += 2;

        uint16_t t_count = data.temps_count;
        memcpy(&buffer[offset], &t_count, 2);
        offset += 2;

        for (uint8_t i = 0; i < t_count; i++) {
            memcpy(&buffer[offset], &data.temps[i], 4);
            offset += 4;
        };

        uint16_t error_code = data.fault;
        memcpy(&buffer[offset], &error_code, 2);
        offset += 2;
    }

    // if (data.check_rele) {
    //     uint16_t cmd = CMD_CHECK_RELE;
    //     memcpy(&buffer[offset], &cmd, 2);
    //     offset += 2;

    //     uint8_t r_count = 0;
    //     if (data.is_rele_on) {
    //         r_count = 1;
    //     }
    //     memcpy(&buffer[offset], &r_count, 1);
    //     offset += 1;
    // }

    return offset;
};

bool isValidCommand(uint16_t cmd) {
    // Биты для команд: 120, 130, 150, 170
    // Это пример, нужно подбирать под ваши значения
    switch (cmd) {
        case CMD_READ_FREQUENCIES:
        case CMD_READ_TEMPERATURES:
        case CMD_READ_ANALOG_PINS:
        case CMD_READ_THERMO:
        // case CMD_CHECK_RELE:
            return true;
        default:
            return false;
    }
}

void pull_loop() {

    int packetSize = Udp.parsePacket();
    if (packetSize <= 0) return;
    
    if (packetSize > B2HV3_PACKET_MAXSIZE) {
        uint8_t trash[64];
        while (Udp.available()) {
            Udp.read(trash, min(Udp.available(), 64));
        }
        return;
    }

    IPAddress remote = Udp.remoteIP();
    
    // 2. Проверка IP ДО чтения пакета (чтобы не читать мусор)
    if (remote == IPAddress(0, 0, 0, 0)) {
        Udp.flush(); // Очистить буфер
        return;
    }
    
    last_remote_ip = remote;

    // 3. Читаем пакет
    int len = Udp.read(packetBuffer, packetSize);

    // 4. ДОЧИТЫВАЕМ ОСТАТОК (Критично!)
    while (Udp.available()) {
        Udp.read();
    }

    if (len <= 0) return;

    const int HEADER_LEN = 8;

    if (len >= HEADER_LEN) {
        uint8_t command = packetBuffer[8];
        if (command == CMD_MODBUS) {
            process_ModbusCMD(packetBuffer, len);
        }
        else if (isValidCommand(command)) {
            //data.reset();
            process_Ub2hV3Packet(packetBuffer, len);

            uint8_t response_buffer[B2HV3_PACKET_MAXSIZE];
            uint16_t response_size = buildUb2hV3Packet(response_buffer, sizeof(response_buffer));
            
            Udp.beginPacket(last_remote_ip, sendPort);
            Udp.write(response_buffer, response_size);
            Udp.endPacket();
        } 
        // else if (command == CMD_TOGGLE_RELE) {
        //     process_ReleToggleCMD(packetBuffer, len);
        // }
    } else {
        
        // 6. Строгая проверка для Modbus
        if (len < 6) {
            return;
        }
        
        uint8_t slave_id = packetBuffer[0];
        uint8_t func_code = packetBuffer[1];
        
        // 7. Проверка на адекватность (защита от мусора)
        if (slave_id == 0 || slave_id > 247) return;
        if (func_code != CMD_READ_SEV && func_code != CMD_WRITE_ONE) return;
        
        uint16_t reg_addr = (packetBuffer[2] << 8) | packetBuffer[3];
        uint16_t value_or_quantity = (packetBuffer[4] << 8) | packetBuffer[5];

        if (func_code == CMD_READ_SEV) {
            bool success = readRegisters(slave_id, reg_addr, value_or_quantity);
        } else if (func_code == CMD_WRITE_ONE) {
            bool success = writeRegister(slave_id, reg_addr, value_or_quantity);
        }
    }
    
}

