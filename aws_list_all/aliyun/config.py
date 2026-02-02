import json
import os

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.aliyun/config.json")


class AliyunConfigError(Exception):
    pass


def _get_first_key(data, keys):
    for key in keys:
        if key in data:
            return data[key]
    return None


def load_profile(profile_name=None, config_path=None):
    config_path = config_path or DEFAULT_CONFIG_PATH
    if not os.path.exists(config_path):
        raise AliyunConfigError("Aliyun config not found at {}".format(config_path))

    with open(config_path, "r") as infile:
        data = json.load(infile)

    profiles = data.get("profiles") or data.get("Profiles") or []
    if not isinstance(profiles, list) or not profiles:
        raise AliyunConfigError("No profiles found in {}".format(config_path))

    current = data.get("current") or data.get("Current")

    chosen = None
    if profile_name:
        for profile in profiles:
            if profile.get("name") == profile_name:
                chosen = profile
                break
        if chosen is None:
            raise AliyunConfigError("Profile '{}' not found in {}".format(profile_name, config_path))
    elif current:
        for profile in profiles:
            if profile.get("name") == current:
                chosen = profile
                break
    if chosen is None:
        for profile in profiles:
            if profile.get("name") == "default":
                chosen = profile
                break
    if chosen is None:
        chosen = profiles[0]

    access_key_id = _get_first_key(
        chosen,
        [
            "access_key_id",
            "accessKeyId",
            "accessKeyID",
            "access_key",
            "accessKey",
        ],
    )
    access_key_secret = _get_first_key(
        chosen,
        [
            "access_key_secret",
            "accessKeySecret",
            "secret",
        ],
    )
    security_token = _get_first_key(
        chosen,
        [
            "security_token",
            "securityToken",
            "sts_token",
            "stsToken",
        ],
    )

    if not access_key_id or not access_key_secret:
        raise AliyunConfigError("Profile '{}' missing access key id/secret".format(chosen.get("name")))

    return {
        "name": chosen.get("name"),
        "access_key_id": access_key_id,
        "access_key_secret": access_key_secret,
        "security_token": security_token,
        "region_id": chosen.get("region_id") or chosen.get("regionId"),
    }
