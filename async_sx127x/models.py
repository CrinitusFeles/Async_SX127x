from pydantic import BaseModel, Field, field_serializer


class LoRaModel(BaseModel):
    spreading_factor: int
    coding_rate: int
    bandwidth: float | int
    sync_word: int
    autogain_control: bool
    lna_gain: int
    lna_boost: bool
    header_mode: str
    ldro: bool

class FSK_Model(BaseModel):
    bitrate: int
    deviation: int
    sync_word: bytes
    dc_free: str
    packet_format: bool

    @field_serializer('sync_word')
    def serialize_sync_word(self, sync_word: bytes, _info):
        try:
            result = sync_word.decode()
        except UnicodeDecodeError:
            result = sync_word.hex(' ').upper()
        return result

class RadioModel(BaseModel):
    frequency: int
    check_crc: bool
    tx_power: float
    pa_select: bool
    mode: FSK_Model | LoRaModel

    def __str__(self) -> str:
        return self.model_dump_json(indent=4)

class RadioPacket(BaseModel):
    timestamp: str
    data: bytes
    data_len: int
    frequency: int
    caller: str = Field(default_factory=lambda: '')

    @field_serializer('data')
    def serialize_data(self, dt: bytes, _info):
        return dt.hex(' ').upper()

class BaseLoRaPacket(RadioPacket):
    mode: str = 'LoRa'
    sf: int
    bw: int | float
    ldro: bool
    Tpkt: float

class LoRaRxPacket(BaseLoRaPacket):
    snr: int
    rssi_pkt: int
    crc_correct: bool
    fei: int
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}] ' if self.caller else ' '
        currepted_string: str = '(CORRUPTED) ' if not self.crc_correct else ' '
        return f'{self.timestamp}\n'\
               f'{self.mode} {caller_name} {currepted_string}\n'\
               f'Freq: {self.frequency:_}\n'\
               f'FEI: {self.fei}\n'\
               f'RSSI: {self.rssi_pkt}\n'\
               f'SNR: {self.snr};\n'\
               f'RX[{self.data_len}] < {self.data.hex(" ").upper()}'


class LoRaTxPacket(BaseLoRaPacket):
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}] ' if self.caller else ''
        return f'{self.timestamp}\n{self.mode} {caller_name}\n'\
               f'Freq: {self.frequency:_}\n'\
               f'TOF(ms): {round(self.Tpkt)};\n'\
               f'TX[{self.data_len}] > {self.data.hex(" ").upper()}'


class FSK_RX_Packet(RadioPacket):
    rssi_pkt: int
    crc_correct: bool
    mode: str = 'FSK'
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}] ' if self.caller else ''
        currepted_string: str = '(CORRUPTED) ' if not self.crc_correct else ' '
        return f'{self.timestamp}\n'\
               f'{self.mode} {caller_name} {currepted_string}\n'\
               f'Freq: {self.frequency:_}\n'\
               f'RSSI: {self.rssi_pkt}\n'\
               f'RX[{self.data_len}] < {self.data.hex(" ").upper()}'

class FSK_TX_Packet(RadioPacket):
    mode: str = 'FSK'
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}] ' if self.caller else ''
        return f'{self.timestamp} {self.mode} {caller_name}\n'\
               f'Freq: {self.frequency:_}\n'\
               f'TX[{self.data_len}] > {self.data.hex(" ").upper()}'


class LoraTransaction(BaseModel):
    request: LoRaTxPacket | None = None
    answer: LoRaRxPacket | None = None
    retries: int = 0
    duration_ms: int = 0
    rx_timeout_ms: int = 0

class FSK_Transaction(BaseModel):
    request: FSK_TX_Packet | None = None
    answer: FSK_RX_Packet | None = None
    retries: int = 0
    duration_ms: int = 0
    rx_timeout_ms: int = 0


class RadioTransaction(BaseModel):
    request: LoRaTxPacket | FSK_TX_Packet | None = None
    answer: LoRaRxPacket | FSK_RX_Packet | None = None
    retries: int = 0
    duration_ms: int = 0
    rx_timeout_ms: int = 0
