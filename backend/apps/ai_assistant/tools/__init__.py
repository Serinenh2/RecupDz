"""
Tool Framework — concrete tool implementation layer.

Every domain tool inherits from BaseTool and returns {success, message, data}.
Tools NEVER import Django models directly — they use the Repository Layer.
"""

from apps.ai_assistant.tools.base_tool import BaseTool
from apps.ai_assistant.tools.tool_context import ToolContext
from apps.ai_assistant.tools.tool_executor import (
    AuditMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    RetryPolicy,
    ToolExecutor,
    ToolMiddleware,
)
from apps.ai_assistant.tools.tool_factory import ToolConfig, ToolFactory
from apps.ai_assistant.tools.tool_registry import ToolRegistry
from apps.ai_assistant.tools.tool_result import ToolResultResponse
from apps.ai_assistant.tools.tool_validator import (
    FieldSchema,
    ParameterSchema,
    SchemaBuilder,
    ToolValidator,
    ValidationError,
)

# -- Concrete domain tools --
from apps.ai_assistant.tools.declaration_tool import DeclarationTool
from apps.ai_assistant.tools.waste_tool import WasteTool
from apps.ai_assistant.tools.partner_tool import PartnerTool
from apps.ai_assistant.tools.producer_tool import ProducerTool
from apps.ai_assistant.tools.transporter_tool import TransporterTool
from apps.ai_assistant.tools.company_tool import CompanyTool
from apps.ai_assistant.tools.statistics_tool import StatisticsTool
from apps.ai_assistant.tools.report_tool import ReportTool
from apps.ai_assistant.tools.regulation_tool import RegulationTool
from apps.ai_assistant.tools.authentication_tool import AuthenticationTool
from apps.ai_assistant.tools.bsd_tool import BSDTool
from apps.ai_assistant.tools.bc_tool import BCTool
from apps.ai_assistant.tools.bl_tool import BLTool
from apps.ai_assistant.tools.inspection_tool import InspectionTool
from apps.ai_assistant.tools.archive_tool import ArchiveTool
from apps.ai_assistant.tools.traceability_tool import TraceabilityTool
from apps.ai_assistant.tools.glossary_tool import GlossaryTool
from apps.ai_assistant.tools.nomenclature_tool import NomenclatureTool
from apps.ai_assistant.tools.notification_tool import NotificationTool
from apps.ai_assistant.tools.dashboard_tool import DashboardTool
from apps.ai_assistant.tools.administration_tool import AdministrationTool
from apps.ai_assistant.tools.permissions_tool import PermissionsTool

__all__ = [
    # Framework
    "BaseTool",
    "ToolContext",
    "ToolResultResponse",
    "ToolRegistry",
    "ToolFactory",
    "ToolConfig",
    "ToolExecutor",
    "ToolMiddleware",
    "LoggingMiddleware",
    "AuditMiddleware",
    "RateLimitMiddleware",
    "RetryPolicy",
    "ToolValidator",
    "ParameterSchema",
    "FieldSchema",
    "SchemaBuilder",
    "ValidationError",
    # Domain tools
    "DeclarationTool",
    "WasteTool",
    "PartnerTool",
    "ProducerTool",
    "TransporterTool",
    "CompanyTool",
    "StatisticsTool",
    "ReportTool",
    "RegulationTool",
    "AuthenticationTool",
    "BSDTool",
    "BCTool",
    "BLTool",
    "InspectionTool",
    "ArchiveTool",
    "TraceabilityTool",
    "GlossaryTool",
    "NomenclatureTool",
    "NotificationTool",
    "DashboardTool",
    "AdministrationTool",
    "PermissionsTool",
]
