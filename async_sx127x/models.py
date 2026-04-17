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
    bw: float
    ldro: bool
    Tpkt: float

class LoRaRxPacket(BaseLoRaPacket):
    snr: int
    rssi_pkt: int
    crc_correct: bool
    fei: int
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}]' if self.caller else ' '
        currepted_string: str = '(CORRUPTED)   ' if not self.crc_correct else ''
        return f'{self.timestamp}  RX[{self.data_len:>3}]  {currepted_string}'\
               f'Freq: {self.frequency/1e6:.3f}  '\
               f'FEI: {self.fei:<8}'\
               f'RSSI: {self.rssi_pkt:<6}'\
               f'SNR: {self.snr:<5}'\
               f'SF: {self.sf:<5}'\
               f'BW: {int(self.bw):<7}'\
               f'ToF(ms): {round(self.Tpkt):<8}'\
               f'{caller_name:<30} < {self.data.hex(" ").upper()}'

    def __repr__(self) -> str:
        return self.__str__()

class LoRaTxPacket(BaseLoRaPacket):
    attempt: int = 0
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}]' if self.caller else ''
        return f'{self.timestamp}  TX[{self.data_len:>3}]  '\
               f'Freq: {self.frequency/1e6:.3f}  '\
               f'Try: {self.attempt:<6}'\
               f'{" ":<24}'\
               f'SF: {self.sf:<5}'\
               f'BW: {int(self.bw):<7}'\
               f'ToF(ms): {round(self.Tpkt):<8}'\
               f'{caller_name:<30} > {self.data.hex(" ").upper()}'

    def __repr__(self) -> str:
        return self.__str__()


class FSK_RX_Packet(RadioPacket):
    rssi_pkt: int
    crc_correct: bool
    mode: str = 'FSK'
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller:<30}]' if self.caller else ''
        currepted_string: str = '(CORRUPTED) ' if not self.crc_correct else ' '
        return f'{self.timestamp}    RX    {currepted_string}'\
               f'{self.mode} {caller_name:<30}   '\
               f'Freq: {self.frequency:_}  '\
               f'RSSI: {self.rssi_pkt:<4}    '\
               f'RX[{self.data_len:^3}] < {self.data.hex(" ").upper()}'

class FSK_TX_Packet(RadioPacket):
    mode: str = 'FSK'
    attempt: int = 0
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}] ' if self.caller else ''
        return f'{self.timestamp}    TX    {self.mode} {caller_name:<30}   '\
               f'Freq: {self.frequency:_} '\
               f'TX[{self.data_len:^3}] > {self.data.hex(" ").upper()}'


class BaseTransaction(BaseModel):
    retries: int = 0
    duration_ms: int = 0
    rx_timeout_ms: int = 0

class LoraTransaction(BaseTransaction):
    request: LoRaTxPacket | None = None
    answer: LoRaRxPacket | None = None

class FSK_Transaction(BaseTransaction):
    request: FSK_TX_Packet | None = None
    answer: FSK_RX_Packet | None = None


class RadioTransaction(BaseTransaction):
    request: LoRaTxPacket | FSK_TX_Packet | None = None
    answer: LoRaRxPacket | FSK_RX_Packet | None = None
