from __future__ import annotations
from loguru import logger

from async_sx127x.interfaces.base_interface import BaseInterface
import asyncio


class EthernetInterface(BaseInterface):
    async def connect(self, ip: str) -> bool:
        if self.connection_status:
            return True
        try:
            self.reader, self.writer = await asyncio.open_connection(ip, 80)
            self._read = self.reader.read
            self._write = self._interface.send
            self._interface.settimeout(2)
            try:
                self._interface.connect((ip, 80))
            except ConnectionRefusedError:
                logger.error('Radio connected in another thread! Connection refused')
                return False
            self.connection_status = True
            return True
        except TimeoutError:
            logger.error('Radio connectoin timeout!')
            return False

    async def _write(self, data):
        self.writer.write(data)
        await self.writer.drain()

    async def disconnect(self) -> bool:
        if self.connection_status:
            self.writer.close()
            await self.writer.wait_closed()
            self.connection_status = False
            return True
        return False


if __name__ == '__main__':
    ser: EthernetInterface = EthernetInterface()
    logger.debug(ser.connect('10.6.1.99'))
