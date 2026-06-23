from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('SUPERADMIN',            'Super Administrateur'),
        ('ADMIN',                 'Administrateur'),
        ('RECUPERATEUR',          'Récupérateur'),
        ('RESPONSABLE_COLLECTE',  'Responsable Collecte'),
        ('AGENT_COLLECTE',        'Agent de Collecte'),
        ('RESPONSABLE_DECHARGE',  'Responsable Décharge'),
        ('OBSERVATEUR',           'Observateur'),
    ]

    ROLE_HIERARCHY = {
        'SUPERADMIN':            100,
        'ADMIN':                 80,
        'RECUPERATEUR':          60,
        'RESPONSABLE_COLLECTE':  60,
        'AGENT_COLLECTE':        40,
        'RESPONSABLE_DECHARGE':  40,
        'OBSERVATEUR':           10,
    }

    role       = models.CharField(max_length=25, choices=ROLE_CHOICES, default='OBSERVATEUR')
    phone      = models.CharField(max_length=20, blank=True)
    wilaya     = models.CharField(max_length=3, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def has_role(self, *role_names):
        return self.role in role_names

    def role_level(self):
        return self.ROLE_HIERARCHY.get(self.role, 0)

    def has_role_or_above(self, min_role):
        return self.role_level() >= self.ROLE_HIERARCHY.get(min_role, 0)

    def get_group_permissions_list(self):
        perms = set()
        for group in self.groups.all():
            for perm in group.permissions.all():
                perms.add(f"{perm.content_type.app_label}.{perm.codename}")
        return sorted(perms)

    def get_all_permissions_list(self):
        perms = set(self.get_group_permissions_list())
        for perm in self.user_permissions.all():
            perms.add(f"{perm.content_type.app_label}.{perm.codename}")
        return sorted(perms)


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE',      'Création'),
        ('UPDATE',      'Modification'),
        ('DELETE',      'Suppression'),
        ('ASSIGN_ROLE', 'Attribution de rôle'),
        ('LOGIN',       'Connexion'),
        ('LOGOUT',      'Déconnexion'),
    ]

    user         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action       = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name   = models.CharField(max_length=100, blank=True)
    object_id    = models.CharField(max_length=100, blank=True)
    details      = models.JSONField(default=dict, blank=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    timestamp    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Journal d\'audit'
        verbose_name_plural = 'Journaux d\'audit'

    def __str__(self):
        return f"[{self.timestamp}] {self.user} — {self.get_action_display()} — {self.model_name}"
