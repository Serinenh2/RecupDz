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
    CLASSE_CHOICES = [
        ('MA', 'Ménagers et Assimilés'),
        ('I',  'Inertes'),
        ('S',  'Spéciaux'),
        ('SD', 'Spéciaux Dangereux'),
    ]
    sous_categorie = models.ForeignKey(SousCategorieSpecialisation, on_delete=models.CASCADE,
                      related_name='details')
    nom            = models.CharField(max_length=200,
                      help_text="ex: Plastique — PET (bouteilles, bocaux)")
    classe_nomenclature = models.CharField(
        max_length=5, choices=CLASSE_CHOICES, blank=True,
        help_text="Classe de nomenclature liée à ce détail. Quand ce détail est coché pour "
                   "un récupérateur, tous les codes de cette classe s'affichent dans sa page "
                   "Nomenclature. Laissez vide si ce détail ne doit filtrer aucun code."
    )
    ordre          = models.PositiveSmallIntegerField(default=0)

    # Codes de nomenclature correspondant à ce détail — cochés par le Super Admin.
    # C'est ce lien qui permet de filtrer la page Nomenclature côté récupérateur.
    codes_nomenclature = models.ManyToManyField(
        'nomenclature.Nomenclature', blank=True, related_name='details_specialisation',
        verbose_name="Codes de nomenclature liés",
        help_text="Cochez les codes déchets (nomenclature) correspondant à ce type."
    )

    class Meta:
        verbose_name = "Détail de spécialisation"
        verbose_name_plural = "3. Détails de spécialisation"
        ordering = ['sous_categorie__categorie__ordre', 'sous_categorie__ordre', 'ordre', 'nom']

    def __str__(self):
        return f"{self.sous_categorie.categorie.nom} → {self.sous_categorie.nom} → {self.nom}"
