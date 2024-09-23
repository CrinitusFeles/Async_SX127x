from loguru import logger

from async_sx127x.interfaces.base_interface import BaseInterface
import asyncio


class EthernetInterface(BaseInterface):
    async def connect(self, ip_or_port: str) -> bool:
        if self.connection_status:
            return True
        try:
            self.reader, self.writer = await asyncio.open_connection(ip_or_port, 80)
            self._read = self.reader.read
            self._write = self._tcp_write
            self.connection_status = True
            return True
        except ConnectionRefusedError:
            logger.error('Radio connected in another thread! Connection refused')
            return False


    async def _tcp_write(self, data):
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
