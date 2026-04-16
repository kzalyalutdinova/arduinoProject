from typing import TypedDict, Union

# Подсказки для составления словаря с modbus - запросом
class ModbusRequestRead(TypedDict):
    function: int
    slave_id: int
    register_address: int
    quantity: int


class ModbusRequestWrite(TypedDict):
    function: int
    slave_id: int
    register_address: int
    value: int

ModbusRequest = Union[ModbusRequestRead, ModbusRequestWrite]