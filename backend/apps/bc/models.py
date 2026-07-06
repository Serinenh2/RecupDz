from django.db import models
from django.conf import settings


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
    numero         = models.CharField(max_length=30, unique=True, blank=True)
    recuperateur   = models.ForeignKey('recuperateurs.Recuperateur', on_delete=models.PROTECT,
                                        related_name='bons_commande')
    ref_client     = models.CharField(max_length=100, blank=True, verbose_name='Réf. client')
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
    pieces_liees   = models.CharField(max_length=200, blank=True, verbose_name='Pièces liées')
    mode_paiement       = models.CharField(max_length=100, blank=True, verbose_name='Mode de paiement')
    reference_paiement  = models.CharField(max_length=100, blank=True, verbose_name='Référence de paiement')

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

    def save(self, *args, **kwargs):
        if not self.numero:
            import uuid
            from datetime import date
            prefix = {'PROFORMA': 'PPR', 'FACTURE': 'FA'}.get(self.type_document, 'PBC')
            self.numero = f"{prefix}{date.today().strftime('%y')}{str(uuid.uuid4())[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.numero
