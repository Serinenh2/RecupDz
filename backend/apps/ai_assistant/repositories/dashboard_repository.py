"""
Dashboard Repository — aggregates KPIs and metrics across all modules.

No Django Dashboard model exists. This repository computes live KPIs
from the existing data models.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DashboardRepository:
    """
    Computes live KPIs across all business modules.
    """

    def get_overview(self) -> Dict[str, Any]:
        """Global system overview KPIs."""
        kpis = {}
        kpis["recuperateurs"] = self._count_recuperateurs()
        kpis["declarations"] = self._count_declarations()
        kpis["bsds"] = self._count_bsds()
        kpis["traceabilities"] = self._count_traceabilities()
        kpis["inspections"] = self._count_inspections()
        kpis["nomenclature_codes"] = self._count_nomenclature()
        kpis["archives"] = self._count_archives()
        kpis["users"] = self._count_users()
        kpis["date"] = date.today().isoformat()
        return kpis

    def get_kpis(self) -> List[Dict[str, Any]]:
        """Detailed KPIs with status indicators."""
        overview = self.get_overview()
        kpis = []

        # Recuperateurs
        r = overview["recuperateurs"]
        kpis.append({
            "name": "Récupérateurs",
            "value": r["total"],
            "active": r["actifs"],
            "pending": r["en_attente"],
            "expired": r["expires"],
            "status": "warning" if r["en_attente"] > 0 else "ok",
            "description": f"{r['actifs']} actifs, {r['en_attente']} en attente",
        })

        # Declarations
        d = overview["declarations"]
        kpis.append({
            "name": "Déclarations DSD",
            "value": d["total"],
            "brouillons": d["brouillons"],
            "soumises": d["soumises"],
            "validees": d["validees"],
            "status": "warning" if d["soumises"] > 0 else "ok",
            "description": f"{d['brouillons']} brouillons, {d['soumises']} en attente",
        })

        # BSD
        b = overview["bsds"]
        kpis.append({
            "name": "BSD",
            "value": b["total"],
            "emis": b["emis"],
            "en_transit": b["en_transit"],
            "receptionnes": b["receptionnes"],
            "status": "warning" if b["emis"] > 0 else "ok",
            "description": f"{b['emis']} émis, {b['en_transit']} en transit",
        })

        # Traceability
        t = overview["traceabilities"]
        kpis.append({
            "name": "Traçabilité",
            "value": t["total"],
            "en_cours": t["en_cours"],
            "terminees": t["terminees"],
            "status": "ok" if t["en_cours"] == 0 else "info",
            "description": f"{t['en_cours']} en cours, {t['terminees']} terminées",
        })

        # Inspections
        i = overview["inspections"]
        kpis.append({
            "name": "Inspections",
            "value": i["total"],
            "conformes": i["conformes"],
            "non_conformes": i["non_conformes"],
            "en_cours": i["en_cours"],
            "status": "error" if i["non_conformes"] > 0 else "ok",
            "description": f"{i['conformes']} conformes, {i['non_conformes']} non conformes",
        })

        return kpis

    def get_by_period(self, days: int = 30) -> Dict[str, Any]:
        """Activity summary for the last N days."""
        since = date.today() - timedelta(days=days)
        result = {"period_days": days, "since": since.isoformat()}

        try:
            from apps.declarations.models import Declaration
            result["declarations"] = Declaration.objects.filter(
                created_at__date__gte=since
            ).count()
        except Exception:
            result["declarations"] = 0

        try:
            from apps.bsd.models import BordereauSuiviDechet
            result["bsds"] = BordereauSuiviDechet.objects.filter(
                created_at__date__gte=since
            ).count()
        except Exception:
            result["bsds"] = 0

        try:
            from apps.traceability.models import Traceability
            result["traceabilities"] = Traceability.objects.filter(
                created_at__date__gte=since
            ).count()
        except Exception:
            result["traceabilities"] = 0

        try:
            from apps.inspections.models import Inspection
            result["inspections"] = Inspection.objects.filter(
                date_inspection__gte=since
            ).count()
        except Exception:
            result["inspections"] = 0

        return result

    def get_by_wilaya(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Aggregate recuperateur counts by wilaya."""
        try:
            from apps.recuperateurs.models import Recuperateur
            from django.db.models import Count

            data = (
                Recuperateur.objects
                .values("wilaya")
                .annotate(total=Count("id"))
                .order_by("-total")[:limit]
            )
            return [
                {"wilaya": row["wilaya"] or "N/A", "count": row["total"]}
                for row in data
            ]
        except Exception as exc:
            logger.warning("Wilaya aggregation failed: %s", exc)
            return []

    def get_activity_feed(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Recent activity across all modules."""
        activities = []

        try:
            from apps.traceability.models import Traceability
            recent = Traceability.objects.order_by("-created_at")[:limit]
            for t in recent:
                activities.append({
                    "type": "traceability",
                    "title": f"Opération {t.numero}",
                    "description": f"{t.designation_dechet} — {t.quantite} {t.unite}",
                    "date": t.created_at.isoformat() if t.created_at else "",
                    "status": t.statut,
                })
        except Exception:
            pass

        try:
            from apps.inspections.models import Inspection
            recent = Inspection.objects.order_by("-created_at")[:limit]
            for insp in recent:
                activities.append({
                    "type": "inspection",
                    "title": f"Inspection {insp.get_type_inspection_display()}",
                    "description": f"{insp.recuperateur} — {insp.get_resultat_display() if insp.resultat else 'En attente'}",
                    "date": insp.created_at.isoformat() if insp.created_at else "",
                    "status": insp.resultat or "EN_COURS",
                })
        except Exception:
            pass

        activities.sort(key=lambda a: a.get("date", ""), reverse=True)
        return activities[:limit]

    # ── Private helpers ───────────────────────────────────────────────

    def _count_recuperateurs(self) -> Dict[str, int]:
        try:
            from apps.recuperateurs.models import Recuperateur
            today = date.today()
            return {
                "total": Recuperateur.objects.count(),
                "actifs": Recuperateur.objects.filter(statut="ACTIF").count(),
                "en_attente": Recuperateur.objects.filter(statut="EN_ATTENTE").count(),
                "suspends": Recuperateur.objects.filter(statut="SUSPENDU").count(),
                "expires": Recuperateur.objects.filter(statut="EXPIRE").count(),
            }
        except Exception:
            return {"total": 0, "actifs": 0, "en_attente": 0, "suspends": 0, "expires": 0}

    def _count_declarations(self) -> Dict[str, int]:
        try:
            from apps.declarations.models import Declaration
            return {
                "total": Declaration.objects.count(),
                "brouillons": Declaration.objects.filter(statut="BROUILLON").count(),
                "soumises": Declaration.objects.filter(statut="SOUMISE").count(),
                "validees": Declaration.objects.filter(statut="VALIDEE").count(),
                "archivees": Declaration.objects.filter(statut="ARCHIVEE").count(),
            }
        except Exception:
            return {"total": 0, "brouillons": 0, "soumises": 0, "validees": 0, "archivees": 0}

    def _count_bsds(self) -> Dict[str, int]:
        try:
            from apps.bsd.models import BordereauSuiviDechet
            return {
                "total": BordereauSuiviDechet.objects.count(),
                "emis": BordereauSuiviDechet.objects.filter(statut="EMIS").count(),
                "en_transit": BordereauSuiviDechet.objects.filter(statut="EN_TRANSIT").count(),
                "receptionnes": BordereauSuiviDechet.objects.filter(statut="RECEPTIONNE").count(),
                "signes": BordereauSuiviDechet.objects.filter(statut="SIGNE").count(),
                "archives": BordereauSuiviDechet.objects.filter(statut="ARCHIVE").count(),
            }
        except Exception:
            return {"total": 0, "emis": 0, "en_transit": 0, "receptionnes": 0, "signes": 0, "archives": 0}

    def _count_traceabilities(self) -> Dict[str, int]:
        try:
            from apps.traceability.models import Traceability
            return {
                "total": Traceability.objects.count(),
                "en_cours": Traceability.objects.filter(
                    statut__in=["EN_COURS", "ENLEVEMENT", "TRANSPORT"]
                ).count(),
                "terminees": Traceability.objects.filter(statut="TERMINEE").count(),
                "annulees": Traceability.objects.filter(statut="ANNULEE").count(),
            }
        except Exception:
            return {"total": 0, "en_cours": 0, "terminees": 0, "annulees": 0}

    def _count_inspections(self) -> Dict[str, int]:
        try:
            from apps.inspections.models import Inspection
            return {
                "total": Inspection.objects.count(),
                "conformes": Inspection.objects.filter(resultat="CONFORME").count(),
                "non_conformes": Inspection.objects.filter(resultat="NON_CONFORME").count(),
                "en_cours": Inspection.objects.filter(resultat="EN_COURS").count(),
            }
        except Exception:
            return {"total": 0, "conformes": 0, "non_conformes": 0, "en_cours": 0}

    def _count_nomenclature(self) -> int:
        try:
            from apps.nomenclature.models import Nomenclature
            return Nomenclature.objects.count()
        except Exception:
            return 0

    def _count_archives(self) -> int:
        try:
            from apps.archive.models import Document
            return Document.objects.count()
        except Exception:
            return 0

    def _count_users(self) -> Dict[str, int]:
        try:
            from apps.accounts.models import User
            return {
                "total": User.objects.count(),
                "active": User.objects.filter(is_active=True).count(),
            }
        except Exception:
            return {"total": 0, "active": 0}
