# pdf-extractext-ms

API para extraer texto de archivos PDF y persistirlo en MongoDB con deduplicación por checksum, **delegando la extracción en un microservicio dedicado**.

Es la variante de `pdf-extractext` en la que la lógica de extracción ya no vive en la app: esta API valida, calcula el SHA-256, consulta al microservicio por HTTP (`POST /extract`) y persiste el resultado. Proyecto académico de **Desarrollo de Software 2026** — UTN Facultad Regional San Rafael.

## Cómo funciona

```
cliente ──► web (:8000) ──/api──► app (:8002) ──► Traefik ──► extractor ×5
                                      │
                                      └──► MongoDB
```

Este repositorio contiene **solo la API**. El front end y el microservicio de extracción son deployables independientes; no comparten código con esta app, solo el contrato HTTP. El stack completo se orquesta desde [`bar-bii/pdf-extractext-deploy`](https://github.com/bar-bii/pdf-extractext-deploy).

1. Recibe un PDF vía `multipart/form-data`.
2. Calcula el SHA-256 del PDF. Si ya existe, responde `409` **sin llamar al extractor**.
3. Envía el PDF al microservicio y obtiene el texto (`content`).
4. Persiste solo el texto y el checksum (nunca el binario) y lo devuelve.
5. Expone el CRUD de documentos persistidos.

El PDF nunca se escribe a disco en esta app.

## Arquitectura

Clean Architecture (`presentation → application ← data`):

- `application/` — puertos (`Protocol`: `PDFExtractor`, `ChecksumRepository`, `DocumentRepository`), excepciones de dominio y casos de uso (`extract_document`).
- `data/` — adaptadores: `HttpPDFExtractor` (cliente `httpx` del microservicio), modelos Beanie y repositorios de MongoDB.
- `presentation/main.py` — adaptador de entrada FastAPI: rutas contra puertos y mapeo de errores a HTTP.
- `presentation/container.py` — composition root: único lugar que liga adaptadores concretos a puertos (`lifespan` y providers de `Depends`).

Reglas de diseño y TDD: ver [`AGENTS.md`](AGENTS.md).

## Requisitos

- Python 3.13+ y [uv](https://docs.astral.sh/uv/)
- MongoDB para correr los tests de integración

## Correr el sistema completo

Cloná el repo de despliegue:

```bash
git clone https://github.com/bar-bii/pdf-extractext-deploy.git
cd pdf-extractext-deploy
docker compose up --build
```

- UI: `http://localhost:8000`
- Swagger: `http://localhost:8000/api/docs`
- API directa: `http://localhost:8002`

Ese repo fija este backend, el front y el extractor a commits concretos.

## Correr solo la API (desarrollo)

```bash
uv sync
docker run -d --rm -p 27017:27017 --name pdf-mongo mongo:8
EXTRACTOR_URL=http://localhost:8080 uv run uvicorn presentation.main:app --reload
```

La API queda en `http://localhost:8000` (Swagger en `/docs`). Sin proxy, `root_path` es vacío; detrás de nginx se pasa con `uvicorn --root-path /api`.

Para los tests:

```bash
uv run pytest
```

`tests/test_database.py` requiere MongoDB (`docker run -d -p 27017:27017 mongo:8`).

## Configuración

| Variable | Descripción | Default |
|---|---|---|
| `DB_URL` | Connection string de MongoDB | `mongodb://localhost:27017` |
| `DB_NAME` | Nombre de la base de datos | `pdf_extractext` |
| `EXTRACTOR_URL` | URL base del microservicio de extracción | `http://localhost:8080` |
| `EXTRACTOR_TIMEOUT_SECONDS` | Timeout de cada llamada al extractor | `30` |

## Endpoints

| Método | Path | Descripción |
|---|---|---|
| `GET` | `/health` | Chequeo de salud |
| `POST` | `/extract` | Sube un PDF, lo extrae vía microservicio y lo persiste si es único |
| `GET` | `/documents` | Lista los documentos |
| `GET` | `/documents/{id}` | Obtiene un documento |
| `PATCH` | `/documents/{id}` | Actualiza texto y/o checksum |
| `DELETE` | `/documents/{id}` | Elimina un documento |

A través de la web, todas las rutas se consumen con el prefijo `/api` (por ejemplo `GET /api/health`).

### Errores de `POST /extract`

| Situación | Respuesta |
|---|---|
| Checksum ya existente | `409` |
| El extractor rechaza el archivo (no es PDF, muy grande, tipo inválido) | `400` / `413` / `415` con su `detail` |
| Extractor saturado, caído o con error | `503` (con `Retry-After` si el extractor lo envió) |
| Extractor demasiado lento | `504` |

No hay reintentos automáticos.

## Licencia

MIT — ver [LICENSE](LICENSE).
