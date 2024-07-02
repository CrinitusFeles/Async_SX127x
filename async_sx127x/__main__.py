

import asyncio
from async_sx127x.radio_controller import RadioController


async def test():
    lora: RadioController = RadioController(interface='Serial', tx_power=2)
    if await lora.connect(port_or_ip='COM25'):  # 192.168.0.5
        print(await lora.read_config())
        rx_task = lora.rx_routine()
        cli_task = lora.user_cli()
        fut = await asyncio.gather(rx_task, cli_task)
        print(fut)

if __name__ == '__main__':
    asyncio.run(test())