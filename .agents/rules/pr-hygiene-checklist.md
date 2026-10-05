# Rule: PR Hygiene Checklist

## Scope
always-active

## Intencion
Evitar ruido en PRs (archivos generados, temporales o fuera de alcance) y mantener cambios enfocados.

## Regla
Antes de abrir o actualizar un PR, ejecutar el checklist de higiene y corregir cualquier hallazgo.

## Checklist verificable
- [ ] El PR no incluye node_modules, .next, dist, build, .pyc, ni carpetas __pycache__.
- [ ] El PR no incluye archivos temporales o auxiliares como pr-body.md, notas locales o outputs de herramientas.
- [ ] Solo hay cambios del alcance funcional del ticket.
- [ ] git status esta limpio despues del commit final.
- [ ] La descripcion del PR documenta vistas protegidas y confirma impacto cero en website publico si aplica.

## Comandos sugeridos
- Revisar cambios staged y unstaged: git status --short
- Revisar archivos del PR: gh pr view <numero> --json files --jq '.files[].path'
- Buscar ruido tipico en PR: gh pr view <numero> --json files --jq '.files[].path' | grep -E '__pycache__|\\.pyc$|node_modules|pr-body\\.md|\\.next|dist|build' || echo 'OK limpio'

## Cuando detenerse y preguntar
- Si aparece una eliminacion o adicion heredada de main que no es parte del alcance.
- Si hay conflicto entre limpieza del PR y reproducibilidad del entorno local.
