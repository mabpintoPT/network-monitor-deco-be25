import asyncio
from network_monitor.main import AppState

async def main():
    s = AppState()

    print('ANTES:', s.repository.stats())

    await s.collect_once()

    print('DEPOIS:', s.repository.stats())
    print('ERRO:', s.last_collection_error)
    print('COUNT:', s.last_collection_count)
    print('TRAFFIC:', s.last_traffic_count)

    await s.stop()

asyncio.run(main())
