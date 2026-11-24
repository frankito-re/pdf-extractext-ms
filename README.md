# pdf-extractext-ms

API para extraer texto de archivos PDF y persistirlo en MongoDB con deduplicación por checksum, **delegando la extracción en un microservicio dedicado**.

Es la variante de `pdf-extractext` en la que la lógica de extracción ya no vive en la app: esta API valida, calcula el SHA-256, consulta al microservicio por HTTP (`POST /extract`) y persiste el resultado. Proyecto académico de **Desarrollo de Software 2026** — UTN Facultad Regional San Rafael.

## Cómo funciona

```
cliente ──► app (:8000) ──► Traefik ──► extractor ×5   (microservicio de extracción)
                │
                └──► MongoDB
```

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

## Requisitos

- Python 3.13+ y [uv](https://docs.astral.sh/uv/)
- Docker (con acceso a internet en el primer build: la imagen del extractor se construye desde GitHub)

## Arranque

Alcanza con clonar este repo. El microservicio de extracción **no hace falta clonarlo**: Docker lo construye directo desde [`bar-bii/Microservicios`](https://github.com/bar-bii/Microservicios), fijado a un commit para que el build sea reproducible.

Stack completo (MongoDB + app + Traefik + 5 réplicas del extractor):

```bash
git clone https://github.com/frankito-re/pdf-extractext-ms.git
cd pdf-extractext-ms
docker compose up --build
```

La API queda en `http://localhost:8000` (Swagger en `/docs`). Cada réplica del extractor tiene un límite de 1 CPU y 1 GB de RAM.

### Desarrollo vs. producción

La imagen no usa `--reload`. El autoreload de uvicorn está solo en `docker-compose.override.yml`, que `docker compose` combina automáticamente con `docker-compose.yml` y es lo que usa `docker compose watch` para reflejar los cambios de código.

Para correr sin autoreload (modo producción):

```bash
docker compose -f docker-compose.yml up --build
```

Desarrollo local contra un extractor ya levantado:

```bash
uv sync
docker compose up mongodb -d
EXTRACTOR_URL=http://localhost:8080 uv run uvicorn presentation.main:app --reload
```

## Configuración

| Variable | Descripción | Default |
|---|---|---|
| `DB_URL` | Connection string de MongoDB | `mongodb://localhost:27017` |
| `DB_NAME` | Nombre de la base de datos | `pdf_extractext` |
| `EXTRACTOR_URL` | URL base del microservicio de extracción | `http://localhost:8080` |
| `EXTRACTOR_TIMEOUT_SECONDS` | Timeout de cada llamada al extractor | `30` |
| `EXTRACTOR_CONTEXT` | Solo para `docker compose`: de dónde se construye el extractor (URL git o carpeta local) | `https://github.com/bar-bii/Microservicios.git#<commit>` |

## Endpoints

| Método | Path | Descripción |
|---|---|---|
| `GET` | `/health` | Chequeo de salud |
| `POST` | `/extract` | Sube un PDF, lo extrae vía microservicio y lo persiste si es único |
| `GET` | `/documents` | Lista los documentos |
| `GET` | `/documents/{id}` | Obtiene un documento |
| `PATCH` | `/documents/{id}` | Actualiza texto y/o checksum |
| `DELETE` | `/documents/{id}` | Elimina un documento |

### Errores de `POST /extract`

| Situación | Respuesta |
|---|---|
| Checksum ya existente | `409` |
| El extractor rechaza el archivo (no es PDF, muy grande, tipo inválido) | `400` / `413` / `415` con su `detail` |
| Extractor saturado, caído o con error | `503` (con `Retry-After` si el extractor lo envió) |
| Extractor demasiado lento | `504` |

No hay reintentos automáticos.

## Tests

El proyecto sigue TDD (Red → Green → Refactor).

```bash
uv run pytest
```

`tests/test_database.py` es de integración y requiere MongoDB (`docker compose up mongodb -d`).

## Licencia

MIT — ver [LICENSE](LICENSE).
