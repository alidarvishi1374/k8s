def format_dashboard_output(namespaces):

    response = {
        "listMeta": {
            "totalItems": len(namespaces)
        },
        "namespaces": [],
        "errors": []
    }


    for ns in namespaces:

        response["namespaces"].append({

            "objectMeta": {

                "name": ns.metadata.name,

                "labels": ns.metadata.labels or {},

                "annotations":
                    ns.metadata.annotations or {},

                "uid":
                    ns.metadata.uid,

                "creationTimestamp":
                    ns.metadata.creation_timestamp.strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )

            },

            "typeMeta": {
                "kind": "namespace"
            },

            "phase":
                ns.status.phase

        })


    return response