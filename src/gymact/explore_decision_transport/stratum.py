from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Stratum:
    methodology: str
    engine: str
    region: str
    evidence_root: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.methodology, self.engine, self.region, self.evidence_root)
