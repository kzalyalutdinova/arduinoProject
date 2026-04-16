from dataclasses import dataclass
from typing import Literal
import struct
import logging

logger = logging.getLogger(__name__)

@dataclass
class ModbusRequest:
    """
    Представляет Modbus-запрос.
    Валидирует данные при создании и предоставляет методы для работы.
    """
    function: Literal[3, 6]  # 0x03 = Read, 0x06 = Write
    slave_id: int
    register_address: int
    value: int
    # quantity: int | None = None  # Для Read
    
    def __post_init__(self):
        self.value = int(self.value)
        self._validate()
    
    def _validate(self):
        # self.function = int(self.function, 0)
        # self.slave_id = int(self.slave_id, 0)
        # self.register_address = int(self.register_address, 0)
        # self.value = int(self.value, 0)

        if not (1 <= self.slave_id <= 247):
            logger.info(f'[MODBUS] Recieved wrong slave_id number:\n{self.slave_id}')
            # raise ValueError(f"slave_id must be 1..247, got {self.slave_id}")
        
        if not (0 <= self.register_address <= 65535):
            logger.info(f'[MODBUS] Recieved wrong register_address number:\n{self.register_address}')
            # raise ValueError(f"register_address must be 0..65535, got {self.register_address}")
        
        if self.function == 6:  # Write
            if self.value is None:
                raise ValueError("value is required for Write function (0x06)")
            if not (0 <= self.value <= 65535):
                logger.info(f'[MODBUS] Recieved wrong value:\n{self.value}')
                # raise ValueError(f"value must be 0..65535, got {self.value}")
            self.quantity = None  # Не используется для Write
        
        elif self.function == 3:  # Read
            if self.value is None:
                raise ValueError("quantity is required for Read function (0x03)")
            if not (1 <= self.value <= 125):
                logger.info(f'[MODBUS] Recieved wrong quantity:\n{self.value}')
                # raise ValueError(f"quantity must be 1..125, got {self.value}")
            # self.value = None  # Не используется для Read
        else:
            raise ValueError(f"Unsupported function code: {self.function}")
    
    def to_bytes(self) -> bytes:
        """
        Сериализует запрос в Modbus-формат (big-endian).
        Формат: [slave_id:1][function:1][address:2][value/quantity:2]
        """

        return struct.pack('>BBHH', self.slave_id, self.function, 
                          self.register_address, self.value)
    
    def to_dict(self) -> dict:
        """Для сериализации в JSON"""
        return {
            'function': self.function,
            'slave_id': self.slave_id,
            'register_address': self.register_address,
            'value': self.value,
            # 'quantity': self.quantity,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ModbusRequest':
        """Создаёт экземпляр из словаря (например, из JSON)"""
        return cls(
            function=data['function'],
            slave_id=data['slave_id'],
            register_address=data['register_address'],
            value=data.get('value'),
            # quantity=data.get('quantity'),
        )
    
    def __str__(self) -> str:
        func_name = "Read" if self.function == 3 else "Write"
        return f"ModbusRequest({func_name}, slave={self.slave_id}, reg=0x{self.register_address:04X})"