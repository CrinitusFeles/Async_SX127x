from pydantic import BaseModel, field_serializer


class LoRaModel(BaseModel):
    spreading_factor: int
    coding_rate: str
    bandwidth: str
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

    @field_serializer('data')
    def serialize_data(self, dt: bytes, _info):
        return dt.hex().upper()


class LoRaRxPacket(RadioPacket):
    snr: int
    rssi_pkt: int
    crc_correct: bool
    fei: int
    mode: str = 'LoRa'
    caller: str = ''

    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}] ' if self.caller else ' '
        currepted_string: str = '(CORRUPTED) ' if not self.crc_correct else ' '
        return f"{self.timestamp} {caller_name}{self.mode} {currepted_string}"\
               f"Freq: {self.frequency:_}; "\
               f"FEI: {self.fei}; " \
               f"RSSI: {self.rssi_pkt}; snr: {self.snr};\n"\
               f"RX[{self.data_len}] < {self.data.hex(' ').upper()}"


class LoRaTxPacket(RadioPacket):
    Tpkt: float
    low_datarate_opt_flag: bool
    mode: str = 'LoRa'
    caller: str = ''
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}] ' if self.caller else ''
        return f"{self.timestamp} {self.mode} {caller_name} "\
               f"Freq: {self.frequency:_} "\
               f"TOF(ms): {round(self.Tpkt)};\n"\
               f"TX[{self.data_len}] > {self.data.hex(' ').upper()}"


class FSK_RX_Packet(RadioPacket):
    rssi: int
    crc_correct: bool
    mode: str = 'FSK'
    caller: str = ''
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}] ' if self.caller else ''
        currepted_string: str = '(CORRUPTED) ' if not self.crc_correct else ' '
        return f"{self.timestamp} {caller_name} {self.mode} {currepted_string}"\
               f"Freq: {self.frequency:_}; "\
               f"RSSI: {self.rssi};\n"\
               f"RX[{self.data_len}] < {self.data.hex(' ').upper()}"

class FSK_TX_Packet(RadioPacket):
    mode: str = 'FSK'
    caller: str = ''
    def __str__(self) -> str:
        caller_name: str = f'[{self.caller}] ' if self.caller else ''
        return f"{self.timestamp} {self.mode} {caller_name} "\
               f"Freq: {self.frequency:_}\n"\
               f"TX[{self.data_len}] > {self.data.hex(' ').upper()}"
