"""Deterministic behavioural archetypes for Portfolio Pulse.

Clusters explain how accounts behave; they never set or modify health. ARR,
health, band, owner, segment, and industry are excluded from model fitting and
are attached only after clusters exist so commercial context cannot manufacture
the behavioural groups.
"""

from itertools import permutations
from math import sqrt
from statistics import median


FEATURES = (
    ("adoption_level", "Adoption level"),
    ("adoption_momentum", "Adoption momentum"),
    ("arr_momentum", "ARR momentum"),
    ("support_position", "Support position"),
    ("engagement_position", "Engagement position"),
)

ARCHETYPE_LIBRARY = {
    "Established Compounders": {
        "description": "ARR and adoption are advancing together from a comparatively strong base.",
        "score": lambda p: p["arr_momentum"] + p["adoption_momentum"] + 0.35 * p["adoption_level"],
    },
    "Under-Adopted Expansion": {
        "description": "Commercial growth is running ahead of product adoption and deserves explanation.",
        "score": lambda p: p["arr_momentum"] - p["adoption_level"] - max(p["adoption_momentum"], 0),
    },
    "Silent Erosion": {
        "description": "Commercial position is holding better than adoption, creating a quieter form of weakness.",
        "score": lambda p: p["arr_momentum"] - 1.5 * p["adoption_momentum"],
    },
    "Active Decliners": {
        "description": "ARR and adoption momentum are both materially weaker than portfolio peers.",
        "score": lambda p: -p["arr_momentum"] - p["adoption_momentum"],
    },
    "Operationally Strained": {
        "description": "Support and engagement conditions are weak relative to the rest of the portfolio.",
        "score": lambda p: -p["support_position"] - p["engagement_position"] - 0.25 * p["adoption_level"],
    },
    "Stable Core": {
        "description": "Current adoption and relationship conditions are comparatively sound with limited movement.",
        "score": lambda p: (
            p["adoption_level"] + 0.5 * p["support_position"] + 0.5 * p["engagement_position"]
            - 0.65 * abs(p["adoption_momentum"])
            - 0.35 * abs(p["arr_momentum"])
        ),
    },
}


def _distance(left, right):
    return sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def _mean_vector(vectors):
    return [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(len(vectors[0]))
    ]


def _fit_kmeans(vectors, cluster_count):
    """Deterministic farthest-point k-means suitable for a small upload."""
    centre = _mean_vector(vectors)
    first = min(range(len(vectors)), key=lambda index: (_distance(vectors[index], centre), index))
    centroids = [list(vectors[first])]
    while len(centroids) < cluster_count:
        candidate = max(
            range(len(vectors)),
            key=lambda index: (
                min(_distance(vectors[index], centroid) for centroid in centroids),
                -index,
            ),
        )
        centroids.append(list(vectors[candidate]))

    assignments = [-1] * len(vectors)
    for _ in range(60):
        new_assignments = [
            min(
                range(cluster_count),
                key=lambda cluster: (_distance(vector, centroids[cluster]), cluster),
            )
            for vector in vectors
        ]
        if new_assignments == assignments:
            break
        assignments = new_assignments
        for cluster in range(cluster_count):
            members = [
                vector for vector, assignment in zip(vectors, assignments)
                if assignment == cluster
            ]
            if members:
                centroids[cluster] = _mean_vector(members)
    return assignments, centroids


def _silhouette(vectors, assignments):
    clusters = sorted(set(assignments))
    if len(clusters) < 2:
        return -1.0
    values = []
    for index, vector in enumerate(vectors):
        own = assignments[index]
        peers = [
            other for other_index, other in enumerate(vectors)
            if assignments[other_index] == own and other_index != index
        ]
        if not peers:
            values.append(0.0)
            continue
        within = sum(_distance(vector, peer) for peer in peers) / len(peers)
        outside = []
        for cluster in clusters:
            if cluster == own:
                continue
            members = [
                other for other, assignment in zip(vectors, assignments)
                if assignment == cluster
            ]
            outside.append(sum(_distance(vector, member) for member in members) / len(members))
        nearest = min(outside)
        values.append((nearest - within) / max(within, nearest) if max(within, nearest) else 0.0)
    return sum(values) / len(values)


def _raw_features(account, rows):
    evidence = account.get("trajectory_evidence") or {}
    trends = evidence.get("trends") or {}

    def annual(key):
        trend = trends.get(key)
        return trend.get("annual_change") if trend else None

    adoption_values = [
        value for value in (
            account.get("seat_utilisation_pct"), account.get("active_user_pct"),
        ) if value is not None
    ]
    adoption_trends = [
        value for value in (annual("utilisation"), annual("active_users"))
        if value is not None
    ]
    recent_tickets = [
        row.get("tickets_opened") for row in rows[-3:]
        if row.get("tickets_opened") is not None
    ]
    ticket_level = sum(recent_tickets) / len(recent_tickets) if recent_tickets else None
    ticket_trend = annual("tickets")
    qbr_age = account.get("days_since_qbr")
    return {
        "adoption_level": sum(adoption_values) / len(adoption_values) if adoption_values else None,
        "adoption_momentum": sum(adoption_trends) / len(adoption_trends) if adoption_trends else None,
        "arr_momentum": annual("arr"),
        # Every displayed fingerprint uses the same direction: higher is stronger.
        "support_position": (
            -(ticket_level + max(ticket_trend or 0, 0) / 6)
            if ticket_level is not None else None
        ),
        "engagement_position": -min(qbr_age, 730) if qbr_age is not None else None,
    }


