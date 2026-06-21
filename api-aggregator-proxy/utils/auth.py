def extract_team(user: str) -> str:
    try:
        parts = user.split(":")
        if len(parts) >= 4:
            sa_name = parts[-1]
            team_parts = sa_name.split("-")

            if len(team_parts) == 3:
                team_name = team_parts[1]
            elif len(team_parts) > 3:
                team_name = "-".join(team_parts[1:-1])
            else:
                team_name = "unknown"
        else:
            team_name = "unknown"

        return team_name

    except Exception as e:
        logger.error(f"Failed to extract team name from user '{user}': {e}")
        team_name = "unknown"