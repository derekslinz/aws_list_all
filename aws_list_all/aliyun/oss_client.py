import oss2


def _get_auth(profile):
    access_key_id = profile["access_key_id"]
    access_key_secret = profile["access_key_secret"]
    security_token = profile.get("security_token")
    if security_token:
        return oss2.StsAuth(access_key_id, access_key_secret, security_token)
    return oss2.Auth(access_key_id, access_key_secret)


def get_oss_bucket_client(profile, endpoint, bucket_name):
    auth = _get_auth(profile)
    return oss2.Bucket(auth, endpoint, bucket_name)


def get_oss_service_client(profile, endpoint):
    auth = _get_auth(profile)
    return oss2.Service(auth, endpoint)
