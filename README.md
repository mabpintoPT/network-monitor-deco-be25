# Network Monitor 1.4

Network Monitor local para TP-Link Deco, com foco em presença e tráfego por dispositivo.

## V1.4

- Estado online/offline por dispositivo.
- Histórico de sessões de presença.
- Nome + MAC nas últimas sessões.
- Consulta local do endpoint `admin/client?form=traffic_stat`.
- Armazenamento de contadores cumulativos de download/upload.
- Cálculo de consumo por sessão através das diferenças entre recolhas.
- Detalhe de dispositivo com IP, MAC, estado atual e histórico de ligações/tráfego.
- SQLite persistente.
- FastAPI + HTML/CSS/JS.

> Os contadores de tráfego são os fornecidos pela API local da Deco. A V1.4 não transforma velocidades instantâneas em consumo.

## Desenvolvimento

```powershell
pip install -e ".[dev]"
pytest
uvicorn network_monitor.main:app --host 0.0.0.0 --port 8000
```

Abrir `http://127.0.0.1:8000`.

## Docker

```powershell
docker compose up -d --build
```

O port interno continua a ser 8000 e o host usa `HOST_PORT`.
