# CSS Capacity Monitor

Surveille uniquement la capacité de `VM.Standard.E2.1.Micro` dans `eu-paris-1`, AD-1.

- Interroge l'API OCI **CreateComputeCapacityReport**.
- Ne crée jamais d'instance, de VM ou de ressource payante.
- Ne teste aucune autre forme.
- Tableau de bord mobile via GitHub Pages.
- Contrôle planifié toutes les 5 minutes (GitHub peut retarder les tâches planifiées).

## A. Ajouter les secrets GitHub

Dans le dépôt : **Settings → Secrets and variables → Actions → New repository secret**.

Ajoute :

| Nom | Valeur |
|---|---|
| `OCI_TENANCY_OCID` | OCID de ta tenancy OCI |
| `OCI_USER_OCID` | OCID de ton utilisateur OCI |
| `OCI_FINGERPRINT` | Empreinte de la clé API |
| `OCI_PRIVATE_KEY` | Contenu complet de la clé privée PEM |
| `NTFY_TOPIC` | Facultatif : nom secret du sujet ntfy pour les alertes téléphone |

Ajoute aussi `OCI_PRIVATE_KEY_PASSPHRASE` seulement si ta clé privée est protégée par une phrase secrète.

Le script utilise le compartiment racine (`tenancy OCID`) comme le demande l'API Oracle. La région et la forme sont fixées dans le code : `eu-paris-1` et `VM.Standard.E2.1.Micro`.

**Ne mets jamais la clé privée, son empreinte ou les OCID dans un fichier du dépôt.** Les valeurs sensibles doivent être enregistrées uniquement dans GitHub Secrets.

## B. Autoriser l'appel API dans OCI

Dans OCI, l'utilisateur associé à la clé API doit appartenir à un groupe autorisé à lire les domaines de disponibilité et à créer des rapports de capacité.

Exemple de policy OCI (remplace `NomDuGroupeOCI` par le groupe réel de ton utilisateur) :

```text
Allow group NomDuGroupeOCI to inspect availability-domains in tenancy
Allow group NomDuGroupeOCI to manage compute-capacity-reports in tenancy
```

La seconde permission correspond à `COMPUTE_CAPACITY_REPORT_CREATE`. Elle ne donne pas le droit de créer des instances.

## C. Activer GitHub Pages

Dans **Settings → Pages → Build and deployment**, choisis **GitHub Actions** comme source.

## D. Démarrer

Dans **Actions → OCI capacity monitor → Run workflow**.

Le tableau de bord sera à :

`https://mamadou9214z.github.io/css-capacity-monitor/`

## E. Alerte sur téléphone (facultatif)

1. Installe l'application **ntfy** sur ton téléphone.
2. Choisis un sujet avec un nom long et imprévisible.
3. Abonne-toi à ce sujet dans l'application.
4. Ajoute ce même nom comme secret GitHub `NTFY_TOPIC`.

Le sujet ntfy.sh est public : son nom doit rester difficile à deviner. Ne le publie pas dans le dépôt. Une notification est envoyée lors du passage à `AVAILABLE`, pas à chaque contrôle.

## États

- `AVAILABLE` : Oracle indique de la capacité disponible dans au moins un fault domain.
- `UNAVAILABLE` : Oracle indique `OUT_OF_HOST_CAPACITY` dans tous les fault domains retournés.
- `CHECK_FAILED` : appel API, authentification ou configuration en échec. Ce n'est pas une preuve d'indisponibilité.

Un rapport de capacité est une photographie à l'instant du contrôle : il ne garantit pas que la capacité sera encore libre lorsque tu tenteras de créer la VM.

## Coût et limites

Le programme n'essaie jamais de lancer une VM et ne sélectionne aucune ressource payante. GitHub Actions sur un dépôt public utilise les runners standards gratuits selon les conditions et limites GitHub en vigueur. Les horaires cron peuvent être retardés : « toutes les 5 minutes » est une fréquence demandée, pas une garantie d'exécution à la minute près. Les services et règles de facturation Oracle restent soumis aux conditions de ton compte OCI.
