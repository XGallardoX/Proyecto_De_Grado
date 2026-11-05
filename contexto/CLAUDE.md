# Instrucciones para Claude Code en este repo

## Git: identidad de los commits

**Los commits en este repo JAMÁS deben quedar a nombre de Claude.**
Siempre deben quedar a nombre de la persona que está usando la sesión
(usuario o correo configurado en `git config user.name`/`user.email`
de este repo).

- No agregar el trailer `Co-Authored-By: Claude` (ni ninguna variante
  de atribución a Claude/Anthropic) en ningún commit.
- Si `git config user.name`/`user.email` no están configurados en este
  repo, avisar antes de commitear en vez de usar un identity fallback.
- Esto aplica también a merges, y a cualquier otro repo que se toque
  desde este proyecto (por ejemplo si se agrega un remoto externo).

Este proyecto lo llevan dos personas (ver `ESTADO_PROYECTO.md`), así
que la autoría real de cada commit importa para que quede claro quién
hizo qué.

## Al empezar una sesión

Lee primero `contexto/OFICIAL.md`: es el documento oficial del estado del
proyecto y manda sobre los demás. `contexto/PLAN_SIGUIENTE.md` guarda las
decisiones tomadas y el detalle de cada paso: esas decisiones ya están
tomadas, no pidas que se revisen con el otro autor. Cuando cambie el estado
del proyecto, actualiza `OFICIAL.md`.
