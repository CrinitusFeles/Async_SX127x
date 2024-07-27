


import asyncio
from async_sx127x.driver import SX127x_Driver
from async_sx127x.registers import (SX127x_DcFree, SX127x_FSK_SHAPING, SX127x_Modulation,
                                            SX127x_RestartRxMode)


async def init_fsk(ax25_mode: bool = False):
    await lora.interface.reset()
    await asyncio.sleep(0.1)

    await lora.set_modulation(SX127x_Modulation.FSK)
    await lora.set_frequency(437_497_497)  # 436_996_300
    await lora.set_tx_power(3)
    await lora.set_pa_select(True)

    await lora.set_fsk_bitrate(9600)
    await lora.set_fsk_deviation(4819)
    await lora.set_fsk_sync_mode(True)
    await lora.set_fsk_payload_length(100)
    await lora.set_fsk_preamble_length(3)
    await lora.set_fsk_data_shaping(SX127x_FSK_SHAPING.GAUSSIAN_1)
    await lora.set_fsk_fifo_threshold(15, immediate_tx=True)
    if ax25_mode:
        await lora.set_fsK_packet_format(False)
        await lora.set_fsk_dc_free_mode(SX127x_DcFree.OFF)
        await lora.set_fsk_crc(False)
        await lora.set_fsk_sync_value(bytes([0xFE, 0xFB, 0x91, 0xC5, 0xD5, 0xBE]))
        await lora.set_fsk_restart_rx_mode(SX127x_RestartRxMode.WAIT_PLL)
    else:
        await lora.set_fsK_packet_format(True)
        await lora.set_fsk_dc_free_mode(SX127x_DcFree.WHITENING)
        await lora.set_fsk_crc(True)
        await lora.set_fsk_sync_value(b'NSUNET')
        await lora.set_fsk_restart_rx_mode(SX127x_RestartRxMode.NO_WAIT_PLL)

    # await lora.set_standby_mode()

async def read_config():
    modulation = await lora.get_modulation()
    op_mode = await lora.get_operation_mode()
    freq = await lora.get_freq()
    tx_power = await lora.get_tx_power_dbm()
    print(f'{modulation=}\n{op_mode=}\n{freq=}\n{tx_power=}')

async def dump_regs():
    data: list[int] = await lora.interface.read_several(1, 100)
    for i, byte in enumerate(data, 1):
        print(f'0x{i:02X} 0x{byte:02X}')

async def main():
    await lora.connect('COM25')
    await init_fsk(False)
    await lora.set_rx_continuous_mode()
    await lora.interface.write_fsk_read_start()
    await dump_regs()
    await read_config()
    await lora.fsk_sequencer.start_tx()
    await lora.interface.write_fsk_fifo(bytes.fromhex('0E 0A 06 01 CB 01 01 01 01 00 3F 00 00 00 01'))
    print(await lora.get_operation_mode())
    await asyncio.sleep(1)
    print(await lora.get_operation_mode())
    # await lora.set_rx_continuous_mode()
    # await lora.interface.write_fsk_read_start()

if __name__ == '__main__':
    lora: SX127x_Driver = SX127x_Driver('Serial')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        lora.disconnect()