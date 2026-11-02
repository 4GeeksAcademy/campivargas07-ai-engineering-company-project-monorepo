# RFP department data requirements

Fuente de verdad de departamentos: `data/process/rfp.py::DEPARTMENTS` y `DEPARTMENT_LABELS`.

Identificadores oficiales:
- `marketing`
- `operaciones`
- `procurement`
- `training`

`config/rfp_departments.json` no es fuente runtime. Si se conserva, debe generarse/validarse desde Python.
No todos los departamentos se activan siempre: `determine_departments`/`decompose_departments` seleccionan según contenido.
