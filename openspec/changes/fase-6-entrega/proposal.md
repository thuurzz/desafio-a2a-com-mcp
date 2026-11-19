# Proposal

## Why

O enunciado exige que o `README.md` do starter seja substituído pela documentação da entrega, com quatro
seções obrigatórias, e que os comandos funcionem a partir de um clone limpo. Sem isso, o avaliador não
consegue subir os dois processos seguindo apenas o repositório, e a entrega é considerada incompleta mesmo
com o validador passando.

## What Changes

- `README.md` passa a documentar a entrega: como rodar (clonar, criar ambiente, instalar, exportar
  `REQUEST_STATE_SECRET`, subir cada processo, rodar o validador), onde a ponte acontece (arquivo e função
  em cada lado), as decisões técnicas (selo do `requestState`, onde ficam as Tasks, `allow_input_required`,
  stateless) e a saída real do validador.
- `docs/fase-6.md` registra a verificação em clone limpo, com a saída do validador e o `exit=0`.
- `docs/roadmap.md` fecha as seis fases.

## Não-objetivos

- Nenhuma mudança de código de aplicação nesta fase.
- Nada de autenticação, streaming, persistência em disco, container ou deploy.
- Não alterar `dados/`, `validador/` nem `exemplos/` (o avaliador roda o validador do repositório original).

## Impact

- Habilita o fluxo do avaliador: clone limpo → README → validador → 36/36 com `exit=0`.
- Documenta a limitação conhecida (`server/discover` sem `traceparent`) em vez de contornar o protocolo.
