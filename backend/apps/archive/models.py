from django.db import models
from django.conf import settings
import os

class Document(models.Model):
    CATEGORIE_CHOICES = [
        ('AGREMENT',       'Agrement'),
        ('AUTORISATION',   'Autorisation environnementale'),
        ('CONTRAT',        'Contrat'),
        ('RAPPORT',        'Rapport'),
        ('DECLARATION',    'Declaration'),
        ('CORRESPONDANCE', 'Correspondance officielle'),
        ('JURIDIQUE',      'Document juridique'),
        ('TECHNIQUE',      'Document technique'),
        ('PROFORMA',       'Proforma'),
        ('BC',             'Bon de Commande'),
        ('BL',             'Bon de Livraison'),
        ('FACTURE',        'Facture'),
        ('AUTRE',          'Autre'),
    ]

    titre        = models.CharField(max_length=300)
    description  = models.TextField(blank=True)
    categorie    = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, default='AUTRE')
    fichier      = models.FileField(upload_to='archive/%Y/%m/')
    nom_original = models.CharField(max_length=300, blank=True)
    taille       = models.PositiveIntegerField(default=0)
    type_mime    = models.CharField(max_length=100, blank=True)
    tags         = models.CharField(max_length=500, blank=True)
    uploaded_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='documents_archives'
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.titre

    @property
    def extension(self):
        _, ext = os.path.splitext(self.nom_original or self.fichier.name)
        return ext.lower().lstrip('.')

    @property
    def taille_lisible(self):
        t = self.taille
        if t < 1024:    return f"{t} o"
        if t < 1048576: return f"{t/1024:.1f} Ko"
        return f"{t/1048576:.1f} Mo"