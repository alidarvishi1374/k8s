from kubernetes import client

def can_list_namespaces(auth_v1, user: str) -> bool:
    sar = client.V1SubjectAccessReview(
        spec=client.V1SubjectAccessReviewSpec(
            user=user,
            resource_attributes=client.V1ResourceAttributes(
                verb="list",
                resource="namespaces",
                group=""
            )
        )
    )

    resp = auth_v1.create_subject_access_review(body=sar)
    return resp.status.allowed