# Stage de build: resuelve dependencias con uv. Todo lo que se instala acá
# (el binario de uv, cache de resolución, etc.) no llega a la imagen final.
# Imágenes fijadas por versión y digest: el build es reproducible y no cambia
# solo porque el tag móvil apunte a otra cosa (12-Factor V/X). Para actualizar,
# cambiar tag y digest juntos.
FROM python:3.13.18-slim@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50 AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.10@sha256:a3ea1357342c1a4bf9a0c53a3deb1b55379aefa037338d8113d5771efa01774f /uv /usr/local/bin/uv
# Se copian solo los manifiestos primero para aprovechar la cache de layers
# de Docker: si el código cambia pero no las dependencias, este paso no se rehace.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# Stage final: imagen limpia, sin uv ni herramientas de build, solo runtime.
FROM python:3.13.18-slim@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50
WORKDIR /app
# Se copia el .venv ya resuelto del stage anterior en vez de reinstalar acá.
COPY --from=builder /app/.venv /app/.venv
COPY . .
# uvicorn queda accesible sin necesidad de "uv run" (uv no existe en esta imagen).
ENV PATH="/app/.venv/bin:$PATH"
# Sin --reload: la imagen es apta para producción. El autoreload de desarrollo
# vive en docker-compose.override.yml.
CMD ["uvicorn", "presentation.main:app", "--host", "0.0.0.0", "--port", "8000"]