def _robust_vectors(feature_rows):
    scaled_columns = {}
    medians = {}
    for key, _ in FEATURES:
        observed = [row[key] for row in feature_rows if row[key] is not None]
        middle = median(observed) if observed else 0.0
        medians[key] = middle
        ordered = sorted(observed)
        if len(ordered) >= 4:
            lower = median(ordered[:len(ordered) // 2])
            upper = median(ordered[(len(ordered) + 1) // 2:])
            scale = upper - lower
        else:
            scale = 0.0
        if scale <= 0 and observed:
            scale = sqrt(sum((value - middle) ** 2 for value in observed) / len(observed))
        scale = scale or 1.0
        scaled_columns[key] = [
            max(-3.0, min(3.0, ((row[key] if row[key] is not None else middle) - middle) / scale))
            for row in feature_rows
        ]
    vectors = [
        [scaled_columns[key][index] for key, _ in FEATURES]
        for index in range(len(feature_rows))
    ]
    return vectors


def _choose_clusters(vectors):
    maximum = min(5, len(vectors) // 5)
    if maximum < 3:
        return None
    candidates = []
    for cluster_count in range(3, maximum + 1):
        assignments, centroids = _fit_kmeans(vectors, cluster_count)
        sizes = [assignments.count(cluster) for cluster in range(cluster_count)]
        if min(sizes) < 2:
            continue
        silhouette = _silhouette(vectors, assignments)
        # A small penalty prevents an extra cluster winning on negligible gain.
        selection_score = silhouette - 0.005 * (cluster_count - 3)
        candidates.append((selection_score, silhouette, assignments, centroids))
    return max(candidates, key=lambda item: item[0]) if candidates else None


def _name_clusters(profiles):
    stable_index = min(
        range(len(profiles)),
        key=lambda index: (
            abs(profiles[index]["arr_momentum"])
            + abs(profiles[index]["adoption_momentum"])
            + 0.25 * abs(profiles[index]["support_position"])
            + 0.25 * abs(profiles[index]["engagement_position"])
        ),
    )
    labels = [label for label in ARCHETYPE_LIBRARY if label != "Stable Core"]
    other_indexes = [index for index in range(len(profiles)) if index != stable_index]
    best = None
    for chosen in permutations(labels, len(other_indexes)):
        score = sum(
            ARCHETYPE_LIBRARY[label]["score"](profiles[index])
            for label, index in zip(chosen, other_indexes)
        )
        if best is None or score > best[0]:
            best = (score, chosen)
    names = [None] * len(profiles)
    names[stable_index] = "Stable Core"
    for index, label in zip(other_indexes, best[1]):
        names[index] = label
    return names


def build_account_archetypes(accounts, timeline_by_account):
    eligible = []
    for account in accounts:
        rows = timeline_by_account.get(account["account_id"], [])
        if len(rows) < 4 or not account.get("trajectory_evidence"):
            continue
        eligible.append((account, _raw_features(account, rows)))

    unavailable = {
        "available": False,
        "reason": "At least 15 accounts with four Timeline observations are required.",
        "eligible_count": len(eligible),
        "excluded_count": len(accounts) - len(eligible),
        "features": [{"key": key, "label": label} for key, label in FEATURES],
        "archetypes": [],
    }
    if len(eligible) < 15:
        return unavailable

    feature_rows = [row for _, row in eligible]
    vectors = _robust_vectors(feature_rows)
    selected = _choose_clusters(vectors)
    if not selected:
        unavailable["reason"] = "The portfolio does not contain enough stable behavioural separation."
        return unavailable

    _, silhouette, assignments, centroids = selected
    profile_keys = [key for key, _ in FEATURES]
    profiles = [
        {key: centroid[index] for index, key in enumerate(profile_keys)}
        for centroid in centroids
    ]
    names = _name_clusters(profiles)
    total_arr = sum(account.get("current_arr", 0.0) for account in accounts)
    rows = []
    for cluster, (name, profile) in enumerate(zip(names, profiles)):
        members = [
            account for (account, _), assignment in zip(eligible, assignments)
            if assignment == cluster
        ]
        cluster_arr = sum(account.get("current_arr", 0.0) for account in members)
        health_values = sorted(account["score"] for account in members)
        band_counts = {
            band: sum(1 for account in members if account["band"] == band)
            for band in ("Critical", "Watch", "Healthy")
        }
        rows.append({
            "id": f"archetype-{cluster + 1}",
            "name": name,
            "description": ARCHETYPE_LIBRARY[name]["description"],
            "count": len(members),
            "arr": round(cluster_arr, 2),
            "arr_share": round(cluster_arr / total_arr * 100, 1) if total_arr else 0.0,
            "median_health": round(median(health_values), 1),
            "bands": band_counts,
            "profile": [
                {"key": key, "label": label, "value": round(profile[key], 2)}
                for key, label in FEATURES
            ],
            "accounts": [
                {
                    "id": account["account_id"],
                    "name": account["account_name"],
                    "arr": round(account.get("current_arr", 0.0), 2),
                    "health": account["score"],
                    "band": account["band"],
                }
                for account in sorted(members, key=lambda item: item.get("current_arr", 0.0), reverse=True)
            ],
        })

    order = {name: index for index, name in enumerate(ARCHETYPE_LIBRARY)}
    rows.sort(key=lambda row: order[row["name"]])
    return {
        "available": True,
        "method": "Deterministic k-means on robust-scaled behavioural evidence",
        "cluster_count": len(rows),
        "silhouette": round(silhouette, 3),
        "eligible_count": len(eligible),
        "excluded_count": len(accounts) - len(eligible),
        "excluded_fields": ["ARR", "health score", "health band", "account name", "owner", "segment", "industry"],
        "features": [{"key": key, "label": label} for key, label in FEATURES],
        "archetypes": rows,
    }
