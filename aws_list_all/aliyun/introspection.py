from . import SUPPORTED_REGIONS
from .operations import get_operations, get_services, get_service_spec


def get_regions_for_service(service, requested_regions=(), default_region=None):
    spec = get_service_spec(service)
    if spec is None:
        return []
    if spec.regional:
        regions = SUPPORTED_REGIONS
        if requested_regions:
            regions = [r for r in regions if r in requested_regions]
        return regions
    if default_region is None:
        if requested_regions:
            return [requested_regions[0]]
        return [SUPPORTED_REGIONS[0]]
    return [default_region]
