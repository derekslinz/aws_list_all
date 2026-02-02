from aliyunsdkcore.client import AcsClient

_CLIENTS = {}


def get_client(region, profile):
    key = (region, profile.get("access_key_id"), profile.get("name"))
    if key not in _CLIENTS:
        security_token = profile.get("security_token")
        try:
            if security_token:
                client = AcsClient(
                    profile["access_key_id"],
                    profile["access_key_secret"],
                    region,
                    security_token=security_token,
                )
            else:
                client = AcsClient(
                    profile["access_key_id"],
                    profile["access_key_secret"],
                    region,
                )
        except TypeError as exc:
            if "security_token" not in str(exc):
                raise
            client = AcsClient(
                profile["access_key_id"],
                profile["access_key_secret"],
                region,
            )
        # Work around aliyun sdk __del__ expecting session on Python 3.13.
        if not hasattr(client, "session"):
            client.session = None
        _CLIENTS[key] = client
    return _CLIENTS[key]
