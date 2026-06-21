def filter_namespaces(namespaces, team_name, label_key):
    return [
        ns for ns in namespaces
        if ns.metadata.labels
        and ns.metadata.labels.get(label_key) == team_name
    ]


def format_namespaces(ns_list):
    result = []

    for ns in ns_list:
        result.append({
            "metadata": {
                "name": ns.metadata.name,
                "creationTimestamp": (
                    ns.metadata.creation_timestamp.isoformat()
                    if ns.metadata.creation_timestamp else None
                )
            },
            "status": {
                "phase": ns.status.phase if ns.status else "Unknown"
            }
        })

    return result