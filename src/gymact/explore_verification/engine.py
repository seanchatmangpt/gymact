from .authority import require
from .receipt import make
from .standing import standing
from .vector import admit


def qualify(rows, subject_sha):
    require("CONSTRUCT")
    admitted = admit(rows, subject_sha)
    axes = {row.axis: row.outcome for row in admitted}
    result_standing = standing(axes.values())
    return {
        "standing": result_standing,
        "receipt": make(subject_sha, result_standing, axes),
        "actuation_performed": False,
    }
