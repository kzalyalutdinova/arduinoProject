#ifndef MODBUS_H
#define MODBUS_H

#include <Arduino.h>
#include <stdint.h>

#define SOFT 1

// Modbus функции
constexpr uint8_t CMD_READ_SEV = 0x03;
constexpr uint8_t CMD_WRITE_ONE  = 0x06;
constexpr uint8_t CMD_READ_ANALOG_PINS = 170;
constexpr uint8_t CMD_READ_TEMPERATURES = 120;
constexpr uint8_t CMD_READ_FREQUENCIES = 130;
constexpr uint8_t CMD_MODBUS = 140;
constexpr uint8_t CMD_READ_THERMO = 150;
constexpr uint8_t CMD_TOGGLE_RELE = 160;
constexpr uint8_t CMD_CHECK_RELE = 161;

// Пины SoftwareSerial
constexpr uint8_t MODBUS_RX_PIN = 3; 
constexpr uint8_t MODBUS_TX_PIN = 2;

// Функции
uint16_t calculateCRC(uint8_t* data, uint8_t len);

bool write(uint8_t* buf, uint8_t size);

bool writeRegister(uint8_t slaveAddr, uint16_t regAddr, uint16_t value);
bool readRegisters(uint8_t slaveAddr, uint16_t startAddr, uint16_t quantity);

float readFrequency(uint8_t slaveAddr, uint16_t startAddr, uint16_t quantity);

void modbus_init();

#endif
