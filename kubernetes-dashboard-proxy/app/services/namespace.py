from app.kubernetes.client import v1



def get_team_namespaces(team):
    """Return all namespaces that have label team=<team_name>."""
    try:

        result = v1.list_namespace(
            label_selector=f"team={team}"
        )

        return result.items


    except Exception as e:

        print(f"[ERROR] Fetching namespaces for team {team_name}: {e}")

        return []