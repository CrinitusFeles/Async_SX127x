from __future__ import annotations
import math
from typing import Literal
from loguru import logger
from async_sx127x.interfaces.base_interface import BaseInterface
from async_sx127x.interfaces.ethernet import EthernetInterface
from async_sx127x.interfaces.serial import SerialInterface
from async_sx127x.registers_and_params import (SX127x_FSK_ISR, SX127x_HeaderMode,
                                            SX127x_PA_Pin, SX127x_Registers,
                                            SX127x_Mode, SX127x_LoRa_ISR,
                                            SX127x_CR, SX127x_Modulation,
                                            SX127x_ReastartRxMode, SX127x_BW,
                                            SX127x_DcFree, Sequencer)


# async def exception_handler(func: Callable):
#     async def _wrapper(*args, **kwargs):
#         try:
#             return await func(*args, **kwargs)
#         except ValueError as err:
#             logger.error(err)
#             return None
#     return _wrapper

def twos_comp(val, bits):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val                         # return positive value as is

class SX127x_Driver:
    reg = SX127x_Registers
    mode = SX127x_Mode
    isr = SX127x_LoRa_ISR
    bw = SX127x_BW
    cr = SX127x_CR

    FXOSC = 32_000_000
    F_STEP: float = FXOSC / 524288

    _bw_khz: dict = {key.value: value for key, value in zip(bw, [7.8, 10.4, 15.6, 20.8, 31.25, 41.7, 62.5, 125, 250,
                                                                 500])}

    def __init__(self, interface: Literal['Ethernet', 'Serial'] = 'Ethernet', **kwargs) -> None:
        self.interface: BaseInterface = EthernetInterface() if interface == 'Ethernet' else SerialInterface()
        self.fsk_sequencer = Sequencer(self.interface)
        self.pa_boost: bool = kwargs.get('pa_boost', True)
        if interface == 'Ethernet':
            self.pa_boost = False
        logger.info(f'PA_BOOST = {self.pa_boost}')

    def set_interface(self, interface: BaseInterface) -> None:
        self.interface = interface

    async def connect(self, port_or_ip: str) -> bool:
        return await self.interface.connect(port_or_ip)

    def disconnect(self) -> bool:
        return self.interface.disconnect()

    async def reset(self) -> None:
        await self.interface.reset()

    # @exception_handler
    async def get_modulation(self) -> SX127x_Modulation:
        result: int = await self.interface.read(SX127x_Registers.OP_MODE.value)
        return SX127x_Modulation(result & 0x80)

    # @exception_handler
    async def get_operation_mode(self) -> SX127x_Mode:
        resutl: int = await self.interface.read(SX127x_Registers.OP_MODE.value)
        return SX127x_Mode(resutl & 0x07)

    async def set_sleep_mode(self) -> None:
        reg: int = await self.interface.read(SX127x_Registers.OP_MODE.value)
        await self.interface.write(SX127x_Registers.OP_MODE.value, [(reg & 0xF8) | SX127x_Mode.SLEEP.value])

    async def set_standby_mode(self) -> None:
        reg: int = await self.interface.read(SX127x_Registers.OP_MODE.value)
        await self.interface.write(SX127x_Registers.OP_MODE.value, [(reg & 0xF8) | SX127x_Mode.STDBY.value])

    async def set_modulation(self, modulation: SX127x_Modulation) -> None:
        await self.set_sleep_mode()
        reg: int = await self.interface.read(SX127x_Registers.OP_MODE.value)
        await self.interface.write(SX127x_Registers.OP_MODE.value, [(reg & 0x7F) | modulation.value])

    async def set_lora_header_mode(self, mode: SX127x_HeaderMode) -> None:
        reg: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_1.value) & 0xFE
        await self.interface.write(SX127x_Registers.LORA_MODEM_CONFIG_1.value, [reg | mode.value])

    # @exception_handler
    async def get_lora_header_mode(self) -> SX127x_HeaderMode:
        result: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_1.value)
        return SX127x_HeaderMode(result & 0x01)

    async def set_lora_coding_rate(self, coding_rate: SX127x_CR) -> None:
        cr: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_1.value) & 0xF1
        await self.interface.write(SX127x_Registers.LORA_MODEM_CONFIG_1.value, [cr | coding_rate.value])

    # @exception_handler
    async def get_lora_coding_rate(self) -> SX127x_CR:
        result: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_1.value)
        return SX127x_CR(result & 0x0E)

    async def set_lora_bandwidth(self, bandwidth: SX127x_BW) -> None:
        bw: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_1.value) & 0x0F
        await self.interface.write(SX127x_Registers.LORA_MODEM_CONFIG_1.value, [bw | bandwidth.value])

    async def set_lora_payload_length(self, payload_length) -> None:
        await self.interface.write(SX127x_Registers.LORA_PAYLOAD_LENGTH.value, [payload_length])

    async def get_lora_payload_length(self) -> int:
        return await self.interface.read(SX127x_Registers.LORA_PAYLOAD_LENGTH.value)

    # @exception_handler
    async def get_lora_bandwidth(self) -> SX127x_BW:
        data: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_1.value)
        return SX127x_BW(data & 0xF0)

    async def get_lora_bw_khz(self) -> float:
        bw: SX127x_BW = await self.get_lora_bandwidth()
        return self._bw_khz[bw.value]

    async def set_lora_sf(self, spreading_factor: int) -> None:
        if 6 <= spreading_factor <= 12:
            sf: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_2.value) & 0x0F
            await self.interface.write(SX127x_Registers.LORA_MODEM_CONFIG_2.value, [sf | spreading_factor << 4])
        else:
            raise ValueError(f'Incorrect SF value {spreading_factor}. SF must be from 6 to 12.')

    async def get_lora_sf(self) -> int:
        result: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_2.value)
        return (result & 0xF0) >> 4

    async def set_lora_crc_mode(self, enable: bool) -> None:
        crc: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_2.value) & 0xfb
        await self.interface.write(SX127x_Registers.LORA_MODEM_CONFIG_2.value, [crc | (enable << 2)])

    async def get_lora_crc_mode(self) -> bool:
        result: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_2.value)
        return bool(result & 0x04)

    async def __disable_ocp(self) -> None:
        await self.interface.write(SX127x_Registers.OCP.value, [0x1f])

    async def select_power_amp_pin(self, pin: SX127x_PA_Pin) -> None:
        reg: int = await self.interface.read(SX127x_Registers.PA_CONFIG.value) & 0x7F
        await self.interface.write(SX127x_Registers.PA_CONFIG.value, [(pin.value << 7) | reg])

    async def set_pa_select(self, pa_select: bool) -> None:
        reg: int = await self.interface.read(SX127x_Registers.PA_CONFIG.value) & 0x7F
        await self.interface.write(SX127x_Registers.PA_CONFIG.value, [(pa_select << 7) | reg])

    async def get_chip_version(self) -> int:
        return await self.interface.read(SX127x_Registers.VERSION.value)

    async def set_tx_power(self, power_dbm: int) -> None:
        """ -3 to 12 - RFO; 13 to 20 - PA_BOOST """

        await self.__disable_ocp()
        ENABLE_20dBm = 0x87
        DISABLE_20dBm = 0x84
        if power_dbm >= 20:
            power_dbm = 20
        elif power_dbm < -3:
            power_dbm = -3
        pa_select = SX127x_PA_Pin.PA_BOOST if self.pa_boost else SX127x_PA_Pin.RFO
        if not pa_select and power_dbm <= 12:
            max_output = 0x02 << 4  # 12dbm
            power_dbm += 3
        elif pa_select:
            max_output: int = 0x07 << 4
        else:
            raise ValueError('Incorrect power output! For RFO pin max output power is 12dBm')

        if not self.pa_boost:
            power_dbm = 15 if power_dbm > 15 else power_dbm
            await self.interface.write(SX127x_Registers.PA_DAC.value, [DISABLE_20dBm])
            await self.interface.write(SX127x_Registers.PA_CONFIG.value, [max_output | power_dbm])
        else:
            if 17 < power_dbm <= 20:
                await self.interface.write(SX127x_Registers.PA_DAC.value, [ENABLE_20dBm])
                power_dbm = 15  # Pout=Pmax-(15-OutputPower)
            else:
                await self.interface.write(SX127x_Registers.PA_DAC.value, [DISABLE_20dBm])
                power_dbm -= 2  # Pout=17-(15-OutputPower) [dBm]
            await self.interface.write(SX127x_Registers.PA_CONFIG.value, [(pa_select.value << 7) | power_dbm | max_output])

    async def get_tx_power_dbm(self) -> float:
        reg: int = await self.interface.read(SX127x_Registers.PA_CONFIG.value)
        max_output: float = 10.8 + 0.6 * ((reg >> 4) & 0x07)
        pa_select: int = reg >> 7
        output_power: int = reg & 0x0F
        output_power_dbm: float = (17 if pa_select else max_output) - (15 - (output_power))
        reg_pa_dac: int = await self.interface.read(SX127x_Registers.PA_DAC.value)
        if reg_pa_dac == 0x87:
            if output_power == 15:
                output_power_dbm = 20
        return output_power_dbm

    async def set_lora_sync_word(self, sync_word: int) -> None:
        if 0 <= sync_word <= 255:
            await self.interface.write(SX127x_Registers.LORA_SYNC_WORD.value, [sync_word])
        else:
            raise ValueError(f'Incorrect sync word value. Value must be from 0 to 255, but got {sync_word}.')

    async def get_lora_sync_word(self) -> int:
        return await self.interface.read(SX127x_Registers.LORA_SYNC_WORD.value)

    async def set_lora_preamble_length(self, length: int) -> None:
        if length > 100:
            raise ValueError('Incorrect preamble length. Max preamble length is 100.')
        length = 6 if length < 6 else length
        await self.interface.write(SX127x_Registers.LORA_PREAMBLE_MSB.value, [length >> 8, length & 0xFF])

    async def get_lora_preamble_length(self) -> int:
        return await self.interface.read(SX127x_Registers.LORA_PREAMBLE_MSB.value)

    async def set_lora_auto_gain_control(self, agc_flag: bool) -> None:
        lna_state: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_3.value) & 0xFB
        await self.interface.write(SX127x_Registers.LORA_MODEM_CONFIG_3.value, [lna_state | (agc_flag << 2)])

    async def get_lora_auto_gain_control(self) -> bool:
        answer: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_3.value)
        return bool(answer & 0x04)

    async def set_low_noize_amplifier(self, lna_gain: int, lna_boost: bool) -> None:
        """lna_gain = 1 - min gain; 6 - max gain"""
        await self.interface.write(SX127x_Registers.LNA.value, [(lna_gain << 5) + 3 * lna_boost])

    async def get_lna_boost(self) -> bool:
        answer: int = await self.interface.read(SX127x_Registers.LNA.value)
        return bool(answer & 0x03)

    async def get_lna_gain(self) -> int:
        answer: int = await self.interface.read(SX127x_Registers.LNA.value)
        return (answer & 0xE0) >> 5

    async def set_frequency(self, freq_hz: int) -> None:
        frf = int((freq_hz / self.FXOSC) * 524288)
        await self.interface.write(SX127x_Registers.FREQ_MSB.value, [frf >> 16, (frf >> 8) & 0xFF, frf & 0xFF])

    async def get_freq(self) -> int:
        freq: list[int] = await self.interface.read_several(SX127x_Registers.FREQ_MSB.value, 3)
        return int((freq[0] << 16 | freq[1] << 8 | freq[2]) * self.FXOSC / 524288)

    async def set_lora_fifo_addr_ptr(self, address: int) -> None:
        await self.interface.write(SX127x_Registers.LORA_FIFO_ADDR_PTR.value, [address])

    async def set_lora_rx_tx_fifo_base_addr(self, rx_ptr: int, tx_ptr: int) -> None:
        await self.interface.write(SX127x_Registers.LORA_FIFO_TX_BASE_ADDR.value, [tx_ptr, rx_ptr])

    async def write_fifo(self, data: list[int] | bytes, is_implicit: bool = False) -> None:
        await self.set_lora_fifo_addr_ptr(0)
        # if is_implicit:
        await self.set_lora_payload_length(len(data))
        await self.interface.write(SX127x_Registers.FIFO.value, [*data])

    async def write_fsk_fifo(self, data: bytes | list[int]) -> None:
        await self.interface.write(SX127x_Registers.FIFO.value, [len(data), *list(data)])

    async def set_lora_irq_flags_mask(self, mask: int) -> None:
        """
        0 bit - active interrupt
        1 bit - inactive interrupt
        """
        await self.interface.write(SX127x_Registers.LORA_IRQ_FLAGS_MASK.value, [mask])

    async def get_lora_irq_mask_register(self) -> int:
        return await self.interface.read(SX127x_Registers.LORA_IRQ_FLAGS_MASK.value)

    async def get_lora_isr_register(self) -> int:
        return await self.interface.read(SX127x_Registers.LORA_IRQ_FLAGS.value)

    async def get_lora_fei(self, bw_khz: float) -> int:
        data = bytes(await self.interface.read_several(SX127x_Registers.LORA_FEI_MSB.value, 3))
        f_err: int = int(twos_comp(int.from_bytes(data, 'big'), 20) * (1 << 24) / self.FXOSC * bw_khz / 500)
        return f_err

    async def get_lora_isr_list(self) -> list[str]:
        reg: int = await self.get_lora_isr_register()
        return [mask.name for mask in list(SX127x_FSK_ISR) if reg & mask.value]

    async def get_rx_done_flag(self) -> bool:
        answer: int = await self.interface.read(SX127x_Registers.LORA_IRQ_FLAGS.value)
        return bool(answer & SX127x_LoRa_ISR.RXDONE.value)

    async def get_tx_done_flag(self) -> bool:
        answer: int = await self.interface.read(SX127x_Registers.LORA_IRQ_FLAGS.value)
        return bool(answer & SX127x_LoRa_ISR.TXDONE.value)

    async def get_crc_flag(self) -> bool:
        data: int = await self.interface.read(SX127x_Registers.LORA_IRQ_FLAGS.value)
        return bool(data & SX127x_LoRa_ISR.PAYLOAD_CRC_ERROR.value)

    async def reset_irq_flags(self) -> None:
        await self.interface.write(SX127x_Registers.LORA_IRQ_FLAGS.value, [0xFF])

    async def set_low_data_rate_optimize(self, optimization_flag: bool) -> None:
        ldro: int = await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_3.value) & 0xf7
        await self.interface.write(SX127x_Registers.LORA_MODEM_CONFIG_3.value, [ldro | (optimization_flag * (1 << 3))])

    async def get_low_data_rate_optimize(self) -> bool:
        return bool(await self.interface.read(SX127x_Registers.LORA_MODEM_CONFIG_3.value) & 0x08)

    async def set_tx_mode(self) -> None:
        reg: int = await self.interface.read(SX127x_Registers.OP_MODE.value)
        await self.interface.write(SX127x_Registers.OP_MODE.value, [(reg & 0xF8) | SX127x_Mode.TX.value])

    async def set_rx_continuous_mode(self) -> None:
        reg: int = await self.interface.read(SX127x_Registers.OP_MODE.value)
        await self.interface.write(SX127x_Registers.OP_MODE.value, [(reg & 0xF8) | SX127x_Mode.RXCONT.value])

    async def get_all_registers(self) -> list[int]:
        return await self.interface.read_several(0x01, 0x70)

    async def set_fsk_bitrate(self, bitrate: int) -> None:
        frac: float = await self.get_fsk_bitrate_frac() / 16
        reg_bitrate = int(self.FXOSC / bitrate - frac)
        await self.interface.write(SX127x_Registers.FSK_BITRATE_MSB.value, [reg_bitrate >> 8, reg_bitrate & 0xFF])

    async def get_fsk_bitrate(self) -> int:
        frac: float = await self.get_fsk_bitrate_frac() / 16
        data: list[int] = await self.interface.read_several(SX127x_Registers.FSK_BITRATE_MSB.value, 2)
        return int(self.FXOSC / ((data[0] << 8) + data[1] + frac))

    async def set_fsk_bitrate_frac(self, frac: int) -> None:
        await self.interface.write(SX127x_Registers.BITRATE_FRAC.value, [frac])

    async def get_fsk_bitrate_frac(self) -> int:
        return await self.interface.read(SX127x_Registers.BITRATE_FRAC.value)

    async def set_fsk_preamble_length(self, preamble_length: int) -> None:
        await self.interface.write(SX127x_Registers.FSK_PREAMBLE_MSB.value, [preamble_length >> 8, preamble_length & 0xFF])

    async def get_fsk_preamble_length(self) -> int:
        data: list[int] = await self.interface.read_several(SX127x_Registers.FSK_PREAMBLE_MSB.value, 2)
        return data[0] << 8 | data[1]

    async def set_fsk_restart_rx_mode(self, mode: SX127x_ReastartRxMode) -> None:
        reg: int = await self.interface.read(SX127x_Registers.FSK_SYNC_CONFIG.value) & 0x3F
        await self.interface.write(SX127x_Registers.FSK_SYNC_CONFIG.value, [reg | (mode.value << 6)])

    async def get_fsk_restart_rx_mode(self) -> SX127x_ReastartRxMode:
        return SX127x_ReastartRxMode((await self.interface.read(SX127x_Registers.FSK_SYNC_CONFIG.value) & 0xC0) >> 6)

    async def set_fsk_sync_size(self, sync_size: int) -> None:
        reg: int = await self.interface.read(SX127x_Registers.FSK_SYNC_CONFIG.value) & 0xF8
        await self.interface.write(SX127x_Registers.FSK_SYNC_CONFIG.value, [reg | sync_size - 1])

    async def get_fsk_sync_size(self) -> int:
        return await self.interface.read(SX127x_Registers.FSK_SYNC_CONFIG.value) & 0x07

    async def set_fsk_sync_value(self, sync_word: bytes) -> None:
        await self.interface.write(SX127x_Registers.FSK_SYNC_VALUE1.value, list(sync_word))

    async def get_fsk_sync_value(self) -> bytes:
        return bytes(await self.interface.read_several(SX127x_Registers.FSK_SYNC_VALUE1.value, 8))

    async def set_fsk_dc_free_mode(self, mode: SX127x_DcFree) -> None:
        reg: int = await self.interface.read(SX127x_Registers.FSK_PACKET_CONFIG1.value) & 0x9F
        await self.interface.write(SX127x_Registers.FSK_PACKET_CONFIG1.value, [reg | (mode.value << 5)])

    # @exception_handler
    async def get_fsk_dc_free_mode(self) -> SX127x_DcFree:
        reg: int = await self.interface.read(SX127x_Registers.FSK_PACKET_CONFIG1.value)
        return SX127x_DcFree((reg & 0x60) >> 5)

    async def set_fstx_mode(self) -> None:
        reg: int = await self.interface.read(SX127x_Registers.OP_MODE.value)
        await self.interface.write(SX127x_Registers.OP_MODE.value, [(reg & 0xF8) | SX127x_Mode.FSTX.value])

    async def set_fsrx_mode(self) -> None:
        reg: int = await self.interface.read(SX127x_Registers.OP_MODE.value)
        await self.interface.write(SX127x_Registers.OP_MODE.value, [(reg & 0xF8) | SX127x_Mode.FSRX.value])

    async def set_fsk_crc(self, crc_mode: bool) -> None:
        reg: int = await self.interface.read(SX127x_Registers.FSK_PACKET_CONFIG1.value) & 0xEF
        await self.interface.write(SX127x_Registers.FSK_PACKET_CONFIG1.value, [reg | (crc_mode << 4)])

    async def get_fsk_crc(self) -> bool:
        return bool(await self.interface.read(SX127x_Registers.FSK_PACKET_CONFIG1.value) & 0x10)

    async def set_fsK_packet_format(self, packet_format: bool) -> None:
        """sets packet length format in fsk mode

        Args:
            packet_format (bool): True - packet has variable length; False - packet has fixed length
        """
        reg: int = await self.interface.read(SX127x_Registers.FSK_PACKET_CONFIG1.value) & 0x7F
        await self.interface.write(SX127x_Registers.FSK_PACKET_CONFIG1.value, [reg | (packet_format << 7)])

    async def get_fsk_packet_format(self) -> bool:
        return bool(await self.interface.read(SX127x_Registers.FSK_PACKET_CONFIG1.value) & 0x80)

    async def set_fsk_sync_mode(self, enable: bool) -> None:
        """Enables the Sync word generation and detection\n
        RegSyncConfig(0x27) 0x04 offset
        """
        reg: int = await self.interface.read(SX127x_Registers.FSK_SYNC_CONFIG.value) & 0xF7
        await self.interface.write(SX127x_Registers.FSK_SYNC_CONFIG.value, [reg | (enable << 4)])

    async def get_fsk_sync_mode(self) -> bool:
        return bool(await self.interface.read(SX127x_Registers.FSK_SYNC_CONFIG.value) & 0x10)

    async def set_fsk_fifo_threshold(self, threshold: int) -> None:
        reg: int = await self.interface.read(SX127x_Registers.FSK_FIFO_THRESH.value) & 0xC0
        await self.interface.write(SX127x_Registers.FSK_FIFO_THRESH.value, [reg | (threshold & 0x3F)])

    async def get_fsk_fifo_threshold(self) -> int:
        return await self.interface.read(SX127x_Registers.FSK_FIFO_THRESH.value) & 0x3F

    async def add_freq_ppm(self, ppm: float) -> None:
        freq: int = await self.get_freq()
        await self.set_frequency(freq - int(freq * ppm / 1_000_000))

    async def add_freq(self, freq_hz: int) -> None:
        freq: int = await self.get_freq()
        await self.set_frequency(freq - freq_hz)

    async def get_fsk_isr(self) -> int:
        data: list[int] = await self.interface.read_several(SX127x_Registers.FSK_IRQ_FLAGS1.value, 2)
        return (data[0] << 8) + data[1]

    async def get_fsk_isr_list(self) -> list[str]:
        reg: int = await self.get_fsk_isr()
        return [mask.name for mask in list(SX127x_FSK_ISR) if reg & mask.value]

    async def get_fsk_payload_length(self) -> int:
        data: list[int] = await self.interface.read_several(SX127x_Registers.FSK_PACKET_CONFIG2.value, 2)
        return ((data[0] & 0x07) << 8) + data[1]

    async def set_fsk_payload_length(self, payload_length: int) -> None:
        reg: int = await self.interface.read(SX127x_Registers.FSK_PACKET_CONFIG2.value) & 0xFC
        payload_high: int = payload_length >> 8
        payload_low: int =  payload_length & 0xFF
        await self.interface.write(SX127x_Registers.FSK_PACKET_CONFIG2.value, [reg | payload_high, payload_low])

    async def set_fsk_deviation(self, deviation_hz: int) -> None:
        fdev_high = math.ceil(deviation_hz / self.F_STEP) >> 8
        fdev_low = math.ceil(deviation_hz / self.F_STEP) & 0xFF
        await self.interface.write(SX127x_Registers.FSK_FDEV_MSB.value, [fdev_high, fdev_low])

    async def get_fsk_fei(self) -> int:
        data = bytes(await self.interface.read_several(SX127x_Registers.FSK_FEI_MSB.value, 2))
        f_err: int = int(twos_comp(int.from_bytes(data, 'big'), 16) * self.F_STEP)
        return f_err

    async def registers_dump(self) -> None:
        data: list[int] = await self.interface.read_several(1, 0x40)
        for i, val in enumerate(data, start=1):
            try:
                print(f'{SX127x_Registers(i).name} (0x{i:02X}): 0x{val:02X}')
            except ValueError:
                print(f'(0x{i:02X}): 0x{val:02X}')

