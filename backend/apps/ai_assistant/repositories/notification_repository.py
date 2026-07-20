"""
Notification Repository — virtual notifications from existing data.

No Django Notification model exists. This repository generates notifications
programmatically from inspections, declarations, BSD, agréments, and traceability.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NotificationRepository:
    """
    Generates notifications from live data across all business modules.
    Each notification is a plain dict — no database table.
    """

    PRIORITY_HIGH = "high"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_LOW = "low"

    TYPE_INSPECTION = "inspection"
    TYPE_DECLARATION = "declaration"
    TYPE_AGREMENT = "agrement"
    TYPE_BSD = "bsd"
    TYPE_TRACEABILITY = "traceability"
    TYPE_SYSTEM = "system"

    def get_notifications(
        self,
        type_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Aggregate notifications from all sources."""
        notifications = []
        notifications.extend(self._inspection_alerts())
        notifications.extend(self._declaration_alerts())
        notifications.extend(self._agrement_alerts())
        notifications.extend(self._bsd_alerts())
        notifications.extend(self._traceability_alerts())

        if type_filter:
            notifications = [n for n in notifications if n["type"] == type_filter]
        if priority_filter:
            notifications = [n for n in notifications if n["priority"] == priority_filter]

        notifications.sort(key=lambda n: (
            {"high": 0, "medium": 1, "low": 2}.get(n["priority"], 3),
            n.get("date", ""),
        ), reverse=False)

        return notifications[:limit]

    def get_unread_count(self) -> int:
        return len(self.get_notifications())

    def get_by_type(self, notif_type: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self.get_notifications(type_filter=notif_type, limit=limit)

    def get_by_priority(self, priority: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self.get_notifications(priority_filter=priority, limit=limit)

    def get_summary(self) -> Dict[str, Any]:
        all_notifs = self.get_notifications(limit=1000)
        by_type = {}
        by_priority = {"high": 0, "medium": 0, "low": 0}
        for n in all_notifs:
            by_type[n["type"]] = by_type.get(n["type"], 0) + 1
            by_priority[n["priority"]] = by_priority.get(n["priority"], 0) + 1
        return {
            "total": len(all_notifs),
            "by_type": by_type,
            "by_priority": by_priority,
        }

    # ── Private generators ────────────────────────────────────────────

    def _inspection_alerts(self) -> List[Dict[str, Any]]:
        alerts = []
        try:
            from apps.inspections.models import Inspection

            non_conformes = Inspection.objects.filter(resultat="NON_CONFORME")
            for insp in non_conformes[:10]:
                alerts.append({
                    "id": f"insp_nc_{insp.pk}",
                    "type": self.TYPE_INSPECTION,
                    "priority": self.PRIORITY_HIGH,
                    "title": f"Inspection non conforme — {insp.recuperateur}",
                    "message": (
                        f"Contrôle {insp.get_type_inspection_display()} du {insp.date_inspection} "
                        f"s'est terminé par non-conformité."
                    ),
                    "date": insp.date_inspection.isoformat() if insp.date_inspection else "",
                    "source_id": insp.pk,
                    "read": False,
                })

            en_cours = Inspection.objects.filter(resultat="EN_COURS")
            for insp in en_cours[:5]:
                alerts.append({
                    "id": f"insp_ec_{insp.pk}",
                    "type": self.TYPE_INSPECTION,
                    "priority": self.PRIORITY_MEDIUM,
                    "title": f"Inspection en cours — {insp.recuperateur}",
                    "message": (
                        f"Contrôle {insp.get_type_inspection_display()} du {insp.date_inspection} "
                        f"en attente de résultat."
                    ),
                    "date": insp.date_inspection.isoformat() if insp.date_inspection else "",
                    "source_id": insp.pk,
                    "read": False,
                })

            today = date.today()
            upcoming = Inspection.objects.filter(
                delai_regularisation__lte=today + timedelta(days=30),
                delai_regularisation__gte=today,
                resultat="NON_CONFORME",
            )
            for insp in upcoming[:5]:
                days_left = (insp.delai_regularisation - today).days
                alerts.append({
                    "id": f"insp_dl_{insp.pk}",
                    "type": self.TYPE_INSPECTION,
                    "priority": self.PRIORITY_HIGH if days_left <= 7 else self.PRIORITY_MEDIUM,
                    "title": f"Régularisation due dans {days_left}j — {insp.recuperateur}",
                    "message": (
                        f"Le délai de régularisation de l'inspection du {insp.date_inspection} "
                        f"expire le {insp.delai_regularisation}."
                    ),
                    "date": insp.delai_regularisation.isoformat(),
                    "source_id": insp.pk,
                    "read": False,
                })
        except Exception as exc:
            logger.warning("Inspection alerts failed: %s", exc)
        return alerts

    def _declaration_alerts(self) -> List[Dict[str, Any]]:
        alerts = []
        try:
            from apps.declarations.models import Declaration

            brouillons = Declaration.objects.filter(statut="BROUILLON")
            count = brouillons.count()
            if count > 0:
                alerts.append({
                    "id": "decl_brouillons",
                    "type": self.TYPE_DECLARATION,
                    "priority": self.PRIORITY_LOW,
                    "title": f"{count} déclaration(s) en brouillon",
                    "message": "Des déclarations DSD n'ont pas encore été soumises.",
                    "date": date.today().isoformat(),
                    "source_id": None,
                    "read": False,
                })

            soumises = Declaration.objects.filter(statut="SOUMISE")
            count = soumises.count()
            if count > 0:
                alerts.append({
                    "id": "decl_soumises",
                    "type": self.TYPE_DECLARATION,
                    "priority": self.PRIORITY_MEDIUM,
                    "title": f"{count} déclaration(s) en attente de validation",
                    "message": "Des déclarations DSD soumises sont en attente de validation.",
                    "date": date.today().isoformat(),
                    "source_id": None,
                    "read": False,
                })
        except Exception as exc:
            logger.warning("Declaration alerts failed: %s", exc)
        return alerts

    def _agrement_alerts(self) -> List[Dict[str, Any]]:
        alerts = []
        try:
            from apps.recuperateurs.models import AgrementRecuperateur

            today = date.today()
            expiring = AgrementRecuperateur.objects.filter(
                statut="ACTIF",
                date_fin__lte=today + timedelta(days=60),
                date_fin__gte=today,
            )
            for agr in expiring[:10]:
                days_left = (agr.date_fin - today).days
                alerts.append({
                    "id": f"agr_exp_{agr.pk}",
                    "type": self.TYPE_AGREMENT,
                    "priority": self.PRIORITY_HIGH if days_left <= 30 else self.PRIORITY_MEDIUM,
                    "title": f"Agrément expire dans {days_left}j — {agr.recuperateur}",
                    "message": (
                        f"Agrément {agr.numero_agrement or 'sans N°'} du récupérateur "
                        f"{agr.recuperateur} expire le {agr.date_fin}."
                    ),
                    "date": agr.date_fin.isoformat(),
                    "source_id": agr.pk,
                    "read": False,
                })

            expired = AgrementRecuperateur.objects.filter(statut="EXPIRE")
            count = expired.count()
            if count > 0:
                alerts.append({
                    "id": "agr_expired_count",
                    "type": self.TYPE_AGREMENT,
                    "priority": self.PRIORITY_HIGH,
                    "title": f"{count} agrément(s) expiré(s)",
                    "message": "Des agréments de récupérateurs ont expiré et nécessitent un renouvellement.",
                    "date": today.isoformat(),
                    "source_id": None,
                    "read": False,
                })
        except Exception as exc:
            logger.warning("Agrement alerts failed: %s", exc)
        return alerts

    def _bsd_alerts(self) -> List[Dict[str, Any]]:
        alerts = []
        try:
            from apps.bsd.models import BordereauSuiviDechet

            non_signes = BordereauSuiviDechet.objects.filter(
                statut="EMIS",
                signature_generateur=False,
            )
            count = non_signes.count()
            if count > 0:
                alerts.append({
                    "id": "bsd_unsigned",
                    "type": self.TYPE_BSD,
                    "priority": self.PRIORITY_MEDIUM,
                    "title": f"{count} BSD(s) en attente de signature",
                    "message": "Des bordereaux de suivi des déchets ont été émis mais pas encore signés.",
                    "date": date.today().isoformat(),
                    "source_id": None,
                    "read": False,
                })
        except Exception as exc:
            logger.warning("BSD alerts failed: %s", exc)
        return alerts

    def _traceability_alerts(self) -> List[Dict[str, Any]]:
        alerts = []
        try:
            from apps.traceability.models import Traceability

            en_cours = Traceability.objects.filter(statut__in=["EN_COURS", "ENLEVEMENT", "TRANSPORT"])
            count = en_cours.count()
            if count > 0:
                alerts.append({
                    "id": "trace_en_cours",
                    "type": self.TYPE_TRACEABILITY,
                    "priority": self.PRIORITY_LOW,
                    "title": f"{count} opération(s) de traçabilité en cours",
                    "message": "Des opérations de traçabilité sont actuellement en cours de traitement.",
                    "date": date.today().isoformat(),
                    "source_id": None,
                    "read": False,
                })
        except Exception as exc:
            logger.warning("Traceability alerts failed: %s", exc)
        return alerts
