from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta
from apps.accounts.permissions import ModulePermission
from .models import AIConversation, AIMessage, AIAlert, KnowledgeBase, AIRecommendation
from .serializers import (
    AIConversationSerializer, AIConversationListSerializer, AIConversationCreateSerializer,
    AIMessageSerializer, AIMessageCreateSerializer,
    AIAlertSerializer, KnowledgeBaseSerializer, KnowledgeBaseCreateSerializer,
    AIRecommendationSerializer, AIStatisticsSerializer
)
from apps.accounts.models import User
from apps.recuperateurs.models import Recuperateur, AgrementRecuperateur
from apps.bsd.models import BordereauSuiviDechet
from apps.traceability.models import Traceability


from .glossaire_data import rechercher_glossaire, formater_glossaire, detecter_langue
from .nomenclature_data import rechercher_par_code, rechercher_par_texte, FAMILLES, CLASSE_LABELS, inferer_bsd_agrement
from .conversation_manager import ConversationManager


def _get_pipeline():
    """Lazy singleton for the enterprise pipeline."""
    from apps.ai_assistant.enterprise.container import Container
    container = Container()
    return container.pipeline


def detecter_anomalies_bsd():
    anomalies = []
    aujourd_hui = timezone.now().date()
    bsds = BordereauSuiviDechet.objects.all()
    for bsd in bsds:
        if bsd.statut == 'BROUILLON' and bsd.date_creation:
            delta = (aujourd_hui - bsd.date_creation).days
            if delta > 7:
                anomalies.append({
                    'type': 'BSD_ANOMALIE',
                    'niveau': 'MOYEN',
                    'description': f'BSD #{bsd.numero} en brouillon depuis plus de 7 jours',
                    'entite_type': 'BSD',
                    'entite_id': bsd.id,
                    'lien': f'/bsd/{bsd.id}'
                })
        if bsd.date_emission and bsd.statut not in ['TERMINE', 'ANNULE', 'ARCHIVE']:
            delta = (aujourd_hui - bsd.date_emission).days
            if delta > 14:
                anomalies.append({
                    'type': 'BSD_ANOMALIE',
                    'niveau': 'ELEVE',
                    'description': f'BSD #{bsd.numero} en retard (émis le {bsd.date_emission})',
                    'entite_type': 'BSD',
                    'entite_id': bsd.id,
                    'lien': f'/bsd/{bsd.id}'
                })
    return anomalies


def detecter_anomalies_agrements():
    anomalies = []
    aujourd_hui = timezone.now().date()
    agrements = AgrementRecuperateur.objects.filter(statut='ACTIF')
    for agr in agrements:
        if agr.date_fin:
            if agr.date_fin < aujourd_hui:
                anomalies.append({
                    'type': 'AGREMENT_EXPIRE',
                    'niveau': 'CRITIQUE',
                    'description': f'Agrément #{agr.numero_agrement} expiré le {agr.date_fin}',
                    'entite_type': 'Agrement',
                    'entite_id': agr.id,
                    'lien': f'/agrements/{agr.id}'
                })
            elif agr.date_fin < aujourd_hui + timedelta(days=30):
                anomalies.append({
                    'type': 'AGREMENT_EXPIRING',
                    'niveau': 'MOYEN',
                    'description': f'Agrément #{agr.numero_agrement} expire bientôt le {agr.date_fin}',
                    'entite_type': 'Agrement',
                    'entite_id': agr.id,
                    'lien': f'/agrements/{agr.id}'
                })
    return anomalies


