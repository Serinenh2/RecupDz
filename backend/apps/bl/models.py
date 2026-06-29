from django.db import models
from django.conf import settings


class BonLivraison(models.Model):
    """Bon de Livraison — émis par le récupérateur à destination d'un
    éliminateur ou d'un valorisateur (jamais un générateur)."""

    DESTINATAIRE_CHOICES = [
        ('ELIMINATEUR',  'Éliminateur de déchets'),
        ('VALORISATEUR', 'Valorisateur de déchets'),
    ]
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('EMIS',      'Émis'),
        ('VALIDE',    'Validé'),
        ('ARCHIVE',   'Archivé'),
    ]
    QUALITE_CRITERES = ['chauffeur', 'sgt', 'maraicher', 'bacher', 'proprete']

    numero               = models.CharField(max_length=30, unique=True, blank=True)
    recuperateur         = models.ForeignKey('recuperateurs.Recuperateur', on_delete=models.PROTECT,
                                              related_name='bons_livraison')
    destinataire_type    = models.CharField(max_length=20, choices=DESTINATAIRE_CHOICES)
    destinataire         = models.ForeignKey('operateurs.Operateur', on_delete=models.PROTECT,
                                              related_name='bons_livraison_recus')

    date_livraison        = models.DateField()
    bon_commande_numero   = models.CharField(max_length=50, blank=True)
    date_commande         = models.DateField(null=True, blank=True)

    # Lignes : [{designation, reference, conditionnement, qte_box, qte_preforme}, ...]
    lignes               = models.JSONField(default=list, blank=True)

    etabli_par           = models.CharField(max_length=200, blank=True)
    # Qualité : {critere: 'OK' | 'NON'} pour chaque clé de QUALITE_CRITERES
    qualite              = models.JSONField(default=dict, blank=True)
    garantie_alimentaire = models.BooleanField(default=False)

    chauffeur_nom         = models.CharField(max_length=200, blank=True)
    camion_numero         = models.CharField(max_length=50, blank=True)
    camion_immatriculation= models.CharField(max_length=50, blank=True)

    statut               = models.CharField(max_length=15, choices=STATUT_CHOICES, default='BROUILLON')
    observations         = models.TextField(blank=True)
    created_by           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                              null=True, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ['-created_at']
        verbose_name = 'Bon de Livraison'

    def save(self, *args, **kwargs):
        if not self.numero:
            import uuid
            from datetime import date
            self.numero = f"PBL{date.today().strftime('%y')}{str(uuid.uuid4())[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.numero
