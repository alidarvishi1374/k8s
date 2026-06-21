from flask import Blueprint, jsonify

bp = Blueprint("discovery", __name__)

@bp.route("/apis/custom.api.local/v1")
def api_root():
    return jsonify({
        "kind": "APIResourceList",
        "apiVersion": "v1",
        "groupVersion": "custom.api.local/v1",
        "resources": [
            {"name": "whoami", "namespaced": False, "kind": "WhoAmI", "verbs": ["get"]},
            {"name": "mynamespace", "namespaced": False, "kind": "MyNamespaceList", "verbs": ["get"]}
        ]
    })