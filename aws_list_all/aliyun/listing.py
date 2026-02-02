import json


def _extract_path(data, path):
    current = data
    for part in path:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return []
    if current is None:
        return []
    if isinstance(current, dict):
        values = list(current.values())
        if len(values) == 1 and isinstance(values[0], list):
            return values[0]
    if isinstance(current, list):
        return current
    return [current]


class AliyunListing(object):
    def __init__(self, service, region, operation, response, profile, resource_type, result_path, resources=None):
        self.service = service
        self.region = region
        self.operation = operation
        self.response = response
        self.profile = profile
        self.resource_type = resource_type
        self.result_path = result_path
        self._resources = resources

    def to_json(self):
        resource_items = self.resources.get(self.resource_type, [])
        return {
            "service": self.service,
            "region": self.region,
            "profile": self.profile,
            "operation": self.operation,
            "resource_type": self.resource_type,
            "result_path": list(self.result_path),
            "response": self.response,
            "resources": resource_items,
        }

    @classmethod
    def from_json(cls, data):
        resources = data.get("resources")
        if isinstance(resources, dict):
            resource_type = data.get("resource_type")
            if resource_type in resources:
                resources = resources.get(resource_type)
        return cls(
            service=data.get("service"),
            region=data.get("region"),
            profile=data.get("profile"),
            operation=data.get("operation"),
            resource_type=data.get("resource_type"),
            result_path=tuple(data.get("result_path") or ()),
            response=data.get("response"),
            resources=resources,
        )

    @property
    def resources(self):
        if self._resources is not None:
            return {self.resource_type: self._resources}
        if self.response is None:
            return {self.resource_type: []}
        return {self.resource_type: _extract_path(self.response, self.result_path)}

    @property
    def resource_total_count(self):
        resources = self.resources.get(self.resource_type, [])
        return len(resources)

    def __str__(self):
        return json.dumps(self.to_json())
