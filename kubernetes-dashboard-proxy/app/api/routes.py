from flask import Blueprint, request, jsonify

from app.services.auth import (
    decode_jwt,
    extract_team_from_sa
)

from app.services.namespace import (
    get_team_namespaces
)

from app.utils.formatter import (
    format_dashboard_output
)



api = Blueprint(
    "api",
    __name__
)



@api.route("/", methods=["GET"])
def namespaces():


    auth = request.headers.get(
        "Authorization"
    )


    if not auth:

        return jsonify(
            {
                "error":"No token found"
            }
        ),401


    token = auth.replace(
        "Bearer ",
        ""
    )


    try:

        payload = decode_jwt(token)


    except Exception as e:

        return jsonify(
            {
                "error":str(e)
            }
        ),400



    sa = payload.get(
        "kubernetes.io/serviceaccount/service-account.name"
    )


    if not sa:

        return jsonify(
            {
                "error":
                "ServiceAccount missing"
            }
        ),400



    team = extract_team_from_sa(sa)


    namespaces = get_team_namespaces(team)


    return jsonify(
        format_dashboard_output(namespaces)
    )




@api.route("/healthz")
def health():
    
    return "ok",200