class AIConversationViewSet(viewsets.ModelViewSet):
    module_label     = 'ai_assistant'
    serializer_class = AIConversationSerializer
    permission_classes = [ModulePermission]

    def get_queryset(self):
        return AIConversation.objects.filter(user=self.request.user).prefetch_related('messages').annotate(
            _messages_count=Count('messages')
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return AIConversationCreateSerializer
        if self.action == 'list':
            return AIConversationListSerializer
        return AIConversationSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def envoyer_message(self, request, pk=None):
        conversation = self.get_object()
        serializer = AIMessageCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        message_user = serializer.validated_data['message']
        contexte_supp = serializer.validated_data.get('contexte_supplementaire', {})

        AIMessage.objects.create(
            conversation=conversation,
            role='USER',
            message=message_user,
            contexte_json=contexte_supp
        )
        conversation.last_message_at = timezone.now()
        conversation.save()

        reponse_ia = self._generer_reponse_intelligente(message_user, conversation, contexte_supp)

        AIMessage.objects.create(
            conversation=conversation,
            role='ASSISTANT',
            message=reponse_ia['message'],
            contexte_json=reponse_ia.get('contexte', {})
        )

        conversation.last_message_at = timezone.now()
        conversation.save()

        return Response({'reponse': reponse_ia['message'], 'contexte': reponse_ia.get('contexte', {})})

    def _generer_reponse_intelligente(self, message, conversation, contexte_supp):
        # ------------------------------------------------------------------
        # Step 1: Try Enterprise Pipeline (mandatory 7-step workflow)
        # ------------------------------------------------------------------
        try:
            pipeline = _get_pipeline()
            result = pipeline.handle(
                message=message,
                user_id=str(conversation.user_id) if hasattr(conversation, 'user_id') else "",
                conversation_id=str(conversation.id) if conversation else "",
                contexte_supp=contexte_supp,
            )
            if result.get("success"):
                response_data = {
                    'message': result['message'],
                    'contexte': result.get('data', {}),
                }
                if result.get('followups'):
                    response_data['followups'] = result['followups']
                return response_data
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Enterprise pipeline failed: %s", exc)

        # ------------------------------------------------------------------
        # Step 2: Try Ollama (Hermes3) via ConversationManager
        # ------------------------------------------------------------------
        manager = ConversationManager()
        ollama_response = manager.generate(message, conversation, contexte_supp)
        if ollama_response is not None:
            return {'message': ollama_response}

        # ------------------------------------------------------------------
        # Step 2: Fallback — rule-based assistant (existing logic)
        # ------------------------------------------------------------------
        msg_lower = message.lower()
        contexte_type = conversation.contexte
        langue = detecter_langue(message)

        if conversation.entite_id:
            try:
                entite = None
                if contexte_type == 'bsd':
                    entite = BordereauSuiviDechet.objects.get(id=conversation.entite_id)
                    return self._analyser_bsd_contextuel(entite, message, langue)
                elif contexte_type == 'recuperateur':
                    entite = Recuperateur.objects.get(id=conversation.entite_id)
                    return self._analyser_recuperateur_contextuel(entite, message, langue)
                elif contexte_type == 'agrement':
                    entite = AgrementRecuperateur.objects.get(id=conversation.entite_id)
                    return self._analyser_agrement_contextuel(entite, message, langue)
                elif contexte_type == 'operation':
                    entite = Traceability.objects.get(id=conversation.entite_id)
                    return self._analyser_operation_contextelle(entite, message, langue)
            except Exception:
                pass

        # If message contains a nomenclature code pattern, skip glossary and go straight to nomenclature
        import re as _re
        if _re.search(r'\d{1,2}\.\d{1,2}\.\d{1,2}', message):
            reponse_ctx = self._reponse_contextuelle(message, msg_lower, conversation, langue)
            if reponse_ctx:
                return reponse_ctx

        resultats_glossaire = rechercher_glossaire(message)
        if resultats_glossaire:
            reponse_glossaire = formater_glossaire(resultats_glossaire, langue)
            return {'message': reponse_glossaire}

        reponse_ctx = self._reponse_contextuelle(message, msg_lower, conversation, langue)
        if reponse_ctx:
            return reponse_ctx

        if langue == 'ar':
            greetings = ['مرحبا', 'سلام', 'السلام', 'مساعدة', 'أهلا', 'هاي']
            if any(mot in msg_lower for mot in greetings):
                return {
                    'message': """مرحباً! أنا المساعد التنظيمي لإدارة النفايات في RECUP-DZ. يمكنني مساعدتك في :

1. **قاموس النفايات** : تعريف جميع المصطلحات التنظيمية (بوليصة المتابعة، الاعتماد، النفايات الخطرة...)
2. **البحث في التصنيف** : البحث بالاسم أو الرمز
3. **التحقق من الاعتمادات** : الحالة والصلاحية
4. **تحليل بوليصات المتابعة** : التأخيرات والبيانات غير الكاملة
5. **تحليل المخزون** : التجاوزات والمخاطر
6. **التنبيهات الذكية** : الشذوذ المكتشف تلقائياً
7. **التقارير التنظيمية** : شهرية وربع سنوية وسنوية

جرب مثلاً: *"ما هي بوليصة المتابعة؟"*, *"نفايات خطرة"*, *"اعتماد"*
كيف يمكنني مساعدتك اليوم؟"""
                }
            return {
                'message': f"لقد تلقّيت رسالتك : \"{message}\".\n\nيمكنني مساعدتك في :\n\n1. **قاموس النفايات** — تعريف جميع المصطلحات التنظيمية\n2. **البحث في التصنيف** — الرموز والتصنيفات\n3. **التحقق من الاعتمادات** — الحالة والصلاحية\n4. **تحليل بوليصات المتابعة** — التأخيرات والمطابقة\n5. **تحليل المخزون** — التجاوزات والمخاطر\n6. **اللوائح** — القانون 01-19، المرسوم 06-104\n\nجرب مثلاً: *\"ما هي بوليصة المتابعة؟\"*, *\"نفايات خطرة\"*, *\"اعتماد\"*"
            }
        else:
            greetings = ['bonjour', 'salut', 'hello', 'aide', 'help', 'coucou']
            if any(mot in msg_lower for mot in greetings):
                return {
                    'message': """Bonjour ! Je suis l'Assistant Réglementaire Déchets de RECUP-DZ. Je peux vous aider avec :

1. **Glossaire des déchets** : Définitions de tous les termes réglementaires (BSD, agrément, déchet dangereux...)
2. **Recherche nomenclature** : Recherche par nom ou code
3. **Vérification des agréments** : Statuts et validité
4. **Analyse des BSD** : Retards, incomplets, conformité
5. **Analyse des stocks** : Dépassements et risques
6. **Alertes intelligentes** : Anomalies détectées automatiquement
7. **Rapports réglementaires** : Mensuels, trimestriels, annuels

Essayez par exemple : *"Qu'est-ce qu'un BSD ?"*, *"déchet dangereux"*, *"agrément"*
Comment puis-je vous aider aujourd'hui ?"""
                }
            return {
                'message': f"J'ai bien reçu votre message : \"{message}\".\n\nJe peux vous aider avec :\n\n1. **Glossaire des déchets** — Définitions de tous les termes réglementaires\n2. **Recherche nomenclature** — Codes et classifications des déchets\n3. **Vérification des agréments** — Statuts et validité\n4. **Analyse des BSD** — Retards, incomplets, conformité\n5. **Analyse des stocks** — Dépassements et risques\n6. **Réglementation** — Loi 01-19, Décret 06-104\n\nEssayez par exemple : *\"Qu'est-ce qu'un BSD ?\"*, *\"déchet dangereux\"*, *\"agrément\"*"
            }

        return {
            'message': f"J'ai bien reçu votre message : \"{message}\".\n\nJe peux vous aider avec :\n\n1. **Glossaire des déchets** — Définitions de tous les termes réglementaires\n2. **Recherche nomenclature** — Codes et classifications des déchets\n3. **Vérification des agréments** — Statuts et validité\n4. **Analyse des BSD** — Retards, incomplets, conformité\n5. **Analyse des stocks** — Dépassements et risques\n6. **Réglementation** — Loi 01-19, Décret 06-104\n\nEssayez par exemple : *\"Qu'est-ce qu'un BSD ?\"*, *\"déchet dangereux\"*, *\"agrément\"*"
        }

    def _reponse_contextuelle(self, message, msg_lower, conversation, langue='fr'):
        import re
        # Detect code patterns like 15.01.01, 1.3.1, 16.06.01
        if re.search(r'\d{1,2}\.\d{1,2}\.\d{1,2}', message):
            return self._rechercher_nomenclature(message, langue)

        nomenclature_keywords = [
            'nomenclature', 'code', 'classification', 'catégorie', 'classe',
            'huile', 'batterie', 'baterie', 'pile', 'accumulateur',
            'métal', 'metal', 'cuivre', 'aluminium', 'fer', 'acier', 'plomb', 'zinc',
            'plastique', 'papier', 'carton', 'verre', 'bois', 'textile',
            'pneu', 'emballage', 'solvant', 'acide', 'peinture', 'déchet', 'dechet',
            'chimique', 'inflammable', 'inflamable', 'toxique', 'dangereux',
            'زيت', 'بطارية', 'معدن', 'نحاس', 'حديد', 'فولاذ', 'بلاستيك', 'ورق',
            'زجاج', 'خشب', 'نسيج', 'إطارات', 'تغليف', 'مذيبات', 'دهانات', 'نفايات',
        ]
        if any(mot in msg_lower for mot in nomenclature_keywords):
            return self._rechercher_nomenclature(message, langue)

        agrement_keywords = ['agrément', 'agréments', 'validité', 'expire', 'expiré', 'اعتماد', 'صلاحيته']
        if any(mot in msg_lower for mot in agrement_keywords):
            return self._verifier_agrements(langue)

        bsd_keywords = ['bsd', 'bordereau', 'bordereaux', 'بوليصة']
        if any(mot in msg_lower for mot in bsd_keywords):
            return self._analyser_bsd(langue)

        stock_keywords = ['stock', 'stocks', 'quantité', 'مخزون', 'كمية']
        if any(mot in msg_lower for mot in stock_keywords):
            return self._analyser_stocks(langue)

        loi_keywords = ['loi 01-19', 'décret', 'قانون', 'مرسوم']
        if any(mot in msg_lower for mot in loi_keywords):
            return self._recherche_reglementaire(message, langue)

        return None

    def _rechercher_nomenclature(self, message, langue='fr'):
        import re
        msg_clean = message.strip().replace(':', '').replace('?', '').replace('!', '').strip()

        # Detect code pattern and search in frontend data (supports both formats: 1.3.1 and 01.03.01)
        code_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{1,2})', msg_clean)
        if code_match:
            # Build both padded and unpadded versions for flexible matching
            parts = [int(x) for x in code_match.groups()]
            formats = [
                f'{parts[0]}.{parts[1]}.{parts[2]}',       # 1.3.1
                f'{parts[0]:02d}.{parts[1]:02d}.{parts[2]:02d}',  # 01.03.01
                f'{parts[0]}.{parts[1]:02d}.{parts[2]:02d}',      # 1.03.01
                f'{parts[0]:02d}.{parts[1]}.{parts[2]}',          # 01.3.1
            ]
            results = []
            seen = set()
            for fmt in formats:
                for item in rechercher_par_code(fmt):
                    key = (item['code'], item['classe'], item['annexe'])
                    if key not in seen:
                        seen.add(key)
                        results.append(item)

            if results:
                if len(results) == 1:
                    return self._nomenclature_detail(results[0], langue)
                # Multiple entries (e.g., 1.3.1 has both Annexe II and III)
                return self._formater_resultats_nomenclature(results, langue)

        # Common typo corrections
        typo_map = {
            'baterie': 'batterie', 'bateris': 'batterie',
            'electrique': 'électrique', 'electronique': 'électronique',
            'inflamable': 'inflammable', 'cancerogene': 'cancérogène',
            'corosif': 'corrosif',
        }
        corrected = msg_clean.lower()
        for wrong, right in typo_map.items():
            corrected = corrected.replace(wrong, right)

        results = rechercher_par_texte(corrected)[:10]
        if results:
            return self._formater_resultats_nomenclature(results, langue)

        if langue == 'ar':
            return {'message': "لم يتم العثور على نتائج في التصنيف. جرب بحثاً بكلمة أخرى (مثال: 'زيت', 'بطارية', 'معدن')."}
        return {'message': "Aucun résultat trouvé dans la nomenclature. Essayez avec un autre terme (ex: 'huile', 'batterie', 'métal')."}

    def _formater_resultats_nomenclature(self, results, langue='fr'):
        """Format multi-result search output (shared by code search and text search)."""
        if langue == 'ar':
            reponse = "## نتائج البحث في التصنيف :\n\n"
            for item in results:
                danger = " ⚠️ خطير" if item.get('danger_fr') else ""
                annexe = f" | الملحق: {item['annexe']}" if item.get('annexe') else ""
                nom = item['nom_fr']
                reponse += f"- **{item['code']}** — {nom}{danger}\n"
                famille_nom = FAMILLES.get(item['famille'], item['famille'])
                reponse += f"  الفئة : {item['classe']} | العائلة : {item['famille']} — {famille_nom}{annexe}\n"
                bsd_obligatoire, agrement_requis = inferer_bsd_agrement(item['classe'])
                if bsd_obligatoire:
                    reponse += f"  📋 بوليصة متابعة مطلوبة\n"
                if agrement_requis:
                    reponse += f"  📝 اعتماد مطلوب\n"
                reponse += "\n"
            reponse += "\n_المصدر: المرجع الوطني للنفايات، المرسوم التنفيذي رقم 06-104_"
        else:
            reponse = "## Résultats de recherche dans la nomenclature :\n\n"
            for item in results:
                danger = " ⚠️ DANGEREUX" if item.get('danger_fr') else ""
                annexe = f" | Annexe {item['annexe']}" if item.get('annexe') else ""
                nom = item['nom_fr']
                reponse += f"- **{item['code']}** — {nom}{danger}\n"
                famille_nom = FAMILLES.get(item['famille'], item['famille'])
                reponse += f"  Catégorie : {item['classe']} | Famille : {item['famille']} — {famille_nom}{annexe}\n"
                bsd_obligatoire, agrement_requis = inferer_bsd_agrement(item['classe'])
                if bsd_obligatoire:
                    reponse += f"  📋 BSD obligatoire\n"
                if agrement_requis:
                    reponse += f"  📝 Agrément requis\n"
                reponse += "\n"
            reponse += "\n_Source : Référentiel national des déchets, Décret exécutif n°06-104_"
        return {'message': reponse}

    def _nomenclature_detail(self, item, langue='fr'):
        """
        Affiche le détail d'un item de nomenclature (dict issu de nomenclature_data.py).
        Compatible avec les données de la page Nomenclature frontend.
        """
        fr_label, ar_label = CLASSE_LABELS.get(item['classe'], (item['classe'], item['classe']))

        # Parse dangers from danger_fr string (newline-separated)
        danger_fr = item.get('danger_fr', '') or ''
        dangers = []
        danger_translation = {
            'Explosible': ('Explosible', 'متفجر'),
            'Explosive': ('Explosive', 'متفجر'),
            'Inflammable': ('Inflammable', 'قابل للاشتعال'),
            'Facilement inflammable': ('Facilement inflammable', 'قابل للاشتعال بسهولة'),
            'Comburante': ('Comburante', 'مؤكسد'),
            'Toxique': ('Toxique', 'سام'),
            'Toxique vis-à-vis de la reproduction': ('Toxique pour la reproduction', 'سام للتكاثر'),
            'Cancérogène': ('Cancérogène', 'مسرطن'),
            'Mutagène': ('Mutagène', 'مطفر'),
            'Corrosive': ('Corrosive', 'آكل'),
            'Corrosif': ('Corrosif', 'آكل'),
            'Irritante': ('Irritante', 'مهيج'),
            'Nocive': ('Nocive', 'ضار'),
            'Infectieuse': ('Infectieuse', 'ممرض'),
            'Dangereuse pour l\'environnement': ('Dangereux environnement', 'خطير للبيئة'),
        }
        if danger_fr:
            for d in danger_fr.split('\n'):
                d = d.strip()
                if d and d in danger_translation:
                    dangers.append(danger_translation[d])
                elif d:
                    dangers.append((d, d))

        bsd_obligatoire, agrement_requis = inferer_bsd_agrement(item['classe'])
        famille_nom = FAMILLES.get(item['famille'], item['famille'])

        if langue == 'ar':
            reponse = f"## التصنيف — `{item['code']}`\n\n"
            reponse += f"### {item['nom_fr']}\n\n"
            reponse += f"**الرمز** : `{item['code']}`\n"
            reponse += f"**التصنيف** : {item['classe']} — {ar_label}\n"
            reponse += f"**العائلة** : {item['famille']} — {famille_nom}\n"
            if item.get('annexe'):
                reponse += f"**الملحق** : {item['annexe']}\n"
            if dangers:
                reponse += f"**أنواع الخطورة** : {', '.join(ar for _, ar in dangers)}\n"
            reponse += "\n"
            reponse += f"**📋 بوليصة متابعة** : {'مطلوب' if bsd_obligatoire else 'غير مطلوب'}\n"
            reponse += f"**📝 اعتماد** : {'مطلوب' if agrement_requis else 'غير مطلوب'}\n"
            reponse += "\n_المصدر: المرجع الوطني للنفايات، المرسوم التنفيذي رقم 06-104_"
        else:
            reponse = f"## Nomenclature — `{item['code']}`\n\n"
            reponse += f"### {item['nom_fr']}\n\n"
            reponse += f"**Code** : `{item['code']}`\n"
            reponse += f"**Classe** : {item['classe']} — {fr_label}\n"
            reponse += f"**Famille** : {item['famille']} — {famille_nom}\n"
            if item.get('annexe'):
                reponse += f"**Annexe** : {item['annexe']}\n"
            if danger_fr:
                reponse += f"**Dangerosité** : {danger_fr.replace(chr(10), ', ')}\n"
            if dangers:
                reponse += f"**Types de danger** : {', '.join(fr for fr, _ in dangers)}\n"
            reponse += "\n"
            reponse += f"**📋 BSD obligatoire** : {'Oui' if bsd_obligatoire else 'Non'}\n"
            reponse += f"**📝 Agrément requis** : {'Oui' if agrement_requis else 'Non'}\n"
            reponse += "\n_Source : Référentiel national des déchets, Décret exécutif n°06-104_"
        return {'message': reponse}

    def _verifier_agrements(self, langue='fr'):
        aujourd_hui = timezone.now().date()
        agrements = AgrementRecuperateur.objects.filter(statut='ACTIF').select_related('recuperateur')
        bientot_expires = []
        expires = []
        for agr in agrements:
            if agr.date_fin:
                if agr.date_fin < aujourd_hui:
                    expires.append(agr)
                elif agr.date_fin < aujourd_hui + timedelta(days=30):
                    bientot_expires.append(agr)

        if langue == 'ar':
            reponse = "## حالة الاعتمادات\n\n"
            reponse += f"📊 **ملخص** : {agrements.count()} اعتماد نشط\n\n"
            if expires:
                reponse += f"### ⚠️ اعتمادات منتهية الصلاحية ({len(expires)})\n"
                for e in expires[:10]:
                    reponse += f"- **{e.numero_agrement}** — {e.recuperateur.nom_raison_sociale} — انتهت الصلاحية في {e.date_fin}\n"
            if bientot_expires:
                reponse += f"\n### ⏳ تنتهي قريباً ({len(bientot_expires)})\n"
                for b in bientot_expires[:10]:
                    reponse += f"- **{b.numero_agrement}** — {b.recuperateur.nom_raison_sociale} — تنتهي الصلاحية في {b.date_fin} (خلال {(b.date_fin - aujourd_hui).days} يوم)\n"
            if not expires and not bientot_expires:
                reponse += "✅ جميع الاعتمادات سارية المفعول."
        else:
            reponse = "## État des agréments\n\n"
            reponse += f"📊 **Résumé** : {agrements.count()} agréments actifs\n\n"
            if expires:
                reponse += f"### ⚠️ Agréments expirés ({len(expires)})\n"
                for e in expires[:10]:
                    reponse += f"- **{e.numero_agrement}** — {e.recuperateur.nom_raison_sociale} — Expiré le {e.date_fin}\n"
            if bientot_expires:
                reponse += f"\n### ⏳ Expirent bientôt ({len(bientot_expires)})\n"
                for b in bientot_expires[:10]:
                    reponse += f"- **{b.numero_agrement}** — {b.recuperateur.nom_raison_sociale} — Expire le {b.date_fin} (dans {(b.date_fin - aujourd_hui).days} jours)\n"
            if not expires and not bientot_expires:
                reponse += "✅ Tous les agréments sont valides."
        return {'message': reponse}

    def _analyser_bsd(self, langue='fr'):
        aujourd_hui = timezone.now().date()
        bsds = BordereauSuiviDechet.objects.all()
        retards = []
        incomplets = []
        for bsd in bsds:
            if bsd.statut == 'BROUILLON' and bsd.date_creation:
                delta = (aujourd_hui - bsd.date_creation).days
                if delta > 7:
                    incomplets.append(bsd)
            elif bsd.date_emission and bsd.statut not in ['TERMINE', 'ANNULE', 'ARCHIVE']:
                delta = (aujourd_hui - bsd.date_emission).days
                if delta > 14:
                    retards.append(bsd)

        if langue == 'ar':
            reponse = "## تحليل بوليصات المتابعة\n\n"
            reponse += f"📊 العدد الإجمالي : {bsds.count()}\n\n"
            if retards:
                reponse += f"### 🔴 بوليصات متأخرة ({len(retards)})\n"
                for r in retards[:10]:
                    reponse += f"- **{r.numero}** — أُصدرت في {r.date_emission}\n"
            if incomplets:
                reponse += f"\n### 🟡 بوليصات غير مكتملة ({len(incomplets)})\n"
                for i in incomplets[:10]:
                    reponse += f"- **{i.numero}** — في مرحلة المسودة\n"
            if not retards and not incomplets:
                reponse += "✅ لم يتم اكتشاف أي شذوذ في بوليصات المتابعة."
        else:
            reponse = "## Analyse des BSD\n\n"
            reponse += f"📊 Total BSD : {bsds.count()}\n\n"
            if retards:
                reponse += f"### 🔴 BSD en retard ({len(retards)})\n"
                for r in retards[:10]:
                    reponse += f"- **{r.numero}** — Émis le {r.date_emission}\n"
            if incomplets:
                reponse += f"\n### 🟡 BSD incomplets ({len(incomplets)})\n"
                for i in incomplets[:10]:
                    reponse += f"- **{i.numero}** — En brouillon\n"
            if not retards and not incomplets:
                reponse += "✅ Aucune anomalie détectée dans les BSD."
        return {'message': reponse}

    def _analyser_stocks(self, langue='fr'):
        if langue == 'ar':
            reponse = "## تحليل المخزون\n\n"
            try:
                operations = Traceability.objects.filter(statut='EN_COURS')
                reponse += f"📊 العمليات الجارية : {operations.count()}\n\n"
                if operations:
                    total = sum(float(op.quantite or 0) for op in operations)
                    reponse += f"**الكمية الإجمالية قيد المعالجة** : {total:,.0f} كغ\n"
            except Exception:
                reponse += "وحدة المخزون غير متاحة حالياً."
        else:
            reponse = "## Analyse des stocks\n\n"
            try:
                operations = Traceability.objects.filter(statut='EN_COURS')
                reponse += f"📊 Opérations en cours : {operations.count()}\n\n"
                if operations:
                    total = sum(float(op.quantite or 0) for op in operations)
                    reponse += f"**Quantité totale en traitement** : {total:,.0f} kg\n"
            except Exception:
                reponse += "Module Stocks non disponible pour le moment."
        return {'message': reponse}

    def _recherche_reglementaire(self, message, langue='fr'):
        results = KnowledgeBase.objects.filter(
            Q(titre__icontains=message) |
            Q(contenu__icontains=message),
            est_active=True
        )[:5]
        if results:
            if langue == 'ar':
                reponse = "## النتائج التنظيمية :\n\n"
                for r in results:
                    reponse += f"### {r.titre}\n"
                    reponse += f"**المصدر** : {r.reference_reglementaire}\n\n"
                    contenu = r.contenu[:400] if len(r.contenu) > 400 else r.contenu
                    reponse += f"{contenu}{'...' if len(r.contenu) > 400 else ''}\n\n"
            else:
                reponse = "## Résultats réglementaires :\n\n"
                for r in results:
                    reponse += f"### {r.titre}\n"
                    reponse += f"**Source** : {r.reference_reglementaire}\n\n"
                    contenu = r.contenu[:400] if len(r.contenu) > 400 else r.contenu
                    reponse += f"{contenu}{'...' if len(r.contenu) > 400 else ''}\n\n"
            return {'message': reponse}
        if langue == 'ar':
            return {'message': "لم يتم العثور على نتائج تنظيمية. اتصل بالمسؤول لإثراء قاعدة المعرفة."}
        return {'message': "Aucun résultat réglementaire trouvé. Contactez votre administrateur pour enrichir la base de connaissances."}

    def _analyser_bsd_contextuel(self, bsd, message, langue='fr'):
        if langue == 'ar':
            reponse = f"## تحليل بوليصة المتابعة #{bsd.numero}\n\n"
            reponse += f"**الحالة** : {bsd.statut}\n"
            reponse += f"**رمز النفاية** : {bsd.code_dechet}\n"
            reponse += f"**الوصف** : {bsd.designation}\n"
            reponse += f"**الكمية** : {bsd.quantite} {bsd.unite}\n"
            if bsd.statut == 'BROUILLON':
                reponse += "\n⚠️ **تنبيه** : هذه البوليصة في مرحلة المسودة. يجب إكمالها وإصدارها قبل أي عملية."
            if bsd.date_emission:
                reponse += f"\n**تاريخ الإصدار** : {bsd.date_emission}"
            reponse += "\n\n✅ تم إنشاء التحليل تلقائياً."
        else:
            reponse = f"## Analyse du BSD #{bsd.numero}\n\n"
            reponse += f"**Statut** : {bsd.statut}\n"
            reponse += f"**Code déchet** : {bsd.code_dechet}\n"
            reponse += f"**Désignation** : {bsd.designation}\n"
            reponse += f"**Quantité** : {bsd.quantite} {bsd.unite}\n"
            if bsd.statut == 'BROUILLON':
                reponse += "\n⚠️ **Attention** : Ce BSD est en brouillon. Il doit être complété et émis avant toute opération."
            if bsd.date_emission:
                reponse += f"\n**Date émission** : {bsd.date_emission}"
            reponse += "\n\n✅ Analyse générée automatiquement."
        return {'message': reponse, 'contexte': {'bsd': {'id': bsd.id, 'numero': bsd.numero}}}

    def _analyser_recuperateur_contextuel(self, recuperateur, message, langue='fr'):
        if langue == 'ar':
            reponse = f"## ملف المسترد : {recuperateur.nom_raison_sociale}\n\n"
            reponse += f"**النوع** : {recuperateur.type_recuperateur}\n"
            reponse += f"**الحالة القانونية** : {recuperateur.statut_juridique}\n"
            reponse += f"**الولاية** : {recuperateur.wilaya}\n"
            if recuperateur.email:
                reponse += f"**البريد الإلكتروني** : {recuperateur.email}\n"
            if recuperateur.telephone:
                reponse += f"**الهاتف** : {recuperateur.telephone}\n"
            agrements = recuperateur.agrements.filter(statut='ACTIF')
            if agrements:
                reponse += f"\n**الاعتمادات النشطة** : {agrements.count()}\n"
                for agr in agrements[:3]:
                    reponse += f"- {agr.numero_agrement} (تنتهي الصلاحية في {agr.date_fin})\n"
            reponse += "\n✅ تم إنشاء التحليل تلقائياً."
        else:
            reponse = f"## Fiche récupérateur : {recuperateur.nom_raison_sociale}\n\n"
            reponse += f"**Type** : {recuperateur.type_recuperateur}\n"
            reponse += f"**Statut** : {recuperateur.statut_juridique}\n"
            reponse += f"**Wilaya** : {recuperateur.wilaya}\n"
            if recuperateur.email:
                reponse += f"**Email** : {recuperateur.email}\n"
            if recuperateur.telephone:
                reponse += f"**Téléphone** : {recuperateur.telephone}\n"
            agrements = recuperateur.agrements.filter(statut='ACTIF')
            if agrements:
                reponse += f"\n**Agréments actifs** : {agrements.count()}\n"
                for agr in agrements[:3]:
                    reponse += f"- {agr.numero_agrement} (expire le {agr.date_fin})\n"
            reponse += "\n✅ Analyse générée automatiquement."
        return {'message': reponse, 'contexte': {'recuperateur': {'id': recuperateur.id}}}

    def _analyser_agrement_contextuel(self, agrement, message, langue='fr'):
        aujourd_hui = timezone.now().date()
        est_valide = agrement.date_fin >= aujourd_hui if agrement.date_fin else False
        jours_restants = (agrement.date_fin - aujourd_hui).days if agrement.date_fin else 0
        if langue == 'ar':
            reponse = f"## الاعتماد #{agrement.numero_agrement}\n\n"
            reponse += f"**المسترد** : {agrement.recuperateur.nom_raison_sociale}\n"
            reponse += f"**الحالة** : {agrement.statut}\n"
            reponse += f"**الصلاحية** : {'✅ ساري' if est_valide else '❌ منتهي'} (تنتهي في {agrement.date_fin})\n"
            reponse += f"**الأيام المتبقية** : {jours_restants}\n"
            if agrement.codes_dechets:
                reponse += f"**رموز النفايات المصرح بها** : {agrement.codes_dechets}\n"
            if not est_valide:
                reponse += "\n⚠️ هذا الاعتماد منتهي الصلاحية. يلزم تقديم طلب تجديد وفقاً للائحة الجزائرية."
            elif jours_restants < 30:
                reponse += f"\n⚠️ هذا الاعتماد ينتهي خلال {jours_restants} يوماً. فكر في بدء إجراءات التجديد."
            reponse += "\n\n_المصدر: القانون 01-19 المتعلق بإدارة النفايات_"
        else:
            reponse = f"## Agrément #{agrement.numero_agrement}\n\n"
            reponse += f"**Récupérateur** : {agrement.recuperateur.nom_raison_sociale}\n"
            reponse += f"**Statut** : {agrement.statut}\n"
            reponse += f"**Validité** : {'✅ Valide' if est_valide else '❌ Expiré'} (expire le {agrement.date_fin})\n"
            reponse += f"**Jours restants** : {jours_restants}\n"
            if agrement.codes_dechets:
                reponse += f"**Codes déchets autorisés** : {agrement.codes_dechets}\n"
            if not est_valide:
                reponse += "\n⚠️ Cet agrément a expiré. Une demande de renouvellement est requise conformément à la réglementation algérienne."
            elif jours_restants < 30:
                reponse += f"\n⚠️ Cet agrément expire dans {jours_restants} jours. Pensez à entamer la procédure de renouvellement."
            reponse += "\n\n_Source : Loi 01-19 relative à la gestion des déchets_"
        return {'message': reponse, 'contexte': {'agrement': {'id': agrement.id}}}

    def _analyser_operation_contextelle(self, operation, message, langue='fr'):
        if langue == 'ar':
            reponse = f"## العملية #{operation.numero}\n\n"
            reponse += f"**المسترد** : {operation.recuperateur.nom_raison_sociale}\n"
            reponse += f"**الحالة** : {operation.statut}\n"
            reponse += f"**الوجهة** : {operation.destination_type}\n"
            reponse += f"**النفاية** : {operation.designation_dechet} ({operation.code_dechet})\n"
            reponse += f"**الكمية** : {operation.quantite} {operation.unite}\n"
            if operation.transporteur:
                reponse += f"**الناقل** : {operation.transporteur.nom_raison_sociale}\n"
            if operation.valorisateur:
                reponse += f"**المثمِن** : {operation.valorisateur.nom_raison_sociale}\n"
            reponse += "\n✅ تم إنشاء التحليل تلقائياً."
        else:
            reponse = f"## Opération #{operation.numero}\n\n"
            reponse += f"**Récupérateur** : {operation.recuperateur.nom_raison_sociale}\n"
            reponse += f"**Statut** : {operation.statut}\n"
            reponse += f"**Destination** : {operation.destination_type}\n"
            reponse += f"**Déchet** : {operation.designation_dechet} ({operation.code_dechet})\n"
            reponse += f"**Quantité** : {operation.quantite} {operation.unite}\n"
            if operation.transporteur:
                reponse += f"**Transporteur** : {operation.transporteur.nom_raison_sociale}\n"
            if operation.valorisateur:
                reponse += f"**Valorisateur** : {operation.valorisateur.nom_raison_sociale}\n"
            reponse += "\n✅ Analyse générée automatiquement."
        return {'message': reponse, 'contexte': {'operation': {'id': operation.id}}}

    @action(detail=False, methods=['post'])
    def analyse_contextuelle(self, request):
        contexte_type = request.data.get('contexte_type', 'general')
        entite_id = request.data.get('entite_id')
        question = request.data.get('question', '')

        if not question:
            return Response({'error': 'La question est requise'}, status=status.HTTP_400_BAD_REQUEST)

        conversation = AIConversation.objects.create(
            user=request.user,
            contexte=contexte_type,
            entite_id=entite_id,
            titre=f"Analyse: {contexte_type} #{entite_id or ''}"
        )
        AIMessage.objects.create(
            conversation=conversation,
            role='USER',
            message=question
        )

        reponse = self._generer_reponse_intelligente(question, conversation, {})
        AIMessage.objects.create(
            conversation=conversation,
            role='ASSISTANT',
            message=reponse['message'],
            contexte_json=reponse.get('contexte', {})
        )

        return Response({'conversation_id': conversation.id, 'reponse': reponse['message']})

    @action(detail=False, methods=['get'])
    def suggestions(self, request):
        suggestions = [
            "Quels agréments expirent bientôt ?",
            "Y a-t-il des BSD en retard ?",
            "Classifie le déchet : huile moteur usagée",
            "Quelle est la réglementation sur les déchets hospitaliers ?",
            "Analyser cet agrément",
            "Générer un rapport mensuel",
            "Vérifier la conformité d'un récupérateur",
            "Liste des déchets dangereux autorisés",
        ]
        return Response({'suggestions': suggestions})


