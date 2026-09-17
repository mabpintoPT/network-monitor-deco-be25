from network_monitor.collectors.deco.client import DecoClient


def main():
    print("=" * 70)
    print("TESTE DE CONTADORES DE TRÁFEGO DO DECO")
    print("=" * 70)

    client = DecoClient()

    try:
        print("\n[1] A autenticar no Deco...")
        client.authenticate()
        print("    AUTENTICAÇÃO OK")

        print("\n[2] A consultar contadores de tráfego...")
        stats = client.get_traffic_stats()

        print(f"\n[3] Total de dispositivos recebidos: {len(stats)}")
        print("-" * 70)

        for item in stats:
            print(f"MAC:             {item.mac}")
            print(f"Download bytes:  {item.download_bytes}")
            print(f"Upload bytes:    {item.upload_bytes}")
            print("-" * 70)

        print("\n" + "=" * 70)
        print("TESTE TERMINADO")
        print("=" * 70)

    except Exception as e:
        print("\nERRO:")
        print(type(e).__name__)
        print(str(e))


if __name__ == "__main__":
    main()