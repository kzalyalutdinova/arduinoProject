#include "modbus.h"
#include "rele.h"

bool releOn = false;

void rele_init() {
    pinMode(RELE_CS, OUTPUT);
    digitalWrite(RELE_CS, HIGH);  // или LOW - изначально выключено
    releOn = false;
};

void rele_on() {
    digitalWrite(RELE_CS, LOW);   // или HIGH - включить
    releOn = true;
};

void rele_off() {
    digitalWrite(RELE_CS, HIGH);   // или LOW - выключить
    releOn = false;
};

void rele_toggle(uint8_t rele_position) {
    if (rele_position == 1) {
        rele_on();
    } else {
        rele_off();
    }
}