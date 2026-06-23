"""
Hiérarchie de spécialisation des récupérateurs — 3 niveaux :
CategorieSpecialisation > SousCategorieSpecialisation > DetailSpecialisation

Gestion entièrement via Django Admin (réservée au Super Admin / Admin système).
Le récupérateur ne fait que CONSULTER sa spécialisation assignée
(relation ManyToMany sur Recuperateur, champ specialisation_details).
"""
from django.db import models


class CategorieSpecialisation(models.Model):
    """Niveau 1 — ex: Déchets ménagers et assimilés"""
    nom    = models.CharField(max_length=200)
    icone  = models.CharField(max_length=10, blank=True, default='📦',
              help_text="Emoji affiché devant le nom, ex: 🏠 🧱 ⚠️")
    ordre  = models.PositiveSmallIntegerField(default=0,
              help_text="Ordre d'affichage (0 = premier)")

    class Meta:
        verbose_name = "Catégorie de spécialisation"
        verbose_name_plural = "1. Catégories de spécialisation"
        ordering = ['ordre', 'nom']

    def __str__(self):
        return f"{self.icone} {self.nom}"


class SousCategorieSpecialisation(models.Model):
    """Niveau 2 — ex: Déchets d'emballage"""
    categorie = models.ForeignKey(CategorieSpecialisation, on_delete=models.CASCADE,
                 related_name='sous_categories')
    nom       = models.CharField(max_length=200)
    ordre     = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Sous-catégorie de spécialisation"
        verbose_name_plural = "2. Sous-catégories de spécialisation"
        ordering = ['categorie__ordre', 'ordre', 'nom']

    def __str__(self):
        return f"{self.categorie.nom} → {self.nom}"


class DetailSpecialisation(models.Model):
    """Niveau 3 — ex: PET, PEHD, Huiles usagées... — c'est ce qui est cochable par récupérateur"""
    sous_categorie = models.ForeignKey(SousCategorieSpecialisation, on_delete=models.CASCADE,
                      related_name='details')
    nom            = models.CharField(max_length=200,
                      help_text="ex: Plastique — PET (bouteilles, bocaux)")
    ordre          = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Détail de spécialisation"
        verbose_name_plural = "3. Détails de spécialisation"
        ordering = ['sous_categorie__categorie__ordre', 'sous_categorie__ordre', 'ordre', 'nom']

    def __str__(self):
        return f"{self.sous_categorie.categorie.nom} → {self.sous_categorie.nom} → {self.nom}"
