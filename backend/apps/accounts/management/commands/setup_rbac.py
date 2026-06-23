from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


# ── Role definitions ──────────────────────────────────────────────────────────
ROLES = {
    'super_administrateur':   'Super Administrateur',
    'administrateur':         'Administrateur',
    'recuperateur':           'Récupérateur',
    'responsable_collecte':   'Responsable Collecte',
    'agent_collecte':         'Agent de Collecte',
    'responsable_decharge':   'Responsable Décharge',
    'observateur':            'Observateur',
}

# ── Permissions matrix: role → {app.model: [actions]} ────────────────────────
# actions: v=view, a=add, c=change, d=delete
PERM_MATRIX = {
    'super_administrateur': {
        'accounts.user':                    ['v', 'a', 'c', 'd'],
        'recuperateurs.recuperateur':       ['v', 'a', 'c', 'd'],
        'recuperateurs.agrementrecuperateur': ['v', 'a', 'c', 'd'],
        'operations.operationrecuperation': ['v', 'a', 'c', 'd'],
        'bsd.bordereausuividechet':         ['v', 'a', 'c', 'd'],
        'declarations.declaration':         ['v', 'a', 'c', 'd'],
        'inspections.inspection':           ['v', 'a', 'c', 'd'],
        'operateurs.operateur':             ['v', 'a', 'c', 'd'],
        'administration.administrationenvironnement': ['v', 'a', 'c', 'd'],
        'nomenclature.nomenclature':        ['v', 'c'],
        'archive.document':                 ['v', 'a', 'c', 'd'],
        'ai_assistant.aiconversation':      ['v', 'a', 'c', 'd'],
        'ai_assistant.knowledgebase':      ['v', 'c'],
        'ai_assistant.airecommendation':    ['v', 'c'],
    },
    'administrateur': {
        'accounts.user':                    ['v'],
        'recuperateurs.recuperateur':       ['v', 'a', 'c', 'd'],
        'recuperateurs.agrementrecuperateur': ['v', 'a', 'c', 'd'],
        'operations.operationrecuperation': ['v', 'a', 'c', 'd'],
        'bsd.bordereausuividechet':         ['v', 'a', 'c', 'd'],
        'declarations.declaration':         ['v', 'a', 'c', 'd'],
        'inspections.inspection':           ['v', 'a', 'c', 'd'],
        'operateurs.operateur':             ['v', 'a', 'c', 'd'],
        'administration.administrationenvironnement': ['v', 'a', 'c', 'd'],
        'nomenclature.nomenclature':        ['v', 'c'],
        'archive.document':                 ['v', 'a', 'c', 'd'],
        'ai_assistant.aiconversation':      ['v', 'a', 'c'],
        'ai_assistant.knowledgebase':       ['v', 'c'],
        'ai_assistant.airecommendation':    ['v', 'c'],
    },
    'recuperateur': {
        'accounts.user':                    [],
        'recuperateurs.recuperateur':       ['v', 'c'],
        'recuperateurs.agrementrecuperateur': ['v'],
        'operations.operationrecuperation': ['v', 'a', 'c'],
        'bsd.bordereausuividechet':         ['v', 'a', 'c'],
        'declarations.declaration':         ['v', 'a', 'c'],
        'inspections.inspection':           ['v'],
        'operateurs.operateur':             ['v'],
        'administration.administrationenvironnement': ['v'],
        'nomenclature.nomenclature':        ['v'],
        'archive.document':                 ['v', 'a'],
        'ai_assistant.aiconversation':      ['v', 'a', 'c'],
        'ai_assistant.knowledgebase':       ['v'],
        'ai_assistant.airecommendation':    ['v'],
    },
    'responsable_collecte': {
        'accounts.user':                    [],
        'recuperateurs.recuperateur':       ['v', 'a', 'c'],
        'recuperateurs.agrementrecuperateur': ['v', 'a', 'c'],
        'operations.operationrecuperation': ['v', 'a', 'c'],
        'bsd.bordereausuividechet':         ['v', 'a', 'c'],
        'declarations.declaration':         ['v', 'a', 'c'],
        'inspections.inspection':           ['v', 'a', 'c'],
        'operateurs.operateur':             ['v', 'a', 'c'],
        'administration.administrationenvironnement': ['v'],
        'nomenclature.nomenclature':        ['v'],
        'archive.document':                 ['v', 'a', 'c'],
        'ai_assistant.aiconversation':      ['v'],
        'ai_assistant.knowledgebase':       ['v'],
        'ai_assistant.airecommendation':    ['v'],
    },
    'agent_collecte': {
        'accounts.user':                    [],
        'recuperateurs.recuperateur':       ['v'],
        'recuperateurs.agrementrecuperateur': ['v'],
        'operations.operationrecuperation': ['v', 'a'],
        'bsd.bordereausuividechet':         ['v', 'a'],
        'declarations.declaration':         ['v', 'a'],
        'inspections.inspection':           ['v'],
        'operateurs.operateur':             ['v'],
        'administration.administrationenvironnement': [],
        'nomenclature.nomenclature':        ['v'],
        'archive.document':                 ['v'],
        'ai_assistant.aiconversation':      ['v'],
        'ai_assistant.knowledgebase':       ['v'],
        'ai_assistant.airecommendation':    ['v'],
    },
    'responsable_decharge': {
        'accounts.user':                    [],
        'recuperateurs.recuperateur':       ['v'],
        'recuperateurs.agrementrecuperateur': ['v'],
        'operations.operationrecuperation': ['v'],
        'bsd.bordereausuividechet':         ['v', 'a', 'c'],
        'declarations.declaration':         ['v'],
        'inspections.inspection':           ['v'],
        'operateurs.operateur':             ['v'],
        'administration.administrationenvironnement': [],
        'nomenclature.nomenclature':        ['v'],
        'archive.document':                 ['v'],
        'ai_assistant.aiconversation':      ['v'],
        'ai_assistant.knowledgebase':       ['v'],
        'ai_assistant.airecommendation':    ['v'],
    },
    'observateur': {
        'accounts.user':                    [],
        'recuperateurs.recuperateur':       ['v'],
        'recuperateurs.agrementrecuperateur': ['v'],
        'operations.operationrecuperation': ['v'],
        'bsd.bordereausuividechet':         ['v'],
        'declarations.declaration':         ['v'],
        'inspections.inspection':           ['v'],
        'operateurs.operateur':             ['v'],
        'administration.administrationenvironnement': ['v'],
        'nomenclature.nomenclature':        ['v'],
        'archive.document':                 ['v'],
        'ai_assistant.aiconversation':      ['v'],
        'ai_assistant.knowledgebase':       [],
        'ai_assistant.airecommendation':    [],
    },
}

