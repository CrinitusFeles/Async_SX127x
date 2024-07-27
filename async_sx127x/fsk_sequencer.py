

from enum import Enum

from async_sx127x.registers import SX127x_Registers


class FromIdle(Enum):
    Transmit = 0
    Receive = 1

class IdleMode(Enum):
    StandbyMode = 0
    SleepMode = 1

class LowPowerSelection(Enum):
    SequencerOff = 0
    IdleMode = 1

class FromStart(Enum):
    LowPower = 0x00 << 3
    Receive = 0x01 << 3
    Transmit = 0x02 << 3
    Transmit_on_FIFOLEVEL = 0x03 << 3

class FromTransmit(Enum):
    LowPower = 0x00
    Receive_on_PACKETSENT = 0x01

class FromReceive(Enum):
    unused = 0
    PacketReceived_on_PAYLOADREADY = 0x01 << 5
    LowPower = 0x02 << 5
    PacketReceived_on_CRCOK = 0x03 << 5
    SequenceOff_on_RSSI = 0x04 << 5
    SequenceOff_on_SYNCADDR = 0x05 << 5
    SequenceOff_on_PREAMBLEDETECT = 0x06 << 5

class FromRxTimeout(Enum):
    Receive = 0x00 << 3
    Transmit = 0x01 << 3
    LowPower = 0x02 << 3
    SequenceOff = 0x03 << 3

class FromPacketReceived(Enum):
    SequenceOff = 0x00
    Transmit = 0x01
    LowPower = 0x02
    Receive_via_FS = 0x03
    Receive = 0x04

class Sequencer:
    idle_mode: IdleMode
    low_power: LowPowerSelection
    from_start: FromStart
    from_idle: FromIdle
    from_transmit: FromTransmit
    from_receive: FromReceive
    from_rx_timeout: FromRxTimeout
    from_packet_received: FromPacketReceived

    def __init__(self, interface) -> None:
        self.interface = interface

    def __str__(self) -> str:
        return f'IdleMode: {self.idle_mode.name}\n'\
               f'LowPowerSelection: {self.low_power.name}\n'\
               f'FromIdle: {self.from_idle.name}\n'\
               f'FromStart: {self.from_start.name}\n'\
               f'FromTransmit: {self.from_transmit.name}\n'\
               f'FromReceive: {self.from_receive.name}\n'\
               f'FromRxTimeout: {self.from_rx_timeout.name}\n'\
               f'FromPacketReceived: {self.from_packet_received.name}\n'

    def read(self):
        addr = SX127x_Registers.FSK_SEQ_CONFIG1.value
        data: list[int] = self.interface.read_several(addr, 2)
        self.low_power = LowPowerSelection(data[0] & 0x04)
        self.idle_mode = IdleMode(data[0] & 0x40)
        self.from_start = FromStart(data[0] & 0x18)
        self.from_idle = FromIdle(data[0] & 0x02)
        self.from_transmit = FromTransmit(data[0] & 0x01)
        self.from_receive = FromReceive(data[1] & 0x1F)
        self.from_rx_timeout = FromRxTimeout(data[1] & 0x18)
        self.from_packet_received = FromPacketReceived(data[1] & 0x07)
        return self

    async def upload(self, start: bool = False) -> None:
        reg1: int = self.idle_mode.value | self.from_start.value
        reg1 |= self.low_power.value | self.from_idle.value
        reg1 |= self.from_transmit.value
        reg2: int = self.from_receive.value | self.from_rx_timeout.value
        reg2 |= self.from_packet_received.value
        await self.interface.write(SX127x_Registers.FSK_SEQ_CONFIG1.value,
                                   [reg1 | 0x80 if start else reg1, reg2])

    async def stop(self) -> None:
        addr = SX127x_Registers.FSK_SEQ_CONFIG1.value
        data: int = await self.interface.read(addr)
        await self.interface.write(addr, [data | 0x40])

    async def start(self) -> None:
        addr = SX127x_Registers.FSK_SEQ_CONFIG1.value
        data: int = await self.interface.read(addr)
        await self.interface.write(addr, [data | 0x80])

    async def start_tx(self) -> None:
        addr = SX127x_Registers.FSK_SEQ_CONFIG1.value
        await self.interface.write(addr, [0x90])
