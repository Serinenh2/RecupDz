from django.db import models
from django.conf import settings

class Traceability(models.Model):
    STATUT_CHOICES = [
        ('EN_COURS',  'En cours'),
        ('TERMINEE',  'Terminée'),
        ('ANNULEE',   'Annulée'),
    ]
    UNITE_CHOICES = [
        ('KG',    'Kilogramme (kg)'),
        ('TONNE', 'Tonne (t)'),
        ('M3',    'Mètre cube (m³)'),
        ('LITRE', 'Litre (L)'),
        ('UNITE', 'Unité'),
    ]
    DESTINATION_CHOICES = [
        ('VALORISATION', 'Valorisation'),
        ('ELIMINATION',  'Élimination (DSD)'),
        ('STOCKAGE',     'Stockage temporaire'),
        ('RECYCLAGE',    'Recyclage'),
    ]

    # ── Numéro de dossier ─────────────────────────────────────────
    numero           = models.CharField(max_length=30, unique=True, blank=True)

    # ── Récupérateur ──────────────────────────────────────────────
    recuperateur     = models.ForeignKey(
        'recuperateurs.Recuperateur', on_delete=models.PROTECT,
        related_name='traceability_records'
    )

    # ── Générateur (lié aux opérateurs enregistrés) ───────────────
    generateur       = models.ForeignKey(
        'operateurs.Operateur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='traceability_generateur',
        limit_choices_to={'type_operateur': 'GENERATEUR'}
    )
    # Bon de livraison / commande
    bon_livraison    = models.CharField(max_length=100, blank=True, verbose_name='Bon de livraison')
    date_livraison   = models.DateField(null=True, blank=True)
    bon_commande     = models.CharField(max_length=100, blank=True, verbose_name='Bon de commande n°')
    commande_client  = models.CharField(max_length=200, blank=True, verbose_name='Commande client')
    date_commande    = models.DateField(null=True, blank=True)

    # ── Déchet ────────────────────────────────────────────────────
    code_dechet       = models.CharField(max_length=20)
    designation_dechet= models.CharField(max_length=300)
    classe_dechet     = models.CharField(max_length=5, blank=True)
    unite             = models.CharField(max_length=10, choices=UNITE_CHOICES, default='KG')
    quantite          = models.DecimalField(max_digits=12, decimal_places=3)

    # ── Transporteur ──────────────────────────────────────────────
    transporteur      = models.ForeignKey(
        'operateurs.Operateur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='traceability_transport',
        limit_choices_to={'type_operateur': 'TRANSPORTEUR'}
    )
    chauffeur         = models.CharField(max_length=200, blank=True)
    immatriculation   = models.CharField(max_length=100, blank=True)

    # ── Date de récupération ──────────────────────────────────────
    date_recuperation = models.DateField(verbose_name='Date de récupération')

    # ── Destination ───────────────────────────────────────────────
    destination_type  = models.CharField(max_length=20, choices=DESTINATION_CHOICES, default='VALORISATION')

    # Valorisateur
    valorisateur      = models.ForeignKey(
        'operateurs.Operateur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='traceability_valorisation',
        limit_choices_to={'type_operateur': 'VALORISATEUR'}
    )

    # Éliminateur (DSD uniquement)
    eliminateur       = models.ForeignKey(
        'operateurs.Operateur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='traceability_elimination',
        limit_choices_to={'type_operateur': 'ELIMINATEUR'}
    )
    # BSD requis si DSD
    bsd_numero        = models.CharField(max_length=100, blank=True, verbose_name='N° BSD (si DSD)')

    # ── Statut & suivi ────────────────────────────────────────────
    statut            = models.CharField(max_length=15, choices=STATUT_CHOICES, default='EN_COURS')
    observations      = models.TextField(blank=True)
    created_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering     = ['-date_recuperation', '-created_at']
        verbose_name = 'Traçabilité'
        verbose_name_plural = 'Traçabilités'

    def __str__(self):
        return f"{self.numero} — {self.recuperateur}"

    def save(self, *args, **kwargs):
        if not self.numero:
            import uuid
            from datetime import date
            self.numero = f"TR-{date.today().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
        super().save(*args, **kwargs)

    @property
    def necessite_bsd(self):
        return self.classe_dechet in ('S', 'SD') or self.destination_type == 'ELIMINATION'