ACTION_MAP = {
    'v': 'view',
    'a': 'add',
    'c': 'change',
    'd': 'delete',
}


class Command(BaseCommand):
    help = 'Crée les groupes RBAC et attribue les permissions selon la matrice.'

    def handle(self, *args, **options):
        created_groups = 0
        created_perms = 0
        assigned_perms = 0

        for role_key, role_label in ROLES.items():
            group, created = Group.objects.get_or_create(name=role_key)
            if created:
                created_groups += 1
                self.stdout.write(self.style.SUCCESS(f'  + Groupe créé : {role_label}'))
            else:
                self.stdout.write(f'  = Groupe existant : {role_label}')

            group.permissions.clear()

            perms_for_role = PERM_MATRIX.get(role_key, {})
            for model_key, actions in perms_for_role.items():
                app_label, model_name = model_key.split('.')
                try:
                    ct = ContentType.objects.get(app_label=app_label, model=model_name)
                except ContentType.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f'    [!] ContentType {app_label}.{model_name} introuvable, ignore'
                    ))
                    continue

                for action_code in actions:
                    action_name = ACTION_MAP[action_code]
                    codename = f'{action_name}_{model_name}'
                    perm, created = Permission.objects.get_or_create(
                        codename=codename,
                        content_type=ct,
                        defaults={'name': f'{action_name} {model_name}'},
                    )
                    if created:
                        created_perms += 1
                    group.permissions.add(perm)
                    assigned_perms += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'RBAC configuré : {created_groups} groupes créés, '
            f'{created_perms} permissions créées, {assigned_perms} assignées'
        ))

        existing_users = __import__('django.contrib.auth', fromlist=['get_user_model']).get_user_model().objects.all()
        migrated = 0
        ROLE_MIGRATION_MAP = {
            'SUPERADMIN':   'super_administrateur',
            'ADMIN':        'administrateur',
            'INSPECTEUR':   'responsable_collecte',
            'RECUPERATEUR': 'recuperateur',
            'READONLY':     'observateur',
        }
        for user in existing_users:
            new_group_name = ROLE_MIGRATION_MAP.get(user.role)
            if new_group_name:
                group = Group.objects.get(name=new_group_name)
                if not user.groups.filter(name=new_group_name).exists():
                    user.groups.add(group)
                    migrated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Migration utilisateurs : {migrated} utilisateurs assignés à leurs groupes'
        ))
        self.stdout.write(self.style.SUCCESS('RBAC initialisé avec succès !'))
