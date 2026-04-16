from configparser import ConfigParser
from typing import List
# import struct, os

# @dataclass
class SlaveDevice:
    SECTION_PREFIX = "ModbusUDP.Slave "

    def __init__(self, config: ConfigParser, section_name: str, if_thermo=False):
        if not config.has_section(section_name):
            raise ValueError(f"Section '{section_name}' not found in config")
        
        self._section_name = section_name
        slave_id_raw = config.get(section_name, 'slave_id').strip()
        self.slave_id = int(slave_id_raw, 0)  # auto-detect base

        if not (1 <= self.slave_id <= 247):
            raise ValueError(f"Invalid slave_id {self.slave_id} (must be in 1-247)")
        
        self.read_regs: List[int] = []
        self.write_regs: List[int] = []
        self._load_registers(config, section_name)

        self.analog_pin_signal = config.get(section_name, 'analog_pin_signal')
        self.analog_pin_temp = config.get(section_name, 'analog_pin_temp')

        self.frequency = 0.0
        self.dmrv_value = 0.0
        self.current_temp_v = 0.0
        self.current_flow_v = 0.0

        self.if_thermo = if_thermo
        if self.if_thermo:
            self.thermo: List[float] = []

    def _load_registers(self, config: ConfigParser, section_name: str):
        """
        Парсит ключи register_address_read_* и register_address_write_*.
        Сохраняет порядок и имена ключей КАК ЕСТЬ из INI.
        """
        # Получаем ключи в том порядке, в котором они записаны в INI
        for key in config.options(section_name):
            value_raw = config.get(section_name, key).strip()
            
            if not key.startswith('register_address_'):
                continue
            
            try:
                address = int(value_raw, 0)  # auto-detect: 0x, 0o, 0b, decimal
            except ValueError:
                print(f"Warning: Invalid register address '{value_raw}' in {key}, skipped")
                continue
            
            # Сохраняем пару (имя_ключа, адрес) — порядок сохраняется!
            if key.startswith('register_address_read'):
                self.read_regs.append(address)
            elif key.startswith('register_address_write'):
                self.write_regs.append(address)
    
    def get_registers(self, is_write: bool = False) -> List[int]:
        """
        Возвращает список регистров как [(key_name, address), ...].
        Порядок соответствует порядку в INI-файле.
        """
        return self.write_regs if is_write else self.read_regs
        
    @property
    def slave_id_hex(self) -> str:
        return f"0x{self.slave_id:02X}"
    
    def to_dict(self) -> dict:
        return {
            'slave_id': self.slave_id,
            'slave_id_hex': self.slave_id_hex,
            # 'name': self.name,
            'read_regs': self.read_regs,
            'write_regs': self.write_regs,
            # 'section': self._section_name,
        }
    
    def update(self, 
               frequency: float = None, 
               dmrv_value: float = None,
               current_temp_v: float = None,
               current_flow_v: float = None,
               thermo: List[float] = None
               ):
        
        self.frequency = frequency
        self.dmrv_value = dmrv_value
        self.current_temp_v = current_temp_v
        self.current_flow_v = current_flow_v

        if self.if_thermo and thermo:
            self.thermo = thermo