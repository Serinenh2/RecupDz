"""
Repositories — abstracted data access layer.

Tools NEVER import Django models directly. They use these repositories.
"""

from apps.ai_assistant.repositories.base_repository import BaseRepository
from apps.ai_assistant.repositories.nomenclature_repository import NomenclatureRepository, DesignationDechetRepository
from apps.ai_assistant.repositories.recuperateur_repository import RecuperateurRepository, AgrementRepository
from apps.ai_assistant.repositories.operateur_repository import OperateurRepository
from apps.ai_assistant.repositories.traceability_repository import TraceabilityRepository
from apps.ai_assistant.repositories.bsd_repository import BSDRepository
from apps.ai_assistant.repositories.declaration_repository import DeclarationRepository
from apps.ai_assistant.repositories.bl_repository import BonLivraisonRepository
from apps.ai_assistant.repositories.bc_repository import BonCommandeRepository
from apps.ai_assistant.repositories.knowledge_repository import KnowledgeBaseRepository
from apps.ai_assistant.repositories.user_repository import UserRepository
from apps.ai_assistant.repositories.inspection_repository import InspectionRepository
from apps.ai_assistant.repositories.archive_repository import ArchiveRepository
from apps.ai_assistant.repositories.glossary_repository import GlossaryRepository
from apps.ai_assistant.repositories.notification_repository import NotificationRepository
from apps.ai_assistant.repositories.dashboard_repository import DashboardRepository
from apps.ai_assistant.repositories.administration_repository import AdministrationRepository
from apps.ai_assistant.repositories.permission_repository import PermissionRepository

__all__ = [
    "BaseRepository",
    "NomenclatureRepository",
    "DesignationDechetRepository",
    "RecuperateurRepository",
    "AgrementRepository",
    "OperateurRepository",
    "TraceabilityRepository",
    "BSDRepository",
    "DeclarationRepository",
    "BonLivraisonRepository",
    "BonCommandeRepository",
    "KnowledgeBaseRepository",
    "UserRepository",
    "InspectionRepository",
    "ArchiveRepository",
    "GlossaryRepository",
    "NotificationRepository",
    "DashboardRepository",
    "AdministrationRepository",
    "PermissionRepository",
]
