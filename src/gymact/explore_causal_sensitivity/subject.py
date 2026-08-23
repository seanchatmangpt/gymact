import re
from dataclasses import dataclass

_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, order=True)
class Subject:
    owner: str
    repo: str
    sha: str

    @classmethod
    def parse(cls, value: str) -> "Subject":
        project, sep, sha = value.partition("@")
        if not sep or "/" not in project or not _SHA.fullmatch(sha):
            raise ValueError("subject must be owner/repo@40hex")
        owner, repo = project.split("/", 1)
        if not owner or not repo:
            raise ValueError("owner and repo are required")
        return cls(owner, repo, sha)

    def canonical(self) -> str:
        return f"{self.owner}/{self.repo}@{self.sha}"
