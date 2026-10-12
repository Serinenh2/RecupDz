from django.db import models

class Operateur(models.Model):
    TYPE_CHOICES = [
        ('GENERATEUR',   'Générateur de déchets'),
        ('TRANSPORTEUR', 'Transporteur de déchets'),
        ('ELIMINATEUR',  'Éliminateur de déchets'),
        ('VALORISATEUR', 'Valorisateur de déchets'),
        ('CET',          "Centre d'Enfouissement Technique"),
        ('DIR_WILAYA',   "Direction de l'Environnement Wilaya"),
        ('MINISTERE',    "Ministère de l'Environnement"),
    ]
    STATUT_CHOICES = [
        ('ACTIF',    'Actif'),
        ('INACTIF',  'Inactif'),
        ('SUSPENDU', 'Suspendu'),
    ]

    # Opérateur privé d'un récupérateur (son propre carnet d'adresses) — vide
    # pour les opérateurs partagés/institutionnels créés par un administrateur
    # (ex: Direction de l'Environnement, Ministère), visibles par tout le monde.
    recuperateur            = models.ForeignKey(
        'recuperateurs.Recuperateur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='operateurs',
    )
    type_operateur          = models.CharField(max_length=20, choices=TYPE_CHOICES)
    raison_sociale          = models.CharField(max_length=300)
    nin                     = models.CharField(max_length=50, blank=True)
    nif                     = models.CharField(max_length=50, blank=True)
    nis                     = models.CharField(max_length=50, blank=True)
    registre_commerce       = models.CharField(max_length=100, blank=True)
    secteur_activite        = models.CharField(max_length=200, blank=True)
    wilaya                  = models.CharField(max_length=3, blank=True)
    commune                 = models.CharField(max_length=200, blank=True)
    adresse                 = models.TextField(blank=True)
    email                   = models.EmailField(blank=True)
    telephone               = models.CharField(max_length=30, blank=True)
    latitude                = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude               = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    # Agrément
    num_agrement            = models.CharField(max_length=100, blank=True)
    date_agrement           = models.DateField(null=True, blank=True)
    duree_agrement          = models.IntegerField(null=True, blank=True)
    date_debut_agrement     = models.DateField(null=True, blank=True)
    date_fin_agrement       = models.DateField(null=True, blank=True)
    # Transporteur
    type_engins             = models.CharField(max_length=200, blank=True)
    immatriculation         = models.CharField(max_length=100, blank=True)
    nom_conducteur          = models.CharField(max_length=200, blank=True)
    # Codes déchets autorisés
    codes_dechets_autorises = models.TextField(blank=True)
    # Convention (CET uniquement)
    convention_numero       = models.CharField(max_length=100, blank=True)
    convention_date         = models.DateField(null=True, blank=True)
    convention_duree        = models.IntegerField(null=True, blank=True, help_text="Durée en années")
    # Statut
    statut                  = models.CharField(max_length=15, choices=STATUT_CHOICES, default='ACTIF')
    notes                   = models.TextField(blank=True)
    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        ordering     = ['type_operateur', 'raison_sociale']
        verbose_name = 'Opérateur'

    def __str__(self):
        return f"{self.get_type_operateur_display()} — {self.raison_sociale}"

    @property
    def agrement_valide(self):
        from datetime import date
        if self.date_fin_agrement:
            return date.today() <= self.date_fin_agrement
        return bool(self.num_agrement)

    @property
    def codes_list(self):
        if not self.codes_dechets_autorises:
            return []
        return [c.strip() for c in self.codes_dechets_autorises.split(',') if c.strip()]

    @property
    def agrement_requis(self):
        if self.type_operateur == 'ELIMINATEUR':
            return True
        if self.type_operateur == 'TRANSPORTEUR':
            # Un transporteur n'a besoin d'un agrément que s'il est enregistré
            # pour des déchets spéciaux ou spéciaux dangereux (S/SD).
            codes = self.codes_list
            if not codes:
                return False
            from apps.nomenclature.models import Nomenclature
            return Nomenclature.objects.filter(code__in=codes, classe__in=['S', 'SD']).exists()
        return False

    @property
    def convention_date_fin(self):
        if self.convention_date and self.convention_duree:
            d = self.convention_date
            return d.replace(year=d.year + self.convention_duree)
        return None

    @property
    def convention_valide(self):
        from datetime import date
        fin = self.convention_date_fin
        if fin:
            return date.today() <= fin
        return bool(self.convention_numero)
