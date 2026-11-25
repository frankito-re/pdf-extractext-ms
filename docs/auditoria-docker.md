# Auditoría Docker: seguridad y principios

Fecha: 2026-11-25 · Rama: `audit/docker-seguridad-y-principios` · Base: `main` (`ba5f012`)

## Alcance

Archivos revisados: `Dockerfile`, `.dockerignore`, `.github/workflows/tests.yml`
(CI que usa Docker para MongoDB), y su coherencia con `AGENTS.md`, `README.md`,
`pyproject.toml`, `uv.lock` y el código de `application/`, `data/`, `presentation/`.

No existen `docker-compose*.yml` en este repo: el merge del fork los eliminó y la
orquestación vive en `pdf-extractext-deploy` (regla de alcance de `AGENTS.md` §1).
**Ese repo no se auditó.**

Método: lectura de archivos, construcción real de la imagen (`docker build`) e
inspección de su contenido (usuario, archivos, capas, healthcheck), búsqueda de
secretos y hosts hardcodeados en código e historial git.

**No se hizo** un escaneo de vulnerabilidades (CVE) de la imagen: no hay
`trivy`/`grype`/`hadolint` instalados. Ver recomendación R9.

## Resumen

| Área | Resultado |
| --- | --- |
| Seguridad de la imagen | 3 hallazgos relevantes (root, sin healthcheck, imágenes sin fijar) |
| 12-Factor | Cumple en su mayoría; 1 punto parcial (V) y 1 débil (X) |
| SOLID / KISS / YAGNI / DRY | Cumple en lo que toca a Docker; 1 inconsistencia documental |
| Documentación | 2 referencias rotas a archivos que ya no existen |

## Seguridad

| # | Severidad | Hallazgo | Evidencia |
| --- | --- | --- | --- |
| S1 | **Alta** | El contenedor corre como **root**. No hay `USER`. Si la app se compromete, el atacante es root dentro del contenedor y puede escribir en `/app`. | `docker inspect` → `User=""`; `id` → `uid=0(root)`; `touch /app/x` funciona. |
| S2 | Media | Imágenes base sin fijar: `python:3.13-slim` (tag móvil) y `ghcr.io/astral-sh/uv:latest`. Un cambio upstream altera el build sin cambio en el repo. `uv:latest` en el stage de build es además un riesgo de cadena de suministro. | `Dockerfile:3,5,12` |
| S3 | Media | Sin `HEALTHCHECK`. Un proceso colgado se ve como "vivo" para Docker. El endpoint `/health` ya existe y no se aprovecha. | `Healthcheck=null`; `presentation/main.py:76` |
| S4 | Baja | La imagen final incluye archivos que no son runtime: `.github/`, `docs/`, `AGENTS.md`, `LICENSE`, `Dockerfile`, `.dockerignore`, `uv.lock`, `pyproject.toml`. Aumenta superficie y filtra detalle interno. Causa: `COPY . .` con un `.dockerignore` corto. | `ls /app` dentro de la imagen |
| S5 | Baja | `.dockerignore` solo excluye `.env`, no `.env.*` ni `*.pem`/`*.key`. Hoy no hay secretos en el repo, pero un `.env.local` futuro entraría a la imagen. | `.dockerignore` |
| S6 | Baja | `COPY . .` copia código como root con permisos por defecto; no hay `--chown` ni filesystem de solo lectura (depende del deploy). | `Dockerfile:16` |
| S7 | Baja | CI: acciones fijadas por tag (`actions/checkout@v4`, `astral-sh/setup-uv@v4`) y no por SHA; `mongo:8` sin patch. CI no construye la imagen, así que un `Dockerfile` roto no se detecta. | `tests.yml:15,30,33` |

Verificado sin hallazgos:

- No hay secretos, contraseñas ni tokens en el código ni en el historial git
  (búsqueda de `mongodb+srv`, `.env`, `.pem`, `.key`, `credentials`).
- `.env` está en `.gitignore` y `.dockerignore`; `.git`, `.venv` y `tests/` no
  llegan a la imagen.
- Multi-stage correcto: `uv` y herramientas de build no están en la imagen final.
- `uv sync --frozen --no-dev`: build reproducible desde `uv.lock`, sin
  dependencias de desarrollo.
- Los únicos `localhost` en el código son defaults de `data/config.py`,
  sobrescribibles por entorno.

## 12-Factor App

