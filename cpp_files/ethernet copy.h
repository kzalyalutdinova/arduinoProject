#ifndef ETHERNET_H
#define ETHERNET_H

#include <Arduino.h>
#include <IPAddress.h>

extern unsigned int localPort;
extern unsigned int sendPort;
extern const IPAddress MONITOR_IP;

void ethernet_init();
void thermo_init();
void pull_loop();

uint16_t buildUb2hV3Packet(uint8_t* buffer, size_t buffer_size);
void process_Ub2hV3Packet(uint8_t* buffer, int len);
void process_ModbusCMD(uint8_t* buffer, int len);
void process_ReleToggleCMD(uint8_t* buffer, int len);
bool isValidCommand(uint16_t cmd);

// void push_loop();
// void push_Ub2hV3Packet();
// void push_loop_2();

#endif