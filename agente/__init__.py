"""Agente A Ponte (fase 3): host MCP por dentro, sem LLM.

O agente é um processo separado do servidor MCP. Por dentro ele é um host MCP de
verdade — descobre tools, lê o resource da política e percorre o ciclo MRTR como
cliente — e expõe uma biblioteca interna (`controllers`) que as fases 4 (servidor
A2A) e 5 (a ponte) vão plugar. Nenhum LLM e nenhuma regra de negócio de sala vivem
aqui: conflito, política e alternativas são decisão exclusiva do servidor MCP.
"""

__all__ = ["models", "controllers", "views"]
