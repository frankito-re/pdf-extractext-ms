# AGENTS.md — Reglas del backend `pdf-extractext-ms`

Este archivo es **vinculante**. Cualquier persona o agente que modifique este
repositorio debe cumplir estas reglas **con rigor técnico y sin excepciones**.
Si una tarea no encaja en estas reglas, se discute antes de implementar.

---

## 1. Alcance

Este repositorio contiene **solo la API** (FastAPI + Clean Architecture).
No contiene front end, ni orquestación de contenedores, ni el microservicio de
extracción. El despliegue completo vive en `pdf-extractext-deploy`.

Regla de dependencias:

```
presentation ──► application ◄── data
```

- `presentation` no importa detalles de infraestructura salvo en el wiring.
- `application` no conoce FastAPI, MongoDB ni HTTP concreto.
- `data` implementa los puertos definidos en `application`.
- El microservicio de extracción se consume por un `Protocol`, nunca por
  implementación concreta.

---

## 2. TDD obligatorio, sin excepción

**No se escribe código de producción sin un test que falle primero.**

Ciclo obligatorio por cada unidad de trabajo:

1. **Red**: escribir el test y correr `uv run pytest` para verlo fallar por la
   razón correcta.
2. **Green**: implementación mínima para pasarlo.
3. **Refactor**: limpiar con los tests en verde.
4. **Commit atómico** por ciclo (`test:`, `feat:`, `fix:`, `refactor:`).

Checklist antes de cerrar un paso:

- [ ] El test se escribió antes y se vio fallar.
- [ ] `uv run pytest` pasa completo.
- [ ] No se debilitaron asserts ni se borraron tests para “que pase”.
- [ ] No se agregaron dependencias sin justificarlas en `pyproject.toml`.
- [ ] Si cambió la API, se actualizó `README.md`.
- [ ] El commit es atómico y describe el ciclo.

Prohibido: implementar primero y testear después, tests dependientes de red real,
de orden de ejecución o de estado compartido.

---

## 3. SOLID, KISS, YAGNI y DRY

- **SOLID**
  - *SRP*: cada módulo/función tiene una responsabilidad.
  - *OCP*: extender con nuevas clases/módulos, no con condicionales gigantes.
  - *LSP*: toda implementación de un `Protocol` debe ser sustituible.
  - *ISP*: interfaces chicas; no exponer métodos que nadie usa.
  - *DIP*: los endpoints dependen de `Protocol`s; la implementación concreta se
    inyecta solo en el wiring (`presentation/main.py`).
- **KISS**: la solución más simple que cumpla el requisito.
- **YAGNI**: no se agregan campos, endpoints, abstracciones ni dependencias que
  la consigna no pida.
- **DRY**: una sola fuente para reglas repetidas (mapeo de respuestas, errores,
  validaciones); sin duplicar lógica entre capas.

---

## 4. Doce factores (12-Factor App)

| Factor | Regla concreta |
| --- | --- |
| I. Código base | Un repo, un deployable. Sin copiar código de otros servicios. |
| II. Dependencias | Declaradas en `pyproject.toml` + `uv.lock`; nunca implícitas. |
| III. Config | Todo por entorno (`DB_URL`, `DB_NAME`, `EXTRACTOR_URL`, `EXTRACTOR_TIMEOUT_SECONDS`). Prohibido hardcodear hosts o credenciales. |
| IV. Backing services | MongoDB y el extractor son servicios externos accesibles por URL, nunca módulos internos. |
| V. Build/release/run | Imagen Docker reproducible; configuración inyectada en runtime. |
| VI. Procesos | Sin estado en el proceso; el PDF no se escribe a disco. |
| VII. Port binding | Uvicorn expone el puerto 8000; el mapeo lo define el deploy. |
| VIII. Concurrencia | Sin estado compartido mutable entre requests. |
| IX. Desechabilidad | Proceso efímero; arranque y apagado sin pasos manuales. |
| X. Dev/prod parity | Mismas dependencias y mismo código en local y contenedor. |
| XI. Logs | A stdout/stderr, sin archivos de log propios. |
| XII. Admin | Tareas operativas por comandos (`uv run pytest`, `uvicorn`, `docker build`). |

Regla adicional: el backend **no conoce el front**. Si está detrás de un proxy,
el prefijo se pasa al arrancar (`uvicorn --root-path /api`); no se codifica.

---

## 5. Convenciones

- Python 3.13, type hints en firmas públicas, `async/await`.
- Nombres de código en inglés; documentación y mensajes de API en inglés.
- Errores de dominio como excepciones propias, mapeados a HTTP en `presentation`.
- Sin `print`; sin secretos en el repo.
- Formato consistente con el código existente.

## 6. Definition of Done

1. Tests escritos antes y en verde (`uv run pytest`).
2. Reglas de las secciones 3 y 4 respetadas.
3. `README.md` correcto si cambió el uso o la config.
4. Sin código muerto, TODOs ni dependencias sin uso.
5. Commit atómico y CI en verde.
