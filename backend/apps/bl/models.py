import uuid
from django.db import models
from django.conf import settings


class BonLivraison(models.Model):
    """Bon de Livraison — émis par le récupérateur à destination d'un
    éliminateur, d'un valorisateur ou d'un Centre d'Enfouissement Technique (CET).
    Les CET n'acceptent pas les déchets spéciaux (S) ni les déchets spéciaux
    dangereux (SD/DSD) — uniquement les déchets ménagers et assimilés."""

    DESTINATAIRE_CHOICES = [
        ('ELIMINATEUR',  'Éliminateur de déchets'),
        ('VALORISATEUR', 'Valorisateur de déchets'),
        ('CET',          "Centre d'Enfouissement Technique"),
    ]
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('EMIS',      'Émis'),
        ('VALIDE',    'Validé'),
        ('ARCHIVE',   'Archivé'),
    ]
    MODE_LIVRAISON_CHOICES = [
        ('ENLEVEMENT', 'Enlèvement'),
        ('LIVRAISON',  'Livraison'),
    ]

    numero               = models.CharField(max_length=30, unique=True, verbose_name='N° document',
                                             help_text="Saisi par l'utilisateur, ex: BL20260003")
    dossier_id           = models.UUIDField(default=uuid.uuid4, db_index=True,
                                             verbose_name='Dossier',
                                             help_text="Identifiant partagé par tous les documents d'une même "
                                                        "opération (Proforma → BC → BL → Facture).")
    recuperateur         = models.ForeignKey('recuperateurs.Recuperateur', on_delete=models.PROTECT,
                                              related_name='bons_livraison')
    destinataire_type    = models.CharField(max_length=20, choices=DESTINATAIRE_CHOICES)
    destinataire         = models.ForeignKey('operateurs.Operateur', on_delete=models.PROTECT,
                                              related_name='bons_livraison_recus')

    ref_client             = models.CharField(max_length=100, blank=True, verbose_name='Réf. client')
    client_rc               = models.CharField(max_length=100, blank=True, verbose_name='N° RC client')
    client_nif               = models.CharField(max_length=100, blank=True, verbose_name='NIF client')
    client_numero_article    = models.CharField(max_length=100, blank=True, verbose_name='N° Article client')
    client_nis               = models.CharField(max_length=100, blank=True, verbose_name='N° I.S. client')
    client_telephone         = models.CharField(max_length=50, blank=True, verbose_name='Tél. client')
    client_fax               = models.CharField(max_length=50, blank=True, verbose_name='Fax client')
    client_email             = models.EmailField(blank=True, verbose_name='Email client')
    pieces_liees             = models.CharField(max_length=200, blank=True, verbose_name='Pièces liées')
    bon_commande_origine     = models.ForeignKey('bc.BonCommande', null=True, blank=True, on_delete=models.SET_NULL,
                                                   related_name='bl_generes', verbose_name='BC d\'origine')
    mode_livraison           = models.CharField(max_length=15, choices=MODE_LIVRAISON_CHOICES,
                                                 default='ENLEVEMENT', verbose_name='Mode de livraison')
    montant_reference        = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                                     verbose_name='Montant de référence (DZD)')

    date_livraison        = models.DateField()

    # Lignes : [{description, quantite, unite, stockage}, ...]
    lignes               = models.JSONField(default=list, blank=True)

    chauffeur_nom          = models.CharField(max_length=200, blank=True)
    camion_immatriculation = models.CharField(max_length=50, blank=True)

    statut               = models.CharField(max_length=15, choices=STATUT_CHOICES, default='BROUILLON')
    observations         = models.TextField(blank=True)
    created_by           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                              null=True, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ['-created_at']
        verbose_name = 'Bon de Livraison'

    def __str__(self):
        return self.numero
