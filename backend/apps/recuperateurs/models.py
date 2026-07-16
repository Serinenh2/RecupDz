from django.db import models
from django.conf import settings
from .models_specialisation import (
    CategorieSpecialisation, SousCategorieSpecialisation, DetailSpecialisation,
)

class Recuperateur(models.Model):
    TYPE_CHOICES = [
        ('AVEC_AGREMENT', 'Avec agrément — Déchets Spéciaux / Dangereux'),
        ('SANS_AGREMENT', 'Sans agrément — Déchets ordinaires (MA/I)'),
        ('SANS_RC',       'Sans registre de commerce — Carte professionnelle'),
    ]
    STATUT_CHOICES = [
        ('ACTIF',       'Actif'),
        ('SUSPENDU',    'Suspendu'),
        ('EXPIRE',      'Expiré'),
        ('ARCHIVE',     'Archivé'),
        ('EN_ATTENTE',  'En attente de validation'),
    ]
    STATUT_JURIDIQUE = [
        ('EURL','EURL'),('SARL','SARL'),('SPA','SPA'),
        ('SNC','SNC'),('PHYSIQUE','Personne physique'),('AUTRE','Autre'),
    ]

    # ── Spécialisation — assignée UNIQUEMENT par le Super Admin via Django Admin ──
    # Le récupérateur la consulte en lecture seule sur son profil (API read-only).
    specialisation_details = models.ManyToManyField(
        DetailSpecialisation, blank=True, related_name='recuperateurs',
        verbose_name="Spécialisation (cochée par l'administrateur)",
        help_text="Cochez les types de déchets que ce récupérateur est autorisé à traiter."
    )

    numero_id          = models.CharField(max_length=30, unique=True, blank=True)
    user               = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                              null=True, blank=True, related_name='recuperateur')
    type_recuperateur  = models.CharField(max_length=20, choices=TYPE_CHOICES)
    statut_juridique   = models.CharField(max_length=15, choices=STATUT_JURIDIQUE, blank=True)

    logo               = models.ImageField(upload_to='recuperateurs/logos/', blank=True, null=True)
    signature_electronique = models.ImageField(upload_to='recuperateurs/signatures/', blank=True, null=True,
                                                 verbose_name='Signature électronique')
    cachet_electronique     = models.ImageField(upload_to='recuperateurs/cachets/', blank=True, null=True,
                                                 verbose_name='Cachet électronique')
    iso_9001           = models.ImageField(upload_to='recuperateurs/iso/', blank=True, null=True,
                                            verbose_name='Certification ISO 9001:2015')
    iso_14001          = models.ImageField(upload_to='recuperateurs/iso/', blank=True, null=True,
                                            verbose_name='Certification ISO 14001:2015')
    iso_45001          = models.ImageField(upload_to='recuperateurs/iso/', blank=True, null=True,
                                            verbose_name='Certification ISO 45001:2018')
    nom_raison_sociale = models.CharField(max_length=300)
    nom_commercial     = models.CharField(max_length=300, blank=True)
    responsable        = models.CharField(max_length=200)
    registre_commerce  = models.CharField(max_length=100, blank=True)
    nif                = models.CharField(max_length=50, blank=True)
    nis                = models.CharField(max_length=50, blank=True)
    numero_article     = models.CharField(max_length=50, blank=True, verbose_name="N° Article (NA)")
    num_carte_pro      = models.CharField(max_length=100, blank=True)

    adresse            = models.TextField(blank=True)
    wilaya             = models.CharField(max_length=3, blank=True)
    commune            = models.CharField(max_length=200, blank=True)
    code_postal        = models.CharField(max_length=10, blank=True)
    latitude           = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude          = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    telephone          = models.CharField(max_length=30, blank=True)
    fax                = models.CharField(max_length=30, blank=True)
    email              = models.EmailField(blank=True)
    site_web           = models.URLField(blank=True)
    compte_bancaire    = models.CharField(max_length=100, blank=True, verbose_name='Compte bancaire (RIB)')

    statut             = models.CharField(max_length=15, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_creation      = models.DateField(null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)
    notes              = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Récupérateur'

    def __str__(self):
        return f"{self.nom_raison_sociale} ({self.numero_id})"

    def save(self, *args, **kwargs):
        if not self.numero_id:
            import uuid
            self.numero_id = f"REC-{self.wilaya or 'XX'}-{str(uuid.uuid4())[:6].upper()}"
        super().save(*args, **kwargs)

    @property
    def agrement_actif(self):
        return self.agrements.filter(statut='ACTIF').first()


class AgrementRecuperateur(models.Model):
    TYPE_CHOICES = [
        ('AVEC_AGREMENT', 'Avec agrément'),
        ('SANS_AGREMENT', 'Sans agrément'),
        ('AUTRE',         'Autre'),
    ]
    ETENDUE_CHOICES = [
        ('NATIONALE', 'Nationale'),
        ('WILAYA',    'Par wilaya'),
        ('WILAYAS',   'Multi-wilayas'),
    ]
    STATUT_CHOICES = [
        ('ACTIF',    'Actif'),
        ('EXPIRE',   'Expiré'),
        ('SUSPENDU', 'Suspendu'),
        ('REVOQUE',  'Révoqué'),
    ]

    recuperateur       = models.ForeignKey(Recuperateur, on_delete=models.CASCADE,
                                           related_name='agrements')
    type_agrement      = models.CharField(max_length=20, choices=TYPE_CHOICES, default='AVEC_AGREMENT')
    numero_agrement    = models.CharField(max_length=100, blank=True)
    date_delivrance    = models.DateField(null=True, blank=True)
    duree_validite_ans = models.IntegerField(null=True, blank=True, verbose_name='Durée validité (années)')
    date_debut         = models.DateField(null=True, blank=True)
    date_fin           = models.DateField(null=True, blank=True)
    etendue_geo        = models.CharField(max_length=15, choices=ETENDUE_CHOICES, default='WILAYA')
    wilayas_couvertes  = models.TextField(blank=True, help_text='Codes wilaya séparés par virgule ex: 16,09,31')
    codes_dechets      = models.TextField(blank=True, help_text='Codes déchets autorisés séparés par virgule')
    statut             = models.CharField(max_length=15, choices=STATUT_CHOICES, default='ACTIF')
    autorite_delivrance= models.CharField(max_length=200, blank=True, verbose_name='Autorité de délivrance')
    observations       = models.TextField(blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_delivrance']
        verbose_name = 'Agrément'

    def __str__(self):
        return f"{self.numero_agrement or 'Sans N°'} — {self.recuperateur}"

    @property
    def est_valide(self):
        from datetime import date
        if self.statut != 'ACTIF': return False
        if self.date_fin and date.today() > self.date_fin: return False
        return True

    @property
    def jours_restants(self):
        from datetime import date
        if not self.date_fin: return None
        return (self.date_fin - date.today()).days

    @property
    def expire_bientot(self):
        j = self.jours_restants
        return j is not None and 0 <= j <= 60

    @property
    def codes_list(self):
        return [c.strip() for c in self.codes_dechets.split(',') if c.strip()] if self.codes_dechets else []

    @property
    def wilayas_list(self):
        return [w.strip() for w in self.wilayas_couvertes.split(',') if w.strip()] if self.wilayas_couvertes else []


class DocumentRecuperateur(models.Model):
    TYPE_DOC = [
        ('CARTE_PRO',    'Carte professionnelle'),
        ('AGREMENT',     'Agrément'),
        ('ASSURANCE',    'Assurance'),
        ('CONTRAT',      'Contrat'),
        ('AUTORISATION', 'Autorisation environnementale'),
        ('AUTRE',        'Autre'),
    ]
    recuperateur = models.ForeignKey(Recuperateur, on_delete=models.CASCADE, related_name='documents')
    type_doc     = models.CharField(max_length=20, choices=TYPE_DOC)
    nom_fichier  = models.CharField(max_length=200)
    fichier      = models.FileField(upload_to='recuperateurs/docs/')
    date_upload  = models.DateTimeField(auto_now_add=True)
    notes        = models.CharField(max_length=300, blank=True)