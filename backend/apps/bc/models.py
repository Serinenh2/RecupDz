import uuid
from django.db import models, transaction
from django.conf import settings


class DocumentCounter(models.Model):
    """Compteur séquentiel par préfixe + année pour la numérotation
    automatique des documents (CM/PR/FA pour BonCommande, BL pour BonLivraison)."""
    prefix     = models.CharField(max_length=5)
    year       = models.PositiveIntegerField()
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('prefix', 'year')]
        verbose_name = 'Compteur de document'
        verbose_name_plural = 'Compteurs de document'

    def __str__(self):
        return f"{self.prefix}{self.year} → {self.last_value}"


def next_numero(prefix):
    """Retourne le prochain numéro séquentiel pour un préfixe donné,
    ex: next_numero('CM') -> 'CM20260007'."""
    from datetime import date
    year = date.today().year
    with transaction.atomic():
        counter, _ = DocumentCounter.objects.select_for_update().get_or_create(
            prefix=prefix, year=year)
        counter.last_value += 1
        counter.save(update_fields=['last_value'])
        return f"{prefix}{year}{counter.last_value:04d}"


class BonCommande(models.Model):
    """Bon de Commande (BC) — document commercial émis par le récupérateur
    listant les déchets avec prix unitaires, TVA et total TTC."""

    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('EMIS',      'Émis'),
        ('VALIDE',    'Validé'),
        ('ARCHIVE',   'Archivé'),
    ]
    TYPE_DOCUMENT_CHOICES = [
        ('BC',       'Bon de Commande'),
        ('PROFORMA', 'Proforma'),
        ('FACTURE',  'Facture'),
    ]

    type_document  = models.CharField(max_length=10, choices=TYPE_DOCUMENT_CHOICES, default='BC')
    numero         = models.CharField(max_length=30, unique=True, verbose_name='N° document',
                                       help_text="Saisi par l'utilisateur, ex: CM20260003 / PR20260003 / FA20260003")
    dossier_id     = models.UUIDField(default=uuid.uuid4, db_index=True,
                                       verbose_name='Dossier',
                                       help_text="Identifiant partagé par tous les documents d'une même opération "
                                                  "(Proforma → BC → BL → Facture) — hérité automatiquement lors "
                                                  "de la génération d'un document à partir d'un autre.")
    recuperateur   = models.ForeignKey('recuperateurs.Recuperateur', on_delete=models.PROTECT,
                                        related_name='bons_commande')
    ref_client     = models.CharField(max_length=100, blank=True, verbose_name='Réf. client')
    client_operateur = models.ForeignKey('operateurs.Operateur', null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name='bons_commande_clients',
                                          verbose_name='Client (fiche opérateur)')
    client_nom     = models.CharField(max_length=300, blank=True)
    client_adresse = models.CharField(max_length=500, blank=True)
    client_rc             = models.CharField(max_length=100, blank=True, verbose_name='N° RC client')
    client_nif             = models.CharField(max_length=100, blank=True, verbose_name='NIF client')
    client_numero_article  = models.CharField(max_length=100, blank=True, verbose_name='N° Article client')
    client_nis             = models.CharField(max_length=100, blank=True, verbose_name='N° I.S. client')
    client_telephone       = models.CharField(max_length=50, blank=True, verbose_name='Tél. client')
    client_fax             = models.CharField(max_length=50, blank=True, verbose_name='Fax client')
    client_email           = models.EmailField(blank=True, verbose_name='Email client')
    date_commande  = models.DateField()
    date_echeance  = models.DateField(null=True, blank=True, verbose_name='Échéance')
    validite_offre_jours = models.PositiveIntegerField(null=True, blank=True,
                                       verbose_name="Validité de l'offre (jours)",
                                       help_text="Proforma uniquement : durée de validité de l'offre, en jours.")
    pieces_liees   = models.CharField(max_length=200, blank=True, verbose_name='Pièces liées')
    mode_paiement       = models.CharField(max_length=100, blank=True, verbose_name='Mode de paiement')
    reference_paiement  = models.CharField(max_length=100, blank=True, verbose_name='Référence de paiement')

    proforma_origine      = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                               related_name='bc_generes', verbose_name='Proforma d\'origine')
    bon_livraison_origine = models.ForeignKey('bl.BonLivraison', null=True, blank=True, on_delete=models.SET_NULL,
                                               related_name='factures_generees', verbose_name='BL d\'origine')

    # Lignes : [{ref_article, description, quantite, unite, prix_unitaire, remise_pct, tva_pct}]
    lignes         = models.JSONField(default=list, blank=True)

    tva_pct        = models.DecimalField(max_digits=5, decimal_places=2, default=19)
    observations   = models.TextField(blank=True)
    statut         = models.CharField(max_length=15, choices=STATUT_CHOICES, default='BROUILLON')
    created_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ['-created_at']
        verbose_name = 'Bon de Commande'

    def __str__(self):
        return self.numero
