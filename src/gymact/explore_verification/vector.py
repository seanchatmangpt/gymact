from .evidence import Evidence


def admit(rows: list[Evidence], subject_sha: str):
    seen = {}
    out = []
    for row in rows:
        if row.subject.sha != subject_sha:
            raise ValueError("REFUSED_FOREIGN_SUBJECT")
        if row.axis in seen and seen[row.axis] != row.outcome:
            raise ValueError("REFUSED_CONTRADICTORY_AXIS")
        seen[row.axis] = row.outcome
        out.append(row)
    return tuple(sorted(out, key=lambda row: row.axis))
