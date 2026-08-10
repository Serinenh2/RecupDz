"""
Adapter Layer — bridges the tools framework to the core interfaces.

This module makes the 10 existing domain tools (BaseTool) compatible with
the core Agent interfaces (core.Tool, core.Executor, core.Router, etc.)
without modifying either side.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from apps.ai_assistant.core.interfaces import (
    Context,
    ExecutionPlan,
    Executor,
    FormattedResponse,
    Formatter,
    Intent,
    LLMProvider,
    Message,
    OutputFormat,
    Planner,
    Reasoner,
    Role,
    RouteResult,
    Router,
    TaskStep,
    ToolResult,
)
from apps.ai_assistant.core.planner import LLMPlanner
from apps.ai_assistant.core.reasoning import LLMReasoner
from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_executor import ToolExecutor
from apps.ai_assistant.tools.tool_registry import ToolRegistry
from apps.ai_assistant.tools.tool_result import ToolResultResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OllamaService → LLMProvider adapter
# ---------------------------------------------------------------------------

class OllamaLLMAdapter(LLMProvider):
    """Wraps the existing OllamaService as a core LLMProvider."""

    def __init__(self, ollama) -> None:
        self._ollama = ollama

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None,
    ) -> str:
        return self._ollama.chat(
            message=prompt,
            history=[],
            system_prompt=system_prompt or "",
            temperature=temperature,
            max_tokens=max_tokens,
        ) or ""

    def generate_structured(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        raw = self.generate(
            prompt, system_prompt=system_prompt,
            temperature=temperature, max_tokens=max_tokens,
        )
        return _extract_json(raw)

    def is_available(self) -> bool:
        return self._ollama.is_available()


def _extract_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(l for l in lines if not l.strip().startswith("```"))
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# BaseTool → core.Tool adapter
# ---------------------------------------------------------------------------

class ToolAdapter:
    """Wraps a BaseTool instance to be compatible with core.Tool protocol."""

    def __init__(self, base_tool: BaseTool) -> None:
        self._tool = base_tool

    @property
    def name(self) -> str:
        return self._tool.name

    @property
    def description(self) -> str:
        return self._tool.description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return self._tool.parameters_schema

    def to_core_tool(self) -> _CoreToolProxy:
        """Return a proxy that satisfies the core.Tool ABC."""
        return _CoreToolProxy(self._tool)


class _CoreToolProxy:
    """Satisfies the core.Tool ABC by delegating to BaseTool."""

    def __init__(self, base_tool: BaseTool) -> None:
        self._tool = base_tool

    @property
    def name(self) -> str:
        return self._tool.name

    @property
    def description(self) -> str:
        return self._tool.description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return self._tool.parameters_schema

    def execute(self, parameters: Dict[str, Any], context: Context) -> ToolResult:
        tool_ctx = ToolContext.create(
            user_id=context.user_id or "",
            conversation_id=context.conversation_id or "",
        )
        try:
            response: ToolResultResponse = self._tool.execute(parameters, tool_ctx)
            return ToolResult(
                tool_name=self._tool.name,
                success=response.success,
                data=response.data,
                error=response.message if not response.success else None,
                metadata=response.metadata,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self._tool.name,
                success=False,
                error=str(exc),
            )

    def validate_parameters(self, parameters: Dict[str, Any]) -> List[str]:
        errors = self._tool.validate(parameters)
        return [e.message for e in errors] if errors else []


# ---------------------------------------------------------------------------
# IntentRouter → core.Router adapter
# ---------------------------------------------------------------------------

class IntentRouterAdapter(Router):
    """Wraps the rule-based IntentRouter as a core.Router."""

    def __init__(self, intent_router) -> None:
        self._router = intent_router

    def classify(self, context: Context) -> RouteResult:
        user_message = ""
        for msg in reversed(context.messages):
            if msg.role == Role.USER:
                user_message = msg.content
                break

        decision = self._router.route(user_message)

        intent_map = {
            "greeting": Intent.GREETING,
            "question": Intent.QUESTION,
            "waste_search": Intent.ENTITY_LOOKUP,
            "nomenclature": Intent.ENTITY_LOOKUP,
            "declaration": Intent.ENTITY_LOOKUP,
            "company": Intent.ENTITY_LOOKUP,
            "partner": Intent.ENTITY_LOOKUP,
            "statistics": Intent.ANALYSIS,
            "report": Intent.ANALYSIS,
            "regulation": Intent.ENTITY_LOOKUP,
            "unknown": Intent.UNKNOWN,
        }

        intent = intent_map.get(decision.intent, Intent.UNKNOWN)
        tool_hint = decision.tool or None

        entities = {}
        for entity in decision.entities:
            entities[entity.type] = entity.value

        return RouteResult(
            intent=intent,
            confidence=decision.confidence,
            entities=entities,
            tool_hint=tool_hint,
        )


# ---------------------------------------------------------------------------
# ToolExecutor → core.Executor adapter
# ---------------------------------------------------------------------------

class ToolExecutorAdapter(Executor):
    """Wraps the tools framework ToolExecutor as a core.Executor."""

    def __init__(self, tool_executor: ToolExecutor) -> None:
        self._executor = tool_executor

    def execute(self, plan: ExecutionPlan, context: Context) -> List[ToolResult]:
        results: List[ToolResult] = []
        for step in plan.steps:
            result = self.execute_step(step, context)
            results.append(result)
        return results

    def execute_step(self, step: TaskStep, context: Context) -> ToolResult:
        tool_ctx = ToolContext.create(
            user_id=context.user_id or "",
            conversation_id=context.conversation_id or "",
        )
        try:
            response: ToolResultResponse = self._executor.execute(
                step.tool_name, step.parameters, tool_ctx,
            )
            return ToolResult(
                tool_name=step.tool_name,
                success=response.success,
                data=response.data,
                error=response.message if not response.success else None,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=step.tool_name,
                success=False,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Deterministic Formatter (no LLM required)
# ---------------------------------------------------------------------------

class DeterministicFormatter(Formatter):
    """Formats tool results without requiring an LLM."""

    def format(
        self,
        results: List[ToolResult],
        context: Context,
        reasoning: Optional[ReasoningResult] = None,
        *,
        output_format: OutputFormat = OutputFormat.TEXT,
    ) -> FormattedResponse:
        parts: List[str] = []
        for result in results:
            if result.success and result.data is not None:
                parts.append(self._format_result(result))
            elif result.error:
                parts.append(f"Erreur: {result.error}")

        text = "\n\n".join(parts) if parts else "Aucun résultat disponible."
        return FormattedResponse(
            text=text,
            format=output_format,
            metadata={"result_count": len(results)},
        )

    def _format_result(self, result: ToolResult) -> str:
        data = result.data
        if isinstance(data, str):
            return data
        if not isinstance(data, dict):
            return str(data)[:500]

        tool = result.tool_name

        if tool == "waste_tool":
            return self._format_waste(data)
        if tool == "nomenclature_tool":
            return self._format_nomenclature(data)
        if tool in ("entreprise_tool", "company_tool"):
            return self._format_companies(data)
        if tool == "partner_tool":
            return self._format_partners(data)
        if tool == "reglementation_tool":
            return self._format_regulations(data)
        if tool == "declaration_tool":
            return self._format_declarations(data)
        if tool == "transporteur_tool":
            return self._format_transporters(data)
        if tool == "producteur_tool":
            return self._format_producers(data)
        if tool == "rapport_tool":
            return self._format_reports(data)
        if tool == "statistiques_tool":
            return self._format_statistics(data)

        if tool == "direct_response":
            resp = data.get("response", "")
            if resp:
                return resp
            fb = data.get("fallback_message", "")
            if fb:
                return fb
            return self._stringify(data)

        return self._stringify(data)

    def _format_waste(self, data: Dict[str, Any]) -> str:
        items = data.get("nomenclatures", [])
        count = data.get("count", len(items))
        if not items:
            return "Aucun déchet trouvé."
        lines = [f"J'ai trouvé {count} code(s) nomenclature :\n"]
        for item in items[:10]:
            code = item.get("code", "?")
            desc = item.get("designation_fr", "")
            classe = item.get("classe", "")
            dangerous_flags = []
            if item.get("inflammable"):
                dangerous_flags.append("Inflammable")
            if item.get("toxique"):
                dangerous_flags.append("Toxique")
            if item.get("cancerogene"):
                dangerous_flags.append("Cancérogène")
            if item.get("corrosive"):
                dangerous_flags.append("Corrosif")
            if item.get("explosible"):
                dangerous_flags.append("Explosif")
            if item.get("dangereuse_environnement"):
                dangerous_flags.append("Nocif env.")
            flags_str = f" [{', '.join(dangerous_flags)}]" if dangerous_flags else ""
            bsd = " (BSD requis)" if item.get("bsd_obligatoire") else ""
            lines.append(f"  • {code} — {desc} (classe {classe}){bsd}{flags_str}")
        if count > 10:
            lines.append(f"\n... et {count - 10} autre(s).")
        return "\n".join(lines)

    def _format_nomenclature(self, data: Dict[str, Any]) -> str:
        # Action: list_children
        if "parent_code" in data and "children" in data:
            parent = data["parent_code"]
            designation = data.get("parent_designation", "")
            children = data["children"]
            count = data.get("count", len(children))
            depth = data.get("depth", 1)

            header = f"**{parent}**"
            if designation:
                header += f" — {designation}"
            header += f" (niveau {depth})"

            if not children:
                return f"{header}\n\nAucun sous-code."

            lines = [header, f"\n{count} sous-code(s) :\n"]
            for item in children[:30]:
                c = item.get("code", "?")
                d = item.get("designation_fr", "")[:50]
                cl = item.get("classe", "")
                lines.append(f"  • {c} — {d} [{cl}]")
            if count > 30:
                lines.append(f"\n... et {count - 30} autre(s).")
            grandparent = data.get("grandparent_code")
            if grandparent:
                lines.append(f"\nParent : {grandparent}")
            return "\n".join(lines)

        # Action: search_by_code (single item with metadata)
        if "nomenclature" in data:
            n = data["nomenclature"]
            code = n.get("code", "?")
            desc = n.get("designation_fr", "")
            classe = n.get("classe", "")
            bsd = " (BSD requis)" if n.get("bsd_obligatoire") else ""
            agrement = " (Agrément requis)" if n.get("agrement_requis") else ""

            flags = []
            if n.get("inflammable"):
                flags.append("Inflammable")
            if n.get("toxique"):
                flags.append("Toxique")
            if n.get("cancerogene"):
                flags.append("Cancérogène")
            if n.get("corrosive"):
                flags.append("Corrosif")
            if n.get("explosible"):
                flags.append("Explosif")
            if n.get("dangereuse_environnement"):
                flags.append("Nocif env.")
            flags_str = f" [{', '.join(flags)}]" if flags else ""

            lines = [
                f"**{code}** — {desc} (classe {classe}){bsd}{agrement}{flags_str}",
            ]

            parent_code = data.get("parent_code")
            if parent_code:
                lines.append(f"Parent : {parent_code}")

            children_count = data.get("children_count", 0)
            if children_count:
                lines.append(f"Sous-codes : {children_count}")

            siblings = data.get("siblings", [])
            if siblings:
                lines.append(f"\nCodes similaires dans la meme famille :")
                for s in siblings[:5]:
                    lines.append(f"  • {s.get('code', '?')} — {s.get('designation_fr', '')[:50]}")

            return "\n".join(lines)

        # Action: search / search_similar (list of items)
        items = data.get("nomenclatures", [])
        count = data.get("count", len(items))
        query = data.get("query", "")

        if not items:
            return f"Aucun code nomenclature trouve pour '{query}'." if query else "Aucun resultat."

        lines = [f"{count} code(s) nomenclature :\n"]
        for item in items[:10]:
            c = item.get("code", "?")
            d = item.get("designation_fr", "")[:60]
            cl = item.get("classe", "")
            lines.append(f"  • {c} — {d} (classe {cl})")
        if count > 10:
            lines.append(f"\n... et {count - 10} autre(s).")
        return "\n".join(lines)

    def _format_companies(self, data: Dict[str, Any]) -> str:
        items = data.get("entreprises", data.get("companies", []))
        count = data.get("count", len(items))
        if not items:
            return "Aucune entreprise trouvée."
        lines = [f"J'ai trouvé {count} entreprise(s) :\n"]
        for item in items[:5]:
            name = item.get("nom", item.get("name", "?"))
            wilaya = item.get("wilaya", "")
            commune = item.get("commune", "")
            activite = item.get("activite", item.get("activite_principale", ""))
            lines.append(f"  • {name} — {commune}, {wilaya}")
            if activite:
                lines.append(f"    Activité: {activite}")
        if count > 5:
            lines.append(f"\n... et {count - 5} autre(s).")
        return "\n".join(lines)

    def _format_partners(self, data: Dict[str, Any]) -> str:
        items = data.get("partenaires", [])
        count = data.get("count", len(items))
        if not items:
            return "Aucun partenaire trouvé."
        lines = [f"J'ai trouvé {count} partenaire(s) :\n"]
        for item in items[:5]:
            name = item.get("nom", "?")
            typ = item.get("type_partenaire", "")
            lines.append(f"  • {name} ({typ})")
        return "\n".join(lines)

    def _format_regulations(self, data: Dict[str, Any]) -> str:
        items = data.get("articles", [])
        count = data.get("count", len(items))
        if not items:
            return "Aucune réglementation trouvée."
        lines = [f"J'ai trouvé {count} article(s) réglementaire :\n"]
        for item in items[:5]:
            title = item.get("titre", item.get("title", "?"))
            desc = item.get("description", "")
            lines.append(f"  • {title}")
            if desc:
                lines.append(f"    {desc[:200]}")
        return "\n".join(lines)

    def _format_declarations(self, data: Dict[str, Any]) -> str:
        items = data.get("declarations", [])
        count = data.get("count", len(items))
        if not items:
            return "Aucune déclaration trouvée."
        lines = [f"J'ai trouvé {count} déclaration(s) :\n"]
        for item in items[:5]:
            ref = item.get("reference", item.get("id", "?"))
            date = item.get("date", "")
            lines.append(f"  • Déclaration {ref} — {date}")
        return "\n".join(lines)

    def _format_transporters(self, data: Dict[str, Any]) -> str:
        items = data.get("transporteurs", [])
        count = data.get("count", len(items))
        if not items:
            return "Aucun transporteur trouvé."
        lines = [f"J'ai trouvé {count} transporteur(s) :\n"]
        for item in items[:5]:
            name = item.get("nom", "?")
            lines.append(f"  • {name}")
        return "\n".join(lines)

    def _format_producers(self, data: Dict[str, Any]) -> str:
        items = data.get("producteurs", [])
        count = data.get("count", len(items))
        if not items:
            return "Aucun producteur trouvé."
        lines = [f"J'ai trouvé {count} producteur(s) :\n"]
        for item in items[:5]:
            name = item.get("nom", "?")
            lines.append(f"  • {name}")
        return "\n".join(lines)

    def _format_reports(self, data: Dict[str, Any]) -> str:
        items = data.get("rapports", [])
        count = data.get("count", len(items))
        if not items:
            return "Aucun rapport trouvé."
        lines = [f"J'ai trouvé {count} rapport(s) :\n"]
        for item in items[:5]:
            title = item.get("titre", item.get("title", "?"))
            lines.append(f"  • {title}")
        return "\n".join(lines)

    def _format_statistics(self, data: Dict[str, Any]) -> str:
        total = data.get("total_quantity", 0)
        lines = [f"Statistiques : {total} tonne(s) au total."]
        for k, v in data.items():
            if k != "total_quantity" and v is not None:
                lines.append(f"  • {k}: {v}")
        return "\n".join(lines)

    def _stringify(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            lines = []
            for k, v in data.items():
                if isinstance(v, list):
                    lines.append(f"- **{k}**: {len(v)} élément(s)")
                else:
                    lines.append(f"- **{k}**: {str(v)[:200]}")
            return "\n".join(lines)
        if isinstance(data, list):
            return f"{len(data)} élément(s)"
        return str(data)[:500]


# ---------------------------------------------------------------------------
# Convenience: wire all adapters
# ---------------------------------------------------------------------------

def create_adapters(
    ollama_service,
    intent_router,
    tool_executor: ToolExecutor,
) -> Dict[str, Any]:
    """
    Create all adapter instances from existing services.

    Returns a dict with keys:
        llm, router, executor, formatter
    """
    llm = OllamaLLMAdapter(ollama_service)
    router = IntentRouterAdapter(intent_router)
    executor = ToolExecutorAdapter(tool_executor)
    formatter = DeterministicFormatter()

    return {
        "llm": llm,
        "router": router,
        "executor": executor,
        "formatter": formatter,
    }
