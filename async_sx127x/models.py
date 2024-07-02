from dataclasses import dataclass
from pydantic import BaseModel

class RadioModel(BaseModel):
    mode: str
    op_mode: str
    frequency: int
    spreading_factor: int
    coding_rate: str
    bandwidth: str
    check_crc: bool
    sync_word: int
    tx_power: float
    autogain_control: bool
    lna_gain: int
    lna_boost: bool
    header_mode: str
    ldro: bool

    def __str__(self) -> str:
        return super().__str__().replace(' ', '\n')

@dataclass
class LoRaPacket:
    timestamp: str
    data: str
    data_len: int
    freq_error_hz: int
    frequency: int

    def to_bytes(self) -> bytes:
        return bytes.fromhex(self.data)


@dataclass
class LoRaRxPacket(LoRaPacket):
    snr: int
    rssi_pkt: int
    is_crc_error: bool
    fei: int
    caller: str = ''

    def __str__(self) -> str:
        caller_name: str = f' [{self.caller}] ' if self.caller else ' '
        currepted_string: str = ' (CORRUPTED) ' if self.is_crc_error else ' '
        return f"{self.timestamp}{caller_name}{currepted_string}"\
               f"freq error: {self.freq_error_hz}; FEI: {self.fei}; " \
               f"rssi: {self.rssi_pkt}; snr: {self.snr}; "\
               f"data len: {self.data_len};\n rx < {self.data}"


@dataclass
class LoRaTxPacket(LoRaPacket):
    Tpkt: float
    low_datarate_opt_flag: bool
    caller: str = ''

    def __str__(self) -> str:
        caller_name: str = f' [{self.caller}] ' if self.caller else ' '
        return f"{self.timestamp}{caller_name}data len: {self.data_len}; "\
               f"TOF(ms): {round(self.Tpkt)}; tx > {self.data}"