#include <drw.h>

byte DOUT_NUM = 8;


unsigned long dout_set(unsigned long v) {
    unsigned long out = 0;
    digitalWrite(DOUT_CLK, LOW);
    digitalWrite(DOUT_LATCH, LOW);
    // A Little hack because pins goes like this |7 6 5 4|3 2 1 0| |15 14 13 12|11 10 9 8|
    unsigned long mask = 1; // << 8;
    for (int i = 0; i < DOUT_NUM; i++) {
        digitalWrite(DOUT_MOSI, ((v & mask) > 0 ? HIGH : LOW));
        digitalWrite(DOUT_CLK, HIGH);

        delayMicroseconds(3);

        mask <<= 1;
        // if (mask > 65536) mask = 1;

        digitalWrite(DOUT_CLK, LOW);

        out = out << 1;
        out |= digitalRead(DOUT_MISO);
    }

    digitalWrite(DOUT_LATCH, HIGH);

    return out;
}

