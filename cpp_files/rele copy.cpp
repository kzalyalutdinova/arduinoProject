// #include "modbus.h"
// #include "rele.h"

// bool releOn = false;

// void rele_init() {
//     pinMode(RELE_CS, OUTPUT);

//     // Тест: 3 цикла включения/выключения
//     // for(int i = 0; i < 3; i++) {
//     //     digitalWrite(RELE_CS, LOW);  // Пробуем включить (Active-Low)
//     //     delay(300);                  // Ждём 0.3 сек
//     //     digitalWrite(RELE_CS, HIGH); // Выключаем
//     //     delay(300);
//     // };

//     digitalWrite(RELE_CS, LOW);  // или LOW - изначально выключено
//     releOn = false;
// };

// void rele_on() {
//     digitalWrite(RELE_CS, HIGH);   // или HIGH - включить
//     releOn = true;
// };

// void rele_off() {
//     digitalWrite(RELE_CS, LOW);   // или LOW - выключить
//     releOn = false;
// };

// void rele_toggle(uint8_t rele_position) {
//     if (rele_position == 1) {
//         rele_on();
//     } else {
//         rele_off();
//     }
// }