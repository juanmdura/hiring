# Scripts en run/

## Web del agente

Para levantar la interfaz web del agente (calibrator):

```bash
# Desde la raíz del proyecto
python run/run_agent_web.py
```

O directamente con ADK:

```bash
cd "candidates calibrator"
adk web --port 8000
```

Abre en el navegador: **http://localhost:8000**

Requisitos: `google-adk` instalado (`pip install google-adk`).

## Otros

- `python run/oauth_login.py` — login OAuth para Google Docs/Drive (guarda access token en config/.env).
- `python run/run_calibrator.py` — ejecuta el calibrator por lotes (candidates con score -1).
- `python run/verify_setup.py` — comprueba Gemini y config.
