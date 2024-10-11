from __future__ import annotations
from ast import literal_eval
import math
from typing import Literal
from loguru import logger
from async_sx127x.fsk_sequencer import Sequencer
from async_sx127x.interfaces.base_interface import BaseInterface
from async_sx127x.interfaces.ethernet import EthernetInterface
from async_sx127x.interfaces.serial import SerialInterface
from async_sx127x.registers import (SX127x_Modulation, SX127x_RestartRxMode,
                                    SX127x_FSK_ISR, SX127x_FSK_SHAPING,
                                    SX127x_HeaderMode, SX127x_PA_Pin,
                                    SX127x_Registers, SX127x_Mode, SX127x_BW,
                                    SX127x_LoRa_ISR, SX127x_CR, SX127x_DcFree)


def twos_comp(val, bits: int):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val                         # return positive value as is

class SX127x_Driver:
    interface: BaseInterface

    FXOSC = 32_000_000
    F_STEP: float = FXOSC / 524288

    bw: dict[float, SX127x_BW] = {
        7.8: SX127x_BW.BW7_8,
        10.4: SX127x_BW.BW10_4,
        15.6: SX127x_BW.BW15_6,
        20.8: SX127x_BW.BW20_8,
        31.25: SX127x_BW.BW31_25,
        41.7: SX127x_BW.BW41_7,
        62.5: SX127x_BW.BW62_5,
        125: SX127x_BW.BW125,
        250: SX127x_BW.BW250,
        500: SX127x_BW.BW500
    }

    def __init__(self, interface: Literal['Ethernet', 'Serial'] = 'Ethernet',
                 **kwargs) -> None:
        if interface == 'Ethernet':
            self.interface = EthernetInterface()
        else:
           self.interface = SerialInterface()
        self.fsk_sequencer = Sequencer(self.interface)
        if interface == 'Ethernet':
            self.pa_boost = False
        self.pa_boost: bool = kwargs.get('pa_boost', True)
        logger.info(f'PA_BOOST = {self.pa_boost}')

    def set_interface(self, interface: BaseInterface) -> None:
        self.interface = interface

    async def connect(self, port_or_ip: str) -> bool:
        return await self.interface.connect(port_or_ip)

    async def disconnect(self) -> bool:
        return await self.interface.disconnect()

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
        addr = SX127x_Registers.OP_MODE.value
        reg: int = await self.interface.read(addr)
        await self.interface.write(addr,
                                   [(reg & 0xF8) | SX127x_Mode.SLEEP.value])

    async def set_standby_mode(self) -> None:
        addr = SX127x_Registers.OP_MODE.value
        reg: int = await self.interface.read(addr)
        await self.interface.write(addr,
                                   [(reg & 0xF8) | SX127x_Mode.STDBY.value])

    async def set_modulation(self, modulation: SX127x_Modulation) -> None:
        await self.set_sleep_mode()
        addr = SX127x_Registers.OP_MODE.value
        reg: int = await self.interface.read(addr)
        await self.interface.write(addr, [(reg & 0x7F) | modulation.value])

    async def set_lora_header_mode(self, mode: SX127x_HeaderMode) -> None:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_1.value
        reg: int = await self.interface.read(addr) & 0xFE
        await self.interface.write(addr, [reg | mode.value])

    # @exception_handler
    async def get_lora_header_mode(self) -> SX127x_HeaderMode:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_1.value
        result: int = await self.interface.read(addr)
        return SX127x_HeaderMode(result & 0x01)

    async def set_lora_coding_rate(self, coding_rate: SX127x_CR) -> None:
        addr =SX127x_Registers.LORA_MODEM_CONFIG_1.value
        cr: int = await self.interface.read(addr) & 0xF1
        await self.interface.write(addr, [cr | coding_rate.value])

    # @exception_handler
    async def get_lora_coding_rate(self) -> SX127x_CR:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_1.value
        result: int = await self.interface.read(addr)
        return SX127x_CR(result & 0x0E)

    async def set_lora_bandwidth(self, bandwidth: SX127x_BW) -> None:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_1.value
        bw: int = await self.interface.read(addr) & 0x0F
        await self.interface.write(addr, [bw | bandwidth.value])

    async def set_lora_payload_length(self, payload_length) -> None:
        addr = SX127x_Registers.LORA_PAYLOAD_LENGTH.value
        await self.interface.write(addr, [payload_length])

    async def get_lora_payload_length(self) -> int:
        addr = SX127x_Registers.LORA_PAYLOAD_LENGTH.value
        return await self.interface.read(addr)

    # @exception_handler
    async def get_lora_bandwidth(self) -> int | float:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_1.value
        data: int = await self.interface.read(addr)
        return literal_eval(SX127x_BW(data & 0xF0).name.replace('_', '.'))

    async def set_lora_sf(self, spreading_factor: int) -> None:
        if 6 <= spreading_factor <= 12:
            addr = SX127x_Registers.LORA_MODEM_CONFIG_2.value
            sf: int = await self.interface.read(addr) & 0x0F
            await self.interface.write(addr, [sf | spreading_factor << 4])
        else:
            raise ValueError(f'Incorrect SF value {spreading_factor}. SF must'\
                             f' be from 6 to 12.')

    async def get_lora_sf(self) -> int:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_2.value
        result: int = await self.interface.read(addr)
        return (result & 0xF0) >> 4

    async def set_lora_crc_mode(self, enable: bool) -> None:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_2.value
        crc: int = await self.interface.read(addr) & 0xfb
        await self.interface.write(addr, [crc | (enable << 2)])

    async def get_lora_crc_mode(self) -> bool:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_2.value
        result: int = await self.interface.read(addr)
        return bool(result & 0x04)

    async def __disable_ocp(self) -> None:
        await self.interface.write(SX127x_Registers.OCP.value, [0x2B])

    async def select_power_amp_pin(self, pin: SX127x_PA_Pin) -> None:
        addr = SX127x_Registers.PA_CONFIG.value
        reg: int = await self.interface.read(addr) & 0x7F
        await self.interface.write(addr, [(pin.value << 7) | reg])

    async def set_pa_select(self, pa_select: bool) -> None:
        addr = SX127x_Registers.PA_CONFIG.value
        reg: int = await self.interface.read(addr) & 0x7F
        await self.interface.write(addr, [(pa_select << 7) | reg])

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
        if self.pa_boost:
            pa_select = SX127x_PA_Pin.PA_BOOST
        else:
            pa_select = SX127x_PA_Pin.RFO
        if not pa_select and power_dbm <= 12:
            max_output = 0x02 << 4  # 12dbm
            power_dbm += 3
        elif pa_select:
            max_output: int = 0x07 << 4
        else:
            raise ValueError('Incorrect power output! For RFO pin max output '\
                             'power is 12dBm')

        if not self.pa_boost:
            power_dbm = 15 if power_dbm > 15 else power_dbm
            await self.interface.write(SX127x_Registers.PA_DAC.value,
                                       [DISABLE_20dBm])
            await self.interface.write(SX127x_Registers.PA_CONFIG.value,
                                       [max_output | power_dbm])
        else:
            if 17 < power_dbm <= 20:
                await self.interface.write(SX127x_Registers.PA_DAC.value,
                                           [ENABLE_20dBm])
                power_dbm = 15  # Pout=Pmax-(15-OutputPower)
            else:
                await self.interface.write(SX127x_Registers.PA_DAC.value,
                                           [DISABLE_20dBm])
                power_dbm -= 2  # Pout=17-(15-OutputPower) [dBm]
            data: int = (pa_select.value << 7) | power_dbm | max_output
            await self.interface.write(SX127x_Registers.PA_CONFIG.value, [data])

    async def get_tx_power_dbm(self) -> float:
        reg: int = await self.interface.read(SX127x_Registers.PA_CONFIG.value)
        max_output: float = 10.8 + 0.6 * ((reg >> 4) & 0x07)
        pa_select: int = reg >> 7
        output_power: int = reg & 0x0F
        if pa_select:
            output_power_dbm: float = 17 - (15 - output_power)
        else:
            output_power_dbm: float = max_output - (15 - output_power)

        reg_pa_dac: int = await self.interface.read(SX127x_Registers.PA_DAC.value)
        if reg_pa_dac == 0x87:
            if output_power == 15:
                output_power_dbm = 20
        return output_power_dbm

    async def set_lora_sync_word(self, sync_word: int) -> None:
        if 0 <= sync_word <= 255:
            await self.interface.write(SX127x_Registers.LORA_SYNC_WORD.value,
                                       [sync_word])
        else:
            raise ValueError(f'Incorrect sync word value. Value must be from '\
                             f'0 to 255, but got {sync_word}.')

    async def get_lora_sync_word(self) -> int:
        return await self.interface.read(SX127x_Registers.LORA_SYNC_WORD.value)

    async def set_lora_preamble_length(self, length: int) -> None:
        if length > 100:
            raise ValueError('Incorrect preamble length. Max preamble length '\
                             'is 100.')
        length = 6 if length < 6 else length
        await self.interface.write(SX127x_Registers.LORA_PREAMBLE_MSB.value,
                                   [length >> 8, length & 0xFF])

    async def get_lora_preamble_length(self) -> int:
        addr = SX127x_Registers.LORA_PREAMBLE_MSB.value
        return await self.interface.read(addr)

    async def set_lora_auto_gain_control(self, agc_flag: bool) -> None:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_3.value
        lna_state: int = await self.interface.read(addr) & 0xFB
        await self.interface.write(addr, [lna_state | (agc_flag << 2)])

    async def get_lora_auto_gain_control(self) -> bool:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_3.value
        answer: int = await self.interface.read(addr)
        return bool(answer & 0x04)

    async def set_low_noize_amplifier(self, lna_gain: int,
                                      lna_boost: bool) -> None:
        """lna_gain = 1 - min gain; 6 - max gain"""
        await self.interface.write(SX127x_Registers.LNA.value,
                                   [(lna_gain << 5) + 3 * lna_boost])

    async def get_lna_boost(self) -> bool:
        answer: int = await self.interface.read(SX127x_Registers.LNA.value)
        return bool(answer & 0x03)

    async def get_lna_gain(self) -> int:
        answer: int = await self.interface.read(SX127x_Registers.LNA.value)
        return (answer & 0xE0) >> 5

    async def set_frequency(self, freq_hz: int) -> None:
        frf = int((freq_hz / self.FXOSC) * 524288)
        await self.interface.write(SX127x_Registers.FREQ_MSB.value,
                                   [frf >> 16, (frf >> 8) & 0xFF, frf & 0xFF])

    async def get_freq(self) -> int:
        addr = SX127x_Registers.FREQ_MSB.value
        freq: list[int] = await self.interface.read_several(addr, 3)
        return int((freq[0] << 16 | freq[1] << 8 | freq[2]) * self.FXOSC / 524288)

    async def set_lora_fifo_addr_ptr(self, address: int) -> None:
        await self.interface.write(SX127x_Registers.LORA_FIFO_ADDR_PTR.value,
                                   [address])

    async def set_lora_rx_tx_fifo_base_addr(self, rx_ptr: int,
                                            tx_ptr: int) -> None:
        addr = SX127x_Registers.LORA_FIFO_TX_BASE_ADDR.value
        await self.interface.write(addr, [tx_ptr, rx_ptr])

    async def write_fifo(self, data: list[int] | bytes,
                         is_implicit: bool = False) -> None:
        await self.set_lora_fifo_addr_ptr(0)
        # if is_implicit:
        await self.set_lora_payload_length(len(data))
        await self.interface.write(SX127x_Registers.FIFO.value, [*data])

    async def write_fsk_fifo(self, data: bytes | list[int]) -> None:
        await self.interface.write(SX127x_Registers.FIFO.value,
                                   [len(data), *list(data)])

    async def read_fsk_fifo(self, data_len: int):
        addr: int = SX127x_Registers.FIFO.value
        return await self.interface.read_several(addr, data_len)

    async def set_lora_irq_flags_mask(self, mask: int) -> None:
        """
        0 bit - active interrupt
        1 bit - inactive interrupt
        """
        addr = SX127x_Registers.LORA_IRQ_FLAGS_MASK.value
        await self.interface.write(addr, [mask])

    async def get_lora_irq_mask_register(self) -> int:
        addr = SX127x_Registers.LORA_IRQ_FLAGS_MASK.value
        return await self.interface.read(addr)

    async def get_lora_isr_register(self) -> int:
        return await self.interface.read(SX127x_Registers.LORA_IRQ_FLAGS.value)

    async def get_lora_fei(self, bw_khz: float) -> int:
        addr = SX127x_Registers.LORA_FEI_MSB.value
        data = bytes(await self.interface.read_several(addr, 3))
        raw_val: int = twos_comp(int.from_bytes(data, 'big'), 20)
        f_err: int = int(raw_val * (1 << 24) / self.FXOSC * bw_khz / 500)
        return f_err

    async def get_lora_isr_list(self) -> list[str]:
        reg: int = await self.get_lora_isr_register()
        return [mask.name for mask in list(SX127x_FSK_ISR) if reg & mask.value]

    async def get_rx_done_flag(self) -> bool:
        addr = SX127x_Registers.LORA_IRQ_FLAGS.value
        answer: int = await self.interface.read(addr)
        return bool(answer & SX127x_LoRa_ISR.RXDONE.value)

    async def get_lora_fifo_ptr(self) -> int:
        addr = SX127x_Registers.LORA_FIFO_RX_CURRENT_ADDR.value
        return await self.interface.read(addr)

    async def read_lora_fifo(self, data_len: int) -> bytes:
        addr: int = SX127x_Registers.FIFO.value
        return bytes(await self.interface.read_several(addr, data_len))

    async def get_tx_done_flag(self) -> bool:
        addr = SX127x_Registers.LORA_IRQ_FLAGS.value
        answer: int = await self.interface.read(addr)
        return bool(answer & SX127x_LoRa_ISR.TXDONE.value)

    async def get_crc_flag(self) -> bool:
        addr = SX127x_Registers.LORA_IRQ_FLAGS.value
        data: int = await self.interface.read(addr)
        return bool(data & SX127x_LoRa_ISR.PAYLOAD_CRC_ERROR.value)

    async def reset_irq_flags(self) -> None:
        addr = SX127x_Registers.LORA_IRQ_FLAGS.value
        await self.interface.write(addr, [0xFF])

    async def set_low_data_rate_optimize(self, optimization_flag: bool) -> None:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_3.value
        ldro: int = await self.interface.read(addr) & 0xf7
        await self.interface.write(addr,
                                   [ldro | (optimization_flag * (1 << 3))])

    async def get_low_data_rate_optimize(self) -> bool:
        addr = SX127x_Registers.LORA_MODEM_CONFIG_3.value
        return bool(await self.interface.read(addr) & 0x08)

    async def set_tx_mode(self) -> None:
        addr = SX127x_Registers.OP_MODE.value
        reg: int = await self.interface.read(addr)
        await self.interface.write(addr, [(reg & 0xF8) | SX127x_Mode.TX.value])

    async def set_rx_continuous_mode(self) -> None:
        addr = SX127x_Registers.OP_MODE.value
        reg: int = await self.interface.read(addr)
        await self.interface.write(addr,
                                   [(reg & 0xF8) | SX127x_Mode.RXCONT.value])

    async def get_all_registers(self) -> list[int]:
        return await self.interface.read_several(0x01, 0x70)

    async def get_lora_rssi_packet(self, freq_hz: int) -> int:
        addr = SX127x_Registers.LORA_PKT_RSSI_VALUE.value
        raw_val: int = await self.interface.read(addr)
        return raw_val - (164 if freq_hz < 0x779E6 else 157)

    async def get_lora_rssi_value(self, freq_hz: int) -> int:
        addr = SX127x_Registers.LORA_RSSI_VALUE.value
        raw_val: int = await self.interface.read(addr)
        return raw_val - (164 if freq_hz < 0x779E6 else 157)

    async def get_lora_snr(self) -> int:
        addr = SX127x_Registers.LORA_PKT_SNR_VALUE.value
        return await self.interface.read(addr) // 4

    async def get_snr_and_rssi(self, freq_hz: int) -> tuple[int, int]:
        addr = SX127x_Registers.LORA_PKT_SNR_VALUE.value
        data: list[int] = await self.interface.read_several(addr, 2)
        if len(data) == 2:
            snr, rssi = data[0], data[1]
            return snr // 4, rssi - (164 if freq_hz < 0x779E6 else 157)
        return 0, 0

    async def set_fsk_bitrate(self, bitrate: int) -> None:
        frac: float = await self._get_fsk_bitrate_frac() / 16
        reg_bitrate = int(self.FXOSC / bitrate - frac)
        addr = SX127x_Registers.FSK_BITRATE_MSB.value
        await self.interface.write(addr, [reg_bitrate >> 8, reg_bitrate & 0xFF])

    async def get_fsk_bitrate(self) -> int:
        frac: float = await self._get_fsk_bitrate_frac() / 16
        addr = SX127x_Registers.FSK_BITRATE_MSB.value
        data: list[int] = await self.interface.read_several(addr, 2)
        return int(self.FXOSC / ((data[0] << 8) + data[1] + frac))

    async def set_fsk_bitrate_frac(self, frac: int) -> None:
        await self.interface.write(SX127x_Registers.BITRATE_FRAC.value, [frac])

    async def _get_fsk_bitrate_frac(self) -> int:
        return await self.interface.read(SX127x_Registers.BITRATE_FRAC.value)

    async def set_fsk_preamble_length(self, preamble: int) -> None:
        addr = SX127x_Registers.FSK_PREAMBLE_MSB.value
        await self.interface.write(addr, [preamble >> 8, preamble & 0xFF])

    async def get_fsk_preamble_length(self) -> int:
        addr = SX127x_Registers.FSK_PREAMBLE_MSB.value
        data: list[int] = await self.interface.read_several(addr, 2)
        return data[0] << 8 | data[1]

    async def set_fsk_restart_rx_mode(self, mode: SX127x_RestartRxMode) -> None:
        addr = SX127x_Registers.FSK_SYNC_CONFIG.value
        reg: int = await self.interface.read(addr) & 0x3F
        await self.interface.write(SX127x_Registers.FSK_SYNC_CONFIG.value,
                                   [reg | (mode.value << 6)])

    async def get_fsk_restart_rx_mode(self) -> SX127x_RestartRxMode:
        addr = SX127x_Registers.FSK_SYNC_CONFIG.value
        data: int = await self.interface.read(addr)
        return SX127x_RestartRxMode((data & 0xC0) >> 6)

    async def get_fsk_sync_size(self) -> int:
        addr = SX127x_Registers.FSK_SYNC_CONFIG.value
        return await self.interface.read(addr) & 0x07

    async def set_fsk_sync_value(self, sync_word: bytes) -> None:
        addr = SX127x_Registers.FSK_SYNC_CONFIG.value
        reg: int = await self.interface.read(addr) & 0xF8
        await self.interface.write(addr, [reg | len(sync_word) - 1])
        await self.interface.write(SX127x_Registers.FSK_SYNC_VALUE1.value,
                                   list(sync_word))

    async def get_fsk_sync_value(self, sync_len: int = 8) -> bytes:
        addr = SX127x_Registers.FSK_SYNC_VALUE1.value
        return bytes(await self.interface.read_several(addr, sync_len))

    async def set_fsk_dc_free_mode(self, mode: SX127x_DcFree) -> None:
        addr = SX127x_Registers.FSK_PACKET_CONFIG1.value
        reg: int = await self.interface.read(addr) & 0x9F
        await self.interface.write(addr, [reg | (mode.value << 5)])

    async def set_fsk_data_shaping(self, shaping: SX127x_FSK_SHAPING) -> None:
        addr = SX127x_Registers.PA_RAMP.value
        reg: int = await self.interface.read(addr) & 0x0F
        await self.interface.write(addr, [reg | (shaping.value << 5)])

    async def get_fsk_dc_free_mode(self) -> SX127x_DcFree:
        addr = SX127x_Registers.FSK_PACKET_CONFIG1.value
        reg: int = await self.interface.read(addr)
        return SX127x_DcFree((reg & 0x60) >> 5)

    async def set_fstx_mode(self) -> None:
        addr = SX127x_Registers.OP_MODE.value
        reg: int = await self.interface.read(addr)
        await self.interface.write(addr, [(reg & 0xF8) | SX127x_Mode.FSTX.value])

    async def set_fsrx_mode(self) -> None:
        addr = SX127x_Registers.OP_MODE.value
        reg: int = await self.interface.read(addr)
        await self.interface.write(addr, [(reg & 0xF8) | SX127x_Mode.FSRX.value])

    async def set_fsk_crc(self, crc_mode: bool) -> None:
        addr = SX127x_Registers.FSK_PACKET_CONFIG1.value
        reg: int = await self.interface.read(addr) & 0xEF
        await self.interface.write(addr, [reg | (crc_mode << 4)])

    async def fsk_clear_fifo_on_crc_fail(self, mode: bool):
        addr = SX127x_Registers.FSK_PACKET_CONFIG1.value
        reg: int = await self.interface.read(addr) & 0xF7
        await self.interface.write(addr, [reg | ((not mode) << 3)])

    async def get_fsk_crc(self) -> bool:
        addr = SX127x_Registers.FSK_PACKET_CONFIG1.value
        return bool(await self.interface.read(addr) & 0x10)

    async def set_fsK_packet_format(self, packet_format: bool) -> None:
        addr = SX127x_Registers.FSK_PACKET_CONFIG1.value
        reg: int = await self.interface.read(addr) & 0x7F
        await self.interface.write(addr, [reg | (packet_format << 7)])

    async def get_fsk_packet_format(self) -> bool:
        addr = SX127x_Registers.FSK_PACKET_CONFIG1.value
        return bool(await self.interface.read(addr) & 0x80)

    async def set_fsk_sync_mode(self, enable: bool) -> None:
        """Enables the Sync word generation and detection\n
        RegSyncConfig(0x27) 0x04 offset
        """
        addr = SX127x_Registers.FSK_SYNC_CONFIG.value
        reg: int = await self.interface.read(addr) & 0xF7
        await self.interface.write(addr, [reg | (enable << 4)])

    async def get_fsk_sync_mode(self) -> bool:
        addr = SX127x_Registers.FSK_SYNC_CONFIG.value
        return bool(await self.interface.read(addr) & 0x10)

    async def set_fsk_fifo_threshold(self, threshold: int,
                                     immediate_tx: bool = False) -> None:
        addr = SX127x_Registers.FSK_FIFO_THRESH.value
        await self.interface.write(addr, [immediate_tx << 7 | threshold])

    async def get_fsk_fifo_threshold(self) -> int:
        addr = SX127x_Registers.FSK_FIFO_THRESH.value
        return await self.interface.read(addr) & 0x3F

    async def add_freq_ppm(self, ppm: float) -> int:
        freq: int = await self.get_freq()
        new_freq: int = freq - int(freq * ppm / 1_000_000)
        await self.set_frequency(new_freq)
        return new_freq

    async def add_freq(self, freq_hz: int) -> int:
        freq: int = await self.get_freq()
        await self.set_standby_mode()
        await self.set_frequency(freq - freq_hz)
        await self.set_rx_continuous_mode()
        return freq - freq_hz

    async def get_fsk_isr(self) -> int:
        addr = SX127x_Registers.FSK_IRQ_FLAGS1.value
        data: list[int] = await self.interface.read_several(addr, 2)
        return (data[0] << 8) + data[1]

    async def get_fsk_isr_list(self) -> list[str]:
        reg: int = await self.get_fsk_isr()
        return [mask.name for mask in list(SX127x_FSK_ISR) if reg & mask.value]

    async def get_fsk_payload_length(self) -> int:
        addr = SX127x_Registers.FSK_PACKET_CONFIG2.value
        data: list[int] = await self.interface.read_several(addr, 2)
        return ((data[0] & 0x07) << 8) + data[1]

    async def set_fsk_payload_length(self, payload_length: int) -> None:
        addr = SX127x_Registers.FSK_PACKET_CONFIG2.value
        reg: int = await self.interface.read(addr) & 0xFC
        payload_high: int = payload_length >> 8
        payload_low: int =  payload_length & 0xFF
        await self.interface.write(addr, [reg | payload_high, payload_low])

    async def set_fsk_deviation(self, deviation_hz: int) -> None:
        fdev_high: int = math.ceil(deviation_hz / self.F_STEP) >> 8
        fdev_low: int = math.ceil(deviation_hz / self.F_STEP) & 0xFF
        addr = SX127x_Registers.FSK_FDEV_MSB.value
        await self.interface.write(addr, [fdev_high, fdev_low])

    async def get_fsk_deviation(self) -> int:
        addr = SX127x_Registers.FSK_FDEV_MSB.value
        data: list[int] = await self.interface.read_several(addr, 2)
        return int((data[0] << 8 | data[1]) * self.F_STEP)

    async def get_fsk_fei(self) -> int:
        """ Works incorrectly on sx127x """
        addr = SX127x_Registers.FSK_FEI_MSB.value
        data = bytes(await self.interface.read_several(addr, 2))
        return int(twos_comp(int.from_bytes(data, 'big'), 16) * self.F_STEP)

    async def set_fsk_auto_afc(self, mode: bool):
        addr = SX127x_Registers.FSK_RX_CONFIG.value
        reg: int = await self.interface.read(addr) & 0xEF
        await self.interface.write(addr, [reg | (mode << 4)])

    async def fsk_clear_afc(self) -> None:
        addr = SX127x_Registers.FSK_AFC_FEI.value
        reg: int = await self.interface.read(addr)
        await self.interface.write(addr, [reg | (1 << 1)])

    async def set_fsk_autoclear_afc(self, mode: bool) -> None:
        addr = SX127x_Registers.FSK_AFC_FEI.value
        reg: int = await self.interface.read(addr)
        await self.interface.write(addr, [reg | mode])

    async def set_fsk_afc_bw(self, mantis: int, exp: int) -> None:
        addr = SX127x_Registers.FSK_AFC_BW.value
        reg: int = await self.interface.read(addr) & 0xE0
        await self.interface.write(addr, [reg | mantis << 3 | exp])

    async def get_fsk_afc(self) -> int:
        addr = SX127x_Registers.FSK_AFC_MSB.value
        data: bytes = bytes(await self.interface.read_several(addr, 2))
        return int(twos_comp(int.from_bytes(data, 'big'), 16) * self.F_STEP)

    async def get_fsk_rssi(self) -> int:
        addr = SX127x_Registers.FSK_RSSI_VALUE.value
        raw_val: int = await self.interface.read(addr)
        return -raw_val // 2

    async def registers_dump(self) -> None:
        data: list[int] = await self.interface.read_several(1, 0x40)
        for i, val in enumerate(data, start=1):
            try:
                print(f'{SX127x_Registers(i).name} (0x{i:02X}): 0x{val:02X}')
            except ValueError:
                print(f'(0x{i:02X}): 0x{val:02X}')
