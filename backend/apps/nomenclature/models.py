from django.db import models

class Nomenclature(models.Model):
    CLASSE_CHOICES = [
        ('MA','Ménagers et Assimilés'),
        ('I', 'Inertes'),
        ('S', 'Spéciaux'),
        ('SD','Spéciaux Dangereux'),
    ]
    code          = models.CharField(max_length=20, unique=True)
    famille       = models.CharField(max_length=10, blank=True)  # ex: "01"
    sous_famille  = models.CharField(max_length=20, blank=True)  # ex: "01 01"
    designation_fr= models.TextField()
    designation_ar= models.TextField(blank=True)
    classe        = models.CharField(max_length=5, choices=CLASSE_CHOICES)
    dangerosite_fr= models.TextField(blank=True)
    dangerosite_ar= models.TextField(blank=True)
    annexe        = models.CharField(max_length=10, blank=True)  # II ou III
    # Réglementaire
    bsd_obligatoire     = models.BooleanField(default=False)
    agrement_requis     = models.BooleanField(default=False)
    conditions_stockage = models.TextField(blank=True)
    conditions_transport= models.TextField(blank=True)
    filieres_valorisation = models.TextField(blank=True)
    filieres_elimination  = models.TextField(blank=True)
    # Danger checkboxes
    explosible             = models.BooleanField(default=False)
    inflammable            = models.BooleanField(default=False)
    toxique                = models.BooleanField(default=False)
    cancerogene            = models.BooleanField(default=False)
    corrosive              = models.BooleanField(default=False)
    infectieuse            = models.BooleanField(default=False)
    dangereuse_environnement = models.BooleanField(default=False)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"[{self.code}] {self.designation_fr[:60]}"

    @property
    def couleur_danger(self):
        return {'MA':'green','I':'green','S':'orange','SD':'red'}.get(self.classe,'gray')


class DesignationDechet(models.Model):
    """
    Désignation précise d'un déchet — plusieurs par code Nomenclature.
    Ex: le code 15.01.02 (Emballages plastiques) a comme désignations possibles
    "Bouteille d'eau PET", "Flacon PEHD", "Big Bag PP", etc.
    Source : fichier nomenclature_dechets_emballage.xlsx fourni par le client.
    Champ français uniquement (le client a explicitement demandé d'ignorer l'arabe).
    """
    id_recup_dz = models.CharField(max_length=20, unique=True,
                   help_text="Identifiant interne — ex: PLA-001, BOIS-012")
    nomenclature = models.ForeignKey(Nomenclature, on_delete=models.CASCADE,
                    related_name='designations')
    designation  = models.CharField(max_length=300, help_text="ex: Bouteille d'eau PET")
    matiere      = models.CharField(max_length=100, blank=True, help_text="ex: PET, PEHD, BOIS, Acier")
    ordre        = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['nomenclature__code', 'ordre', 'designation']
        verbose_name = "Désignation de déchet"
        verbose_name_plural = "Désignations de déchets"

    def __str__(self):
        return f"[{self.id_recup_dz}] {self.designation} ({self.nomenclature.code})"
