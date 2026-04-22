#include <Arduino.h>
#include <Adafruit_MAX31856.h>
#include <EthernetUdp.h>
#include "ethernet.h"
#include "modbus.h"
// #include "rele.h"
#include "drw.h"

// const int LED_PIN = 4;  // Встроенный светодиод или внешний


// void setup() {
//     // pinMode(LED_PIN, OUTPUT);  // Объявляем пин как выход

//     //Serial.begin(9600);
//     ethernet_init();
//     modbus_init();
    

// }

// void loop() {
//     pull_loop();

    
//     // digitalWrite(LED_PIN, HIGH);  // Включить (5В)
//     // delay(1000);                  // Ждать 1000 мс (1 секунда)
  
//     // digitalWrite(LED_PIN, LOW);   // Выключить (0В)  
//     // delay(1000);     

// }


void setup() {
    ethernet_init();
    delay(100);
    thermo_init();
    delay(100);
    // rele_init();
    delay(100);
    modbus_init();
    delay(1000);
    pinMode(DOUT_CLK, OUTPUT);
    pinMode(DOUT_LATCH, OUTPUT);
    pinMode(DOUT_MOSI, OUTPUT);
    pinMode(DOUT_MISO, INPUT);
}

void loop() {
    pull_loop();
    // push_loop();
}


