import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import oci
import requests

REGION = "eu-paris-1"
SHAPE = "VM.Standard.E2.1.Micro"
STATE_FILE = Path(".cache/previous.json")
OUTPUT_FILE = Path("site/status.json")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_previous():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def write_status(state, details, ad_name=None):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state,
        "shape": SHAPE,
        "region": REGION,
        "availability_domain": ad_name or "AD-1",
        "checked_at_utc": now_iso(),
        "details": details,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def notify_available(topic):
    if not topic:
        print("NTFY_TOPIC absent : notification téléphone désactivée.")
        return
    # Le sujet reste dans un en-tête HTTP, jamais dans les logs ou le dépôt.
    response = requests.post(
        "https://ntfy.sh/",
        headers={
            "Topic": topic,
            "Title": "Capacité OCI disponible",
            "Priority": "urgent",
            "Tags": "white_check_mark,cloud",
        },
        data=f"Oracle indique de la capacité pour {SHAPE} dans {REGION}, AD-1. Vérifie immédiatement dans OCI : la capacité peut changer.".encode("utf-8"),
        timeout=20,
    )
    response.raise_for_status()
    print("Notification ntfy envoyée.")


def main():
    required = [
        "OCI_TENANCY_OCID",
        "OCI_USER_OCID",
        "OCI_FINGERPRINT",
        "OCI_PRIVATE_KEY",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        payload = write_status("CHECK_FAILED", "Secrets GitHub manquants : " + ", ".join(missing))
        print(json.dumps(payload, ensure_ascii=False))
        return 1

    tenancy = os.environ["OCI_TENANCY_OCID"]
    config = {
        "user": os.environ["OCI_USER_OCID"],
        "tenancy": tenancy,
        "fingerprint": os.environ["OCI_FINGERPRINT"],
        "region": REGION,
    }
    passphrase = os.getenv("OCI_PRIVATE_KEY_PASSPHRASE") or None
    signer = oci.signer.Signer(
        tenancy=tenancy,
        user=config["user"],
        fingerprint=config["fingerprint"],
        private_key_content=os.environ["OCI_PRIVATE_KEY"],
        pass_phrase=passphrase,
    )

    identity = oci.identity.IdentityClient(config=config, signer=signer)
    compute = oci.core.ComputeClient(config=config, signer=signer)

    # Le nom complet de l'AD OCI contient un préfixe propre à la tenancy/région.
    ads = identity.list_availability_domains(compartment_id=tenancy).data
    matching_ads = [ad for ad in ads if ad.name.upper().endswith("-AD-1")]
    if len(matching_ads) != 1:
        raise RuntimeError(
            f"Impossible d'identifier de façon unique AD-1 dans {REGION}; "
            f"domaines reçus : {[ad.name for ad in ads]}"
        )
    ad = matching_ads[0]

    request = oci.core.models.CreateComputeCapacityReportDetails(
        compartment_id=tenancy,
        availability_domain=ad.name,
        # Sans fault_domain : Oracle renvoie les résultats pour tous les FDs.
        shape_availabilities=[
            oci.core.models.CreateCapacityReportShapeAvailabilityDetails(
                instance_shape=SHAPE
            )
        ],
    )
    report = compute.create_compute_capacity_report(
        create_compute_capacity_report_details=request
    ).data

    rows = report.shape_availabilities or []
    statuses = []
    row_details = []
    for row in rows:
        status = str(row.availability_status or "").upper()
        statuses.append(status)
        row_details.append({
            "fault_domain": row.fault_domain,
            "availability_status": status or "UNKNOWN",
            "available_count": row.available_count,
        })

    if not rows:
        state = "CHECK_FAILED"
        details = "Oracle a répondu sans résultat de capacité pour la forme demandée."
    elif "AVAILABLE" in statuses:
        state = "AVAILABLE"
        details = {"message": "Capacité annoncée par Oracle dans au moins un fault domain.", "fault_domains": row_details}
    elif all(s == "OUT_OF_HOST_CAPACITY" for s in statuses):
        state = "UNAVAILABLE"
        details = {"message": "OUT_OF_HOST_CAPACITY dans tous les fault domains retournés.", "fault_domains": row_details}
    else:
        state = "CHECK_FAILED"
        details = {"message": "Réponse Oracle non reconnue ou ambiguë ; aucune alerte positive envoyée.", "fault_domains": row_details}

    previous = load_previous()
    payload = write_status(state, details, ad.name)
    print(json.dumps(payload, ensure_ascii=False))

    # N'envoie l'alerte qu'au front montant vers AVAILABLE.
    if state == "AVAILABLE" and previous.get("state") != "AVAILABLE":
        notify_available(os.getenv("NTFY_TOPIC", "").strip())

    # Ne remplace l'état mémorisé qu'après une réponse API exploitable.
    if state in ("AVAILABLE", "UNAVAILABLE"):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({"state": state, "checked_at_utc": now_iso()}), encoding="utf-8")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        payload = write_status("CHECK_FAILED", f"{type(exc).__name__}: {exc}")
        print(json.dumps(payload, ensure_ascii=False))
        sys.exit(1)
