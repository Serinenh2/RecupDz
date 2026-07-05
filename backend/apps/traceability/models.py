from django.db import models
from django.conf import settings

class OperationCounter(models.Model):
    """Compteur séquentiel par année pour le numéro d'opération (Traceability.numero)."""
    year       = models.PositiveIntegerField(unique=True)
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Compteur d'opération"
        verbose_name_plural = "Compteurs d'opération"

    def __str__(self):
        return f"{self.year} → {self.last_value}"


class Traceability(models.Model):
    STATUT_CHOICES = [
        ('EN_COURS',   'En cours'),
        ('ENLEVEMENT', "En cours d'enlèvement"),
        ('TRANSPORT',  'En transport'),
        ('RECEPTION',  'Réceptionné'),
        ('TRAITEMENT', 'En traitement'),
        ('TERMINEE',   'Terminée'),
        ('ANNULEE',    'Annulée'),
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
        ('CET',          "Centre d'Enfouissement Technique"),
        ('MULTIPLE',     'Multi-destinations'),
    ]
    COULEUR_CHOICES = [
        ('TRANSPARENT', 'Transparent'),
        ('BLANC',       'Blanc'),
        ('NOIR',        'Noir'),
        ('BLEU',        'Bleu'),
        ('VERT',        'Vert'),
        ('ROUGE',       'Rouge'),
        ('JAUNE',       'Jaune'),
        ('GRIS',        'Gris'),
        ('MARRON',      'Marron'),
        ('MULTICOLORE', 'Multicolore'),
    ]
    PROPRETE_CHOICES = [
        ('TRES_PROPRE',         'Très propre'),
        ('PROPRE',              'Propre'),
        ('MOYENNEMENT_PROPRE',  'Moyennement propre'),
        ('SALE',                'Sale'),
        ('TRES_SALE',           'Très sale'),
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
    # Spécifique aux plastiques (ex: code 15.01.02) — caractérisation visuelle du déchet.
    couleur           = models.CharField(max_length=20, choices=COULEUR_CHOICES, blank=True)
    niveau_proprete   = models.CharField(max_length=25, choices=PROPRETE_CHOICES, blank=True, verbose_name='Niveau de propreté')

    # ── Transporteur ──────────────────────────────────────────────
    transporteur      = models.ForeignKey(
        'operateurs.Operateur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='traceability_transport',
        limit_choices_to={'type_operateur': 'TRANSPORTEUR'}
    )
    chauffeur         = models.CharField(max_length=200, blank=True)
    immatriculation   = models.CharField(max_length=100, blank=True)
    frais_transport_ttc = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Frais de transport TTC (DZD)'
    )
    autres_frais_ttc  = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Autres frais TTC (DZD)'
    )

    # ── Date de récupération ──────────────────────────────────────
    date_recuperation = models.DateField(verbose_name='Date de récupération')
    prix_unitaire_ttc = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Prix unitaire TTC (DZD)'
    )
    prix_achat_ttc    = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name="Prix d'achat total TTC (DZD)"
    )

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
    # Centre d'Enfouissement Technique
    cet               = models.ForeignKey(
        'operateurs.Operateur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='traceability_cet',
        limit_choices_to={'type_operateur': 'CET'}
    )
    quantite_enfouie  = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    # BSD requis si DSD
    bsd_numero        = models.CharField(max_length=100, blank=True, verbose_name='N° BSD (si DSD)')

    # ── Répartition multi-destinations ───────────────────────────
    # Chaque élément : {type, quantite, operateur (id|null), operateur_nom, notes}
    repartitions      = models.JSONField(default=list, blank=True)

    # ── Statut & suivi ────────────────────────────────────────────
    # Prix de revient global = prix d'achat total + frais de transport + autres frais
    prix_revient_global_ttc   = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Prix de revient global TTC (DZD)'
    )
    prix_revient_unitaire_ttc = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Prix de revient unitaire TTC (DZD)'
    )
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
            from datetime import date
            from django.db import transaction
            year = date.today().year
            with transaction.atomic():
                counter, _ = OperationCounter.objects.select_for_update().get_or_create(year=year)
                counter.last_value += 1
                counter.save(update_fields=['last_value'])
                self.numero = f"OP-{year}-{counter.last_value:04d}"
        super().save(*args, **kwargs)

    @property
    def necessite_bsd(self):
        return self.classe_dechet in ('S', 'SD') or self.destination_type == 'ELIMINATION'
