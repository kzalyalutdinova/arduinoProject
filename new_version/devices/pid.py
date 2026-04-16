import time
import logging
from typing import List
from configparser import ConfigParser

logger = logging.getLogger(__name__)

class PID:
    SECTION_PREFIX = 'ModbusUDP'
    PID_PREFIX = 'pid_i_'
    FREQUENCY_BORDERS = [0, 50]

    def __init__(self, config: ConfigParser, desired_value: float = None, sample_time: float = 1.0): 
        self.sample_time = sample_time
        self._desired_value = desired_value
        self.real_value = 0.0
        self.output = 0.0

        self._Kp = config.getfloat(self.SECTION_PREFIX, f'{self.PID_PREFIX}p')
        self._Ki = config.getfloat(self.SECTION_PREFIX, f'{self.PID_PREFIX}i')
        self._Kd = config.getfloat(self.SECTION_PREFIX, f'{self.PID_PREFIX}d')
        self._db = config.getfloat(self.SECTION_PREFIX, f'{self.PID_PREFIX}deadband')

        self.is_running = False

        self.reset()

    def reset(self):
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = time.monotonic()
        self.output = 0.0
    
    def set_goal(self, value: float):
        self._desired_value = value
        self.reset()
    
    def set_real_value(self, values: List[float]):
        real_value_average = sum(values) / len(values)
        # real_value_average = values[0]
        self.real_value = real_value_average

    def compute(self) -> float:
        if time.monotonic() - self.last_time < self.sample_time:
            return self.output
        
        dt = (time.monotonic() - self.last_time) 
        dt = 1 if dt <= 0 else dt

        current_error = self._desired_value - self.real_value

        self.integral += current_error * dt
        derivative = (current_error - self.last_error) / dt

        output = self._Kp * current_error + self._Ki * self.integral + self._Kd * derivative
        self.output = output

        self.last_error = current_error
        self.last_time = time.monotonic()

        if abs(self.last_error) < self._db:
            return 0.0
        
        logger.info(f"[PID] error={current_error:.3f}, integral={self.integral:.3f}, output={output:.3f}")
        return output   # output - частота
    
    # def compute_hyst_pid(self, hyst_rate: float) -> float:
    #     if time.monotonic() - self.last_time < self.period:
    #         return None
        
    #     current_error = self._desired_value - self.real_value

    #     if current_error < hyst_rate * self._desired_value:
    #         output = None
    #     else:
    #         output = 1
        
    #     self.output = output
    #     return output

class ReleController:
    def __init__(self, threshold: float):
        self._desired_value = 0.0
        self.bounded_value: List[float, float] = []

        self.real_value = 0.0
        self.threshold = threshold
        self.last_error = 0.0

        self.output = 0.0

        self.is_running = False
        # self.rele_position = 0

    def set_real_value(self, values: List[float]):
        if len(values) == 0: 
            real_value_average = 0
        else:
            # real_value_average = sum(values) / len(values)
            real_value_average = values[2]
        self.real_value = real_value_average
    
    def set_temperature_bounds(self):
        lower_bound = self._desired_value * (1 - self.threshold)
        upper_bound = self._desired_value * (1 + self.threshold)
        self.bounded_value = [lower_bound, upper_bound]
    
    def set_desired_value(self, des_value: float):
        self._desired_value = des_value
        self.set_temperature_bounds()

    def reset(self):
        self.last_error = 0.0
        self._desired_value = 0.0
        self.bounded_value = [0.0, 0.0]

    def compute(self):
        current_error = self._desired_value - self.real_value
        
        if self.real_value < self.bounded_value[0]:
            output = 1
        elif self.real_value > self.bounded_value[1]:
            output = 0
        else:
            output = self.output
        
        self.last_error = current_error
        self.output = output
        return output





