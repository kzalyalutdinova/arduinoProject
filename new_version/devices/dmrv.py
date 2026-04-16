import math
from typing import List, Dict


class Sensor:
    B = 3980.0
    T0 = 298.15
    R0 = 2000.0
    M = 0.03995
    P_ATM = 101325.0
    R_GAS = 8.314

    # Коэффициенты для формулы массового расхода (кг/ч)
    MAF_A, MAF_B, MAF_C, MAF_D = 38.75, -89.25, 53.75, 2.3

    # Коэффициенты для формулы температуры (°C)
    # TEMP_A, TEMP_B, TEMP_C = -15.3267, -56.9575, 80.5282

    def __init__(self):
        self.dmrv_results: List[float, float] = []
        
        # self.current_flow_v: List[float, float] = []
        # self.current_temp_v: List[float, float] = []
        
        self.current_voltages: List[float] = []

    def update(self, voltage_values):
        self.current_voltages = []
        for slave_id in sorted(voltage_values.keys()):
            values = self._validate(voltage_values[slave_id])
            self.current_voltages.append(values)

        # border = int(len(voltage_values)/2)
        # # Поменять местами
        # self.current_flow_v = voltage_values[:border]
        # self.current_temp_v = voltage_values[border:]
        # self._validate()

        self.dmrv_results = self._parse_analog_values_from_arduino()
    
    def _validate(self, values: List[float]):
        values[0] = 4.999 if values[0] >= 5.0 else values[0]    # signal pin
        values[1] = 1e-3 if values[1] <= 0.0 else values[1]     # temp pin
        return values

    def _parse_analog_values_from_arduino(self):
        results = []
        for i in range(len(self.current_voltages)):
            res = self.dmrv_count(self.current_voltages[i][0], self.current_voltages[i][1])
            results.append(res)
        return results

    def dmrv_count(self, flow_v, temp_v):
        curr_flow = self.MAF_A * flow_v ** 2 + self.MAF_B * flow_v + self.MAF_C + self.MAF_D

        curr_temp_v = temp_v * 2500 / (5 - temp_v)

        log_arg = curr_temp_v / self.R0
        if log_arg <= 0:
            log_arg = 1e-6
        
        curr_temp_k = 1.0 / (1.0/self.T0 + (1.0/self.B) * math.log(log_arg)) - 273

        rho = (self.P_ATM * self.M) / (self.R_GAS * curr_temp_k)
        x = (curr_flow / rho)

        return x