from __future__ import annotations

from gymact.models import Capability, Consequence

CLOUDS = ("aws", "azure", "gcp")

CLOUDSIM_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        iri="urn:gymact:cloudsim:aws:capability:apply",
        title="aws.cloudsim.apply",
        consequence=Consequence.DO,
        binding="aws_cloudsim_apply",
    ),
    Capability(
        iri="urn:gymact:cloudsim:azure:capability:apply",
        title="azure.cloudsim.apply",
        consequence=Consequence.DO,
        binding="azure_cloudsim_apply",
    ),
    Capability(
        iri="urn:gymact:cloudsim:gcp:capability:apply",
        title="gcp.cloudsim.apply",
        consequence=Consequence.DO,
        binding="gcp_cloudsim_apply",
    ),
    Capability(
        iri="urn:gymact:cloudsim:capability:advance-clock",
        title="cloudsim.advance_clock",
        consequence=Consequence.DO,
        binding="cloudsim_advance_clock",
    ),
)

CAPABILITY_BY_BINDING = {item.binding: item for item in CLOUDSIM_CAPABILITIES}
CLOUD_BY_BINDING = {
    "aws_cloudsim_apply": "aws",
    "azure_cloudsim_apply": "azure",
    "gcp_cloudsim_apply": "gcp",
}

assert len(CAPABILITY_BY_BINDING) == len(CLOUDSIM_CAPABILITIES)
