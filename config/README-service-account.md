# Acceso online a Google Docs (OAuth)

El acceso a Docs y Drive se hace con **OAuth**: Client ID y Client Secret en `config/.env`. No se usa archivo de service account.

---

## 1. Obtener Client ID y Client Secret

1. Entra en [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Crea o selecciona un proyecto.
3. **Credenciales** → **Crear credenciales** → **ID de cliente de OAuth**.
4. Si te pide configurar la pantalla de consentimiento, hazlo (tipo “Externo” y añade tu cuenta de prueba si está en modo prueba).
5. Tipo de aplicación: **Aplicación web** (o **Desktop**).
6. Si eliges “Aplicación web”, en **URIs de redirección autorizados** agrega: `http://localhost:8080/`
7. Crea. En la pantalla (o en el JSON descargable) verás:
   - **ID de cliente** → ese valor es `GOOGLE_CLIENT_ID`
   - **Secreto de cliente** → ese valor es `GOOGLE_CLIENT_SECRET`
8. Copia ambos en `config/.env`:
   ```
   GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-xxxx
   ```

No hace falta “exportar” ningún archivo: solo copiar esos dos valores desde la consola al `.env`.

---

## 2. Obtener el refresh token (una sola vez)

1. En la consola, en tu cliente OAuth, confirma que está el URI de redirección: `http://localhost:8080/`
2. En el proyecto: `pip install google-auth-oauthlib`
3. Ejecuta: `python run/oauth_login.py`
4. Se abre el navegador; inicia sesión con la **cuenta de Google que tiene acceso a los Docs y a la carpeta de Drive**.
5. El script imprime `GOOGLE_REFRESH_TOKEN=...`. Copia ese valor y pégalo en `config/.env` en la línea `GOOGLE_REFRESH_TOKEN=...`

Con eso, el modo **online** usará tu cuenta para leer Docs y la carpeta de Drive (sin service account).

---

## Opción alternativa: Service account

Si prefieres no usar OAuth:

1. [Consola](https://console.cloud.google.com/iam-admin/serviceaccounts) → crear service account → crear clave (JSON) y descargar.
2. Guardar el JSON como `config/service_account.json` (está en `.gitignore`).
3. Compartir cada Doc (o la carpeta de Drive) con el email del service account (Lector).

---

## Carpeta de Google Drive

Si en `config/.env` defines **GOOGLE_DRIVE_FOLDER_ID** con el ID de la carpeta raíz de Drive, el sistema leerá desde sus **subcarpetas**:

| Subcarpeta              | Uso |
|-------------------------|-----|
| **transcripts**         | Google Docs de transcripciones; el nombre del doc debe contener el email del candidato (ej. `brunomembrado10@gmail.com`). |
| **scorecards-templates**| Google Docs de scorecards; el nombre debe contener el rol (ej. `Backend`) o la palabra `scorecard`. |

El ID de la carpeta raíz está en la URL: `https://drive.google.com/drive/folders/ESTE_ES_EL_ID`

Si no existen las subcarpetas, se busca en la carpeta raíz (comportamiento anterior). Orden del flujo: export URL → Docs API (por doc_id de config) → **Drive (subcarpetas o raíz)** → archivos locales en `data/`.

---

## Guardar reportes en Google Drive (Interviews/reports)

Puedes cambiar la carpeta de destino de dos formas:

1. **Por defecto:** en `config/drive_reports.json` está `reports_folder_id`. Ahí va el ID de la carpeta de Drive (por defecto: [esta carpeta](https://drive.google.com/drive/folders/12K-YFnnGpvG-Pg03IXvfZeQejhXMkOIn)). Edita ese archivo si quieres otra carpeta sin tocar `.env`.
2. **Override:** en `config/.env` define **GOOGLE_DRIVE_REPORTS_FOLDER_ID** y tendrá prioridad sobre `drive_reports.json`.

Para obtener el ID: crea en Drive la carpeta que quieras (p. ej. **Interviews** → **reports**), ábrela y copia el ID de la URL: `https://drive.google.com/drive/folders/ESTE_ES_EL_ID`

Cada vez que el agente genere un reporte, se guardará en `data/reports/` en local y además se subirá un archivo `.md` a esa carpeta de Drive. Para subir a Drive hace falta el scope `drive.file`; si añadiste esto después de obtener el refresh token, vuelve a ejecutar `python run/oauth_login.py` y actualiza `GOOGLE_REFRESH_TOKEN` en `.env`.