class AIMessageViewSet(viewsets.ReadOnlyModelViewSet):
    module_label     = 'ai_assistant'
    serializer_class = AIMessageSerializer
    permission_classes = [ModulePermission]

    def get_queryset(self):
        conversation_id = self.request.query_params.get('conversation_id')
        if conversation_id:
            return AIMessage.objects.filter(conversation_id=conversation_id, conversation__user=self.request.user)
        return AIMessage.objects.filter(conversation__user=self.request.user).select_related('conversation')


class AIAlertViewSet(viewsets.ModelViewSet):
    module_label     = 'ai_assistant'
    serializer_class = AIAlertSerializer
    permission_classes = [ModulePermission]

    def get_queryset(self):
        qs = AIAlert.objects.filter(user=self.request.user)
        est_lue = self.request.query_params.get('est_lue')
        if est_lue is not None:
            qs = qs.filter(est_lue=(est_lue.lower() == 'true'))
        return qs

    @action(detail=True, methods=['post'])
    def marquer_lue(self, request, pk=None):
        alerte = self.get_object()
        alerte.est_lue = True
        alerte.save()
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'])
    def generer_alertes_auto(self, request):
        anomalies_bsd = detecter_anomalies_bsd()
        anomalies_agr = detecter_anomalies_agrements()
        toutes_anomalies = anomalies_bsd + anomalies_agr

        creees = 0
        for anomalie in toutes_anomalies:
            user = request.user
            existe = AIAlert.objects.filter(
                type_alerte=anomalie['type'],
                entite_type=anomalie['entite_type'],
                entite_id=anomalie['entite_id'],
                est_lue=False
            ).exists()
            if not existe:
                AIAlert.objects.create(
                    type_alerte=anomalie['type'],
                    niveau=anomalie['niveau'],
                    description=anomalie['description'],
                    user=user,
                    entite_type=anomalie['entite_type'],
                    entite_id=anomalie['entite_id'],
                    lien=anomalie['lien']
                )
                creees += 1

        return Response({'alertes_creees': creees, 'total_anomalies': len(toutes_anomalies)})

    @action(detail=False, methods=['get'])
    def resume_alertes(self, request):
        alertes = AIAlert.objects.filter(user=request.user)
        par_type = alertes.values('type_alerte').annotate(count=Count('id'))
        par_niveau = alertes.values('niveau').annotate(count=Count('id'))
        non_lues = alertes.filter(est_lue=False).count()
        critiques = alertes.filter(niveau='critique', est_lue=False).count()

        return Response({
            'total': alertes.count(),
            'non_lues': non_lues,
            'critiques': critiques,
            'par_type': list(par_type),
            'par_niveau': list(par_niveau),
        })


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    module_label     = 'ai_assistant'
    serializer_class = KnowledgeBaseSerializer
    permission_classes = [ModulePermission]

    def get_queryset(self):
        qs = KnowledgeBase.objects.filter(est_active=True)
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        langue = self.request.query_params.get('langue')
        if langue:
            qs = qs.filter(langue=langue)
        recherche = self.request.query_params.get('recherche')
        if recherche:
            qs = qs.filter(
                Q(titre__icontains=recherche) |
                Q(contenu__icontains=recherche) |
                Q(reference_reglementaire__icontains=recherche)
            )
        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return KnowledgeBaseCreateSerializer
        return KnowledgeBaseSerializer

    @action(detail=False, methods=['get'])
    def categories(self, request):
        categories = [{'id': c[0], 'label': c[1]} for c in KnowledgeBase.CATEGORIE_CHOICES]
        return Response({'categories': categories})

    @action(detail=False, methods=['get'])
    def rechercher_reglementaire(self, request):
        terme = request.query_params.get('terme', '')
        if not terme:
            return Response({'results': []})
        results = self.get_queryset().filter(
            Q(titre__icontains=terme) |
            Q(contenu__icontains=terme) |
            Q(reference_reglementaire__icontains=terme)
        )[:20]
        serializer = self.get_serializer(results, many=True)
        return Response({'results': serializer.data, 'terme': terme})


