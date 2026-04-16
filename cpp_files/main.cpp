#include <Arduino.h>
#include <Adafruit_MAX31856.h>
#include <EthernetUdp.h>
#include "ethernet.h"
#include "modbus.h"

void setup() {
    ethernet_init();
    delay(100);
    thermo_init();
    delay(100);
    modbus_init();
    delay(1000);
}

void loop() {
    pull_loop();
    // push_loop();
}


