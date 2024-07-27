from enum import Enum


class SX127x_Registers(Enum):
    FIFO = 0x00
    OP_MODE = 0x01
    FSK_BITRATE_MSB = 0x02
    FSK_BITRATE_LSB = 0x03
    FSK_FDEV_MSB = 0x04
    FSK_FDEV_LSB = 0x05
    FREQ_MSB = 0x06
    FREQ_MID = 0x07
    FREQ_LSB = 0x08
    PA_CONFIG = 0x09
    PA_RAMP = 0x0A
    OCP = 0x0B
    LNA = 0x0C
    LORA_FIFO_ADDR_PTR = 0x0D
    FSK_RX_CONFIG = 0x0D
    LORA_FIFO_TX_BASE_ADDR = 0x0E
    LORA_FIFO_RX_BASE_ADDR = 0x0F
    LORA_FIFO_RX_CURRENT_ADDR = 0x10
    LORA_IRQ_FLAGS_MASK = 0x11
    FSK_RSSI_VALUE = 0x11
    LORA_IRQ_FLAGS = 0x12
    LORA_RX_NB_BYTES = 0x13
    FSK_AFC_BW = 0x13
    LORA_RX_HEADER_CNT_VALUE_MSB = 0x14
    LORA_RX_HEADER_CNT_VALUE_LSB = 0x15
    LORA_RX_PACKET_CNT_VALUE_MSB = 0x16
    LORA_RX_PACKET_CNT_VALUE_LSB = 0x17
    LORA_PKT_SNR_VALUE = 0x19
    LORA_PKT_RSSI_VALUE = 0x1A
    FSK_AFC_FEI = 0x1A
    LORA_RSSI_VALUE = 0x1B
    FSK_AFC_MSB = 0x1B
    LORA_MODEM_CONFIG_1 = 0x1D
    FSK_FEI_MSB = 0x1D
    LORA_MODEM_CONFIG_2 = 0x1E
    LORA_PREAMBLE_MSB = 0x20
    LORA_PREAMBLE_LSB = 0x21
    LORA_PAYLOAD_LENGTH = 0x22
    LORA_FIFO_RX_BYTE_ADDR = 0x25
    LORA_MODEM_CONFIG_3 = 0x26
    FSK_PREAMBLE_MSB = 0x25
    FSK_PREAMBLE_LSB = 0x26
    FSK_SYNC_CONFIG = 0x27
    FSK_SYNC_VALUE1 = 0x28
    LORA_FEI_MSB = 0x28
    LORA_FEI_MID = 0x29
    LORA_FEI_LSB = 0x30
    FSK_PACKET_CONFIG1 = 0x30
    LORA_DETECT_OPTIMIZE = 0x31
    FSK_PACKET_CONFIG2 = 0x31
    FSK_PAYLOAND_LENGTH = 0x32
    FSK_FIFO_THRESH = 0x35
    FSK_SEQ_CONFIG1 = 0x36
    FSK_SEQ_CONFIG2 = 0x37
    LORA_DETECTION_THRESHOLD = 0x37
    FSK_TIMER_RES = 0x38
    LORA_SYNC_WORD = 0x39
    FSK_TEMP = 0x3c
    FSK_IRQ_FLAGS1 = 0x3e
    FSK_IRQ_FLAGS2 = 0x3f

    DIO_MAPPING_1 = 0x40
    DIO_MAPPING_2 = 0x41
    VERSION = 0x42
    PA_DAC = 0x4d

    BITRATE_FRAC = 0x5D

class SX127x_Mode(Enum):
    SLEEP = 0x00
    STDBY = 0x01
    FSTX = 0x02
    TX = 0x03
    FSRX = 0x04
    RXCONT = 0x05
    RXSINGLE = 0x06
    CAD = 0x07

class SX127x_FSK_ISR(Enum):
    MODE_READY = 1 << 15
    RX_READY = 1 << 14
    TX_READY = 1 << 13
    PLL_LOCK = 1 << 12
    RSSI = 1 << 11
    TIMEOUT = 1 << 10
    PREAMBLE_DETECT = 1 << 9
    SYNC_ADDR_MATCH = 1 << 8
    FIFO_FULL = 1 << 7
    FIFO_EMPTY = 1 << 6
    FIFO_LEVEL = 1 << 5
    FIFO_OVERRUN = 1 << 4
    PACKET_SENT = 1 << 3
    PAYLOAD_READY = 1 << 2
    CRC_OK = 1 << 1
    LOW_BAT = 1 << 0


class SX127x_Modulation(Enum):
    LORA = 0x80
    FSK = 0

class SX127x_HeaderMode(Enum):
    EXPLICIT = 0
    IMPLICIT = 1

class SX127x_PA_Pin(Enum):
    RFO = 0
    PA_BOOST = 1

class SX127x_LoRa_ISR(Enum):
    RX_TIMEOUT = 1 << 7
    RXDONE = 1 << 6
    PAYLOAD_CRC_ERROR = 1 << 5
    VALID_HEADER = 1 << 4
    TXDONE = 1 << 3
    CAD_DONE = 1 << 2
    FHSS_CHANGE_CHANNEL = 1 << 1
    CAD_DETECTED = 1 << 0


class SX127x_BW(Enum):
    BW7_8 = 0
    BW10_4 = 1 << 4
    BW15_6 = 2 << 4
    BW20_8 = 3 << 4
    BW31_25 = 4 << 4
    BW41_7 = 5 << 4
    BW62_5 = 6 << 4
    BW125 = 7 << 4
    BW250 = 8 << 4
    BW500 = 9 << 4


class SX127x_CR(Enum):
    CR5 = 1 << 1
    CR6 = 2 << 1
    CR7 = 3 << 1
    CR8 = 4 << 1


class SX127x_RestartRxMode(Enum):
    OFF = 0
    NO_WAIT_PLL = 1
    WAIT_PLL = 2

class SX127x_DcFree(Enum):
    OFF = 0
    MANCHESTER = 1
    WHITENING = 2

class SX127x_FSK_SHAPING(Enum):
    NO_SHAPING = 0
    GAUSSIAN_1 = 1
    GAUSSIAN_0_5 = 2
    GAUSSIAN_0_3 = 3