class AIRecommendationViewSet(viewsets.ModelViewSet):
    module_label     = 'ai_assistant'
    serializer_class = AIRecommendationSerializer
    permission_classes = [ModulePermission]

    def get_queryset(self):
        return AIRecommendation.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def changer_statut(self, request, pk=None):
        recommendation = self.get_object()
        nouveau_statut = request.data.get('statut')
        if nouveau_statut not in dict(AIRecommendation.STATUT_CHOICES):
            return Response({'error': 'Statut invalide'}, status=status.HTTP_400_BAD_REQUEST)
        recommendation.statut = nouveau_statut
        if nouveau_statut == 'REALISEE':
            recommendation.date_traitement = timezone.now()
        recommendation.save()
        return Response({'statut': 'ok'})

    @action(detail=False, methods=['get'])
    def recommendations_actives(self, request):
        recommendations = AIRecommendation.objects.filter(
            user=request.user,
            statut__in=['ACTIVE', 'EN_ATTENTE']
        )[:10]
        serializer = self.get_serializer(recommendations, many=True)
        return Response({'recommendations': serializer.data})


class AIDashboardViewSet(viewsets.ViewSet):
    module_label     = 'ai_assistant'
    permission_classes = [ModulePermission]

    @action(detail=False, methods=['get'])
    def statistiques(self, request):
        user = request.user
        questions_posees = AIMessage.objects.filter(
            conversation__user=user, role='USER'
        ).count()
        alertes_detectees = AIAlert.objects.filter(user=user).count()
        alertes_non_lues = AIAlert.objects.filter(user=user, est_lue=False).count()

        bsd_analyses = AIConversation.objects.filter(
            user=user, contexte='bsd'
        ).count()

        agrements_verifies = AIConversation.objects.filter(
            user=user, contexte='agrement'
        ).count()

        rapports_generes = AIRecommendation.objects.filter(
            user=user, type_recommandation='analyse'
        ).count()

        conversations_total = AIConversation.objects.filter(user=user).count()

        data = {
            'questions_posees': questions_posees,
            'alertes_detectees': alertes_detectees,
            'bsd_analyses': bsd_analyses,
            'agrements_verifies': agrements_verifies,
            'rapports_generes': rapports_generes,
            'conversations_total': conversations_total,
            'alertes_non_lues': alertes_non_lues,
        }
        serializer = AIStatisticsSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def alertes_recuperees(self, request):
        alertes = AIAlert.objects.filter(user=request.user, est_lue=False)[:20]
        serializer = AIAlertSerializer(alertes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def historique_recent(self, request):
        conversations = AIConversation.objects.filter(
            user=request.user
        ).order_by('-last_message_at')[:10]
        serializer = AIConversationSerializer(conversations, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recommandations_actives(self, request):
        recommendations = AIRecommendation.objects.filter(
            user=request.user,
            statut__in=['ACTIVE', 'EN_ATTENTE']
        ).order_by('-date_creation')[:10]
        serializer = AIRecommendationSerializer(recommendations, many=True)
        return Response({'recommendations': serializer.data})
