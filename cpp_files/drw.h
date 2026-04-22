#ifndef DRW_H
#define DRW_H

#include <Arduino.h>

// DRW dout pins
#define DOUT_CLK 7
#define DOUT_LATCH 8
#define DOUT_MOSI 6
#define DOUT_MISO 9

// ========== Функции (объявления) ==========
unsigned long dout_set(unsigned long v);
#endif