| Factor | Estado | Comentario |
| --- | --- | --- |
| I. Código base | Cumple | Un repo, un deployable. |
| II. Dependencias | Cumple | `pyproject.toml` + `uv.lock`, `--frozen`. Los rangos `>=` sin tope son aceptables porque el lock fija versiones. |
| III. Config | Cumple | Todo por entorno (`DB_URL`, `DB_NAME`, `EXTRACTOR_URL`, `EXTRACTOR_TIMEOUT_SECONDS`). Defaults a `localhost` solo para desarrollo. |
| IV. Backing services | Cumple | Mongo y extractor por URL. |
| V. Build/release/run | **Parcial** | Build y run separados, pero las imágenes base sin fijar (S2) hacen que el build no sea reproducible. |
| VI. Procesos | Cumple | Sin estado; el PDF no se escribe a disco. |
| VII. Port binding | Cumple | Uvicorn en `0.0.0.0:8000`; no hay `EXPOSE` (opcional, solo documenta). |
| VIII. Concurrencia | Cumple | Sin estado mutable compartido. |
| IX. Desechabilidad | Cumple | Arranque/apagado sin pasos manuales. Sin healthcheck (S3) el orquestador no distingue "arrancando" de "colgado". |
| X. Dev/prod parity | **Débil** | Mismo código, pero dev corre con `uv run uvicorn --reload` en el host y prod en contenedor; además `--reload` ya no está en la imagen y su override (`docker-compose.override.yml`) fue eliminado. |
| XI. Logs | Cumple | Sin `print`, sin archivos de log; uvicorn escribe a stdout. |
| XII. Admin | Cumple | Tareas por comando (`uv run pytest`, `uvicorn`, `docker build`). |

Nota sobre `--root-path`: `AGENTS.md` dice que el prefijo se pasa al arrancar. El
`CMD` no lo incluye, lo cual es coherente (el deploy lo inyecta), pero el
`Dockerfile` no lo documenta.

## SOLID, KISS, YAGNI, DRY

| Principio | Estado | Comentario |
| --- | --- | --- |
| SRP | Cumple | `Dockerfile` solo construye la imagen; la orquestación salió a otro repo. |
| OCP / LSP / ISP | N/A | No aplican a archivos Docker. En código: `PDFExtractor`, `ChecksumRepository`, `DocumentRepository` son `Protocol` chicos. |
| DIP | Cumple en código, **inconsistente en docs** | El wiring está en `presentation/container.py`, pero `AGENTS.md` §3 sigue diciendo "`presentation/main.py`". |
| KISS | Cumple | Dos stages, nueve líneas efectivas, sin scripts de entrypoint. |
| YAGNI | Cumple | Sin `EXPOSE`/`HEALTHCHECK`/usuarios innecesarios (aunque S1 y S3 son carencias reales, no abstracciones sobrantes). |
| DRY | Cumple | Una sola fuente de config (`DatabaseSettings`, `ExtractorSettings`); el `Dockerfile` no repite lógica. Los defaults de config se repiten en `README.md` y `tests.yml`, aceptable al ser documentación y CI. |

## Referencias rotas

| # | Dónde | Problema |
| --- | --- | --- |
| D1 | `Dockerfile:19-20` | Dice que el autoreload vive en `docker-compose.override.yml`, archivo que ya no existe. |
| D2 | `docs/superpowers/specs/2026-11-19-extractor-client-design.md:45` | Describe un `docker-compose.yml` que ya no está en este repo (puede ser histórico a propósito). |
| D3 | `AGENTS.md` §3 (DIP) | Apunta a `presentation/main.py` como wiring; ahora es `presentation/container.py`. |

## Recomendaciones (ordenadas por prioridad)

1. **R1 (S1)** Crear usuario sin privilegios y `USER` en la imagen final; `COPY --chown`.
2. **R2 (S2)** Fijar `python:3.13-slim` por versión de patch o digest, y `uv` por versión (no `latest`).
3. **R3 (S3)** Agregar `HEALTHCHECK` contra `/health` (con `python -c urllib…`, ya que la imagen slim no trae `curl`).
4. **R4 (S4, S5)** Ampliar `.dockerignore`: `.github/`, `docs/`, `AGENTS.md`, `LICENSE`, `Dockerfile`, `.dockerignore`, `.env.*`, `*.pem`, `*.key`. Alternativa más robusta: copiar solo `application/ data/ presentation/` en vez de `COPY . .`.
5. **R5 (D1)** Corregir el comentario del `Dockerfile` (ya no hay override en este repo).
6. **R6 (D3)** Actualizar `AGENTS.md` §3: wiring en `presentation/container.py`.
7. **R7 (S7)** CI: agregar un job que haga `docker build` para detectar un `Dockerfile` roto; fijar acciones por SHA.
8. **R8 (X)** Documentar en el `README.md` cómo se desarrolla con contenedor, ahora que el override no está.
9. **R9** Ejecutar un escaneo de CVE (`trivy image`/`grype`) sobre la imagen y de dependencias (`uv.lock`); no se hizo en esta auditoría.

Ningún cambio de esta lista se aplicó: esta rama solo contiene el informe.
