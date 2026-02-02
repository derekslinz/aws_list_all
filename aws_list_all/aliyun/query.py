from __future__ import print_function

import json
import sys
import contextlib
from collections import defaultdict
from datetime import datetime, timedelta
from functools import partial
from multiprocessing.pool import ThreadPool
from random import shuffle
from time import time
from traceback import print_exc

from aliyunsdkcore.request import CommonRequest

from dataclasses import replace

from .client import get_client
from .config import load_profile
from .introspection import get_regions_for_service
from .listing import AliyunListing
from .operations import get_operations, get_service_spec
from .oss_client import get_oss_service_client

RESULT_NOTHING = '---'
RESULT_SOMETHING = '+++'
RESULT_ERROR = '!!!'
RESULT_NO_ACCESS = '>:|'

ACCESS_DENIED_STRINGS = [
    'Forbidden',
    'Unauthorized',
    'InvalidAccessKeyId.NotFound',
    'SignatureDoesNotMatch',
    'MissingAccessKeyId',
]

NOT_AVAILABLE_STRINGS = [
    'InvalidRegionId.NotFound',
    'InvalidRegionId',
    'This product is not available',
    'NameResolutionError',
    'Failed to resolve',
]


def _build_request(operation, endpoint, region, parameters):
    request = CommonRequest()
    request.set_accept_format('json')
    request.set_domain(endpoint)
    request.set_version(operation.version)
    request.set_action_name(operation.action)
    request.set_method(operation.method)
    if region:
        request.add_query_param('RegionId', region)
    for key, value in (parameters or {}).items():
        request.add_query_param(key, value)
    return request


def _resolve_parameters(params):
    if not params:
        return {}
    now = datetime.utcnow()
    today = now.date()
    defaults = {
        "__DEFAULT_START_DATE__": (today - timedelta(days=30)).isoformat(),
        "__DEFAULT_END_DATE__": today.isoformat(),
        "__DEFAULT_START_TIME__": (now - timedelta(days=30)).isoformat(timespec="seconds") + "Z",
        "__DEFAULT_END_TIME__": now.isoformat(timespec="seconds") + "Z",
    }
    resolved = {}
    for key, value in params.items():
        if isinstance(value, str) and value in defaults:
            resolved[key] = defaults[value]
        else:
            resolved[key] = value
    return resolved


def _extract_items(response, result_path):
    current = response
    for part in result_path:
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


def _execute_operation(client, operation, endpoint, region):
    items = []
    base_params = _resolve_parameters(operation.parameters)

    if operation.pagination == "none":
        request = _build_request(operation, endpoint, region, base_params)
        response = json.loads(client.do_action_with_exception(request).decode('utf-8'))
        return response, _extract_items(response, operation.result_path)

    if operation.pagination == "marker":
        marker = None
        while True:
            params = dict(base_params)
            params['MaxItems'] = operation.page_size
            if marker:
                params['Marker'] = marker
            request = _build_request(operation, endpoint, region, params)
            response = json.loads(client.do_action_with_exception(request).decode('utf-8'))
            items.extend(_extract_items(response, operation.result_path))
            if not response.get('IsTruncated'):
                return response, items
            marker = response.get('Marker') or response.get('NextMarker')
            if not marker:
                return response, items

    if operation.pagination == "token":
        next_token = None
        while True:
            params = dict(base_params)
            params[operation.limit_param] = operation.page_size
            if next_token:
                params[operation.token_param] = next_token
            request = _build_request(operation, endpoint, region, params)
            response = json.loads(client.do_action_with_exception(request).decode('utf-8'))
            items.extend(_extract_items(response, operation.result_path))
            next_token = response.get(operation.token_param)
            if not next_token:
                return response, items

    page_number = 1
    while True:
        params = dict(base_params)
        params[operation.page_size_param] = operation.page_size
        params[operation.page_number_param] = page_number
        request = _build_request(operation, endpoint, region, params)
        response = json.loads(client.do_action_with_exception(request).decode('utf-8'))
        items.extend(_extract_items(response, operation.result_path))
        total_count = response.get('TotalCount')
        if total_count is None:
            return response, items
        if page_number * operation.page_size >= int(total_count):
            return response, items
        page_number += 1


def _execute_oss_operation(profile, operation, endpoint):
    service_client = get_oss_service_client(profile, endpoint)
    if operation.name == "ListBuckets":
        resp = service_client.list_buckets()
        buckets = []
        for bucket in resp.buckets or []:
            buckets.append({
                "Name": bucket.name,
                "Location": bucket.location,
                "CreationDate": bucket.creation_date,
                "StorageClass": bucket.storage_class,
                "ExtranetEndpoint": bucket.extranet_endpoint,
                "IntranetEndpoint": bucket.intranet_endpoint,
            })
        return {
            "Buckets": buckets,
        }, buckets
    return {}, []


def do_query(services, selected_regions=(), selected_operations=(), verbose=0, parallel=16, profile_name=None):
    profile = load_profile(profile_name=profile_name)
    to_run = []
    iterated_ops = []
    print('Building set of queries to execute...')
    for service in services:
        spec = get_service_spec(service)
        if spec is None:
            continue
        regions = get_regions_for_service(service, selected_regions, default_region=profile.get('region_id'))
        for region in regions:
            for operation in get_operations(service):
                if selected_operations and operation.name not in selected_operations:
                    continue
                region_label = region if spec.regional else 'global'
                if verbose > 0:
                    print('Service: {: <10} | Region: {:<12} | Operation: {}'.format(service, region_label, operation.name))
                if operation.iterate_from:
                    iterated_ops.append([service, region, operation, profile, spec, region_label])
                else:
                    to_run.append([service, region, operation, profile, spec, region_label])

    shuffle(to_run)
    results_by_type = defaultdict(list)
    listings_by_key = {}
    print('...done. Executing queries...')
    with contextlib.closing(ThreadPool(parallel)) as pool:
        for result in pool.imap_unordered(partial(acquire_listing, verbose), to_run):
            results_by_type[result["result"][0]].append(result["result"])
            if result["listing"] is not None:
                key = (result["service"], result["region_label"], result["operation_name"])
                listings_by_key[key] = result["listing"]
            if verbose > 1:
                print('ExecutedQueryResult: {}'.format(result))
            else:
                print(result["result"][0][-1], end='')
                sys.stdout.flush()
    print('...done')
    for result_type in (RESULT_NOTHING, RESULT_SOMETHING, RESULT_NO_ACCESS, RESULT_ERROR):
        for result in sorted(results_by_type[result_type]):
            print(*result)

    if iterated_ops:
        to_run = []
        for service, region, operation, profile, spec, region_label in iterated_ops:
            key = (service, region_label, operation.iterate_from)
            listing = listings_by_key.get(key)
            if listing is None:
                continue
            resources = listing.resources
            items = []
            for resource_items in resources.values():
                items.extend(resource_items)
            iterate_values = []
            if operation.iterate_params:
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    param_values = {}
                    missing = False
                    for param_key, field_key in operation.iterate_params.items():
                        if field_key not in item:
                            missing = True
                            break
                        param_values[param_key] = item.get(field_key)
                    if not missing:
                        iterate_values.append(param_values)
            elif operation.iterate_field and operation.iterate_param:
                for item in items:
                    if isinstance(item, dict) and operation.iterate_field in item:
                        value = item.get(operation.iterate_field)
                        if value:
                            iterate_values.append({operation.iterate_param: value})
            if not iterate_values:
                continue
            deduped = []
            seen = set()
            for params in iterate_values:
                key = tuple(sorted(params.items()))
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(params)
            to_run.append([service, region, operation, profile, spec, region_label, deduped])
        if not to_run:
            return
        shuffle(to_run)
        results_by_type = defaultdict(list)
        print('Executing dependent queries...')
        with contextlib.closing(ThreadPool(parallel)) as pool:
            for result in pool.imap_unordered(partial(acquire_listing, verbose), to_run):
                results_by_type[result["result"][0]].append(result["result"])
                if verbose > 1:
                    print('ExecutedQueryResult: {}'.format(result))
                else:
                    print(result["result"][0][-1], end='')
                    sys.stdout.flush()
        print('...done')
        for result_type in (RESULT_NOTHING, RESULT_SOMETHING, RESULT_NO_ACCESS, RESULT_ERROR):
            for result in sorted(results_by_type[result_type]):
                print(*result)


def acquire_listing(verbose, what):
    service, region, operation, profile, spec, region_label = what[:6]
    iterate_values = what[6] if len(what) > 6 else None
    start_time = time()
    endpoint = spec.endpoint_template.format(region=region)
    try:
        if verbose > 1:
            print(what, 'starting request...')
        if service == "oss":
            response, items = _execute_oss_operation(profile, operation, endpoint)
        else:
            client_region = region or profile.get('region_id')
            client = get_client(client_region, profile)
            request_region = region if spec.regional else None
            if iterate_values:
                items = []
                response = None
                for params_override in iterate_values:
                    params = _resolve_parameters(operation.parameters)
                    params.update(params_override)
                    op_with_params = replace(operation, parameters=params)
                    response, new_items = _execute_operation(client, op_with_params, endpoint, request_region)
                    items.extend(new_items)
            else:
                response, items = _execute_operation(client, operation, endpoint, request_region)
        duration = time() - start_time
        if verbose > 1:
            print(what, '...request successful')
            print("timing [success]:", duration, what)
        listing = AliyunListing(
            service=service,
            region=region_label,
            operation=operation.name,
            response=response,
            profile=profile.get('name'),
            resource_type=operation.resource_type,
            result_path=operation.result_path,
            resources=items,
        )
        if listing.resource_total_count > 0:
            filename = '{}_{}_{}_{}.json'.format(service, operation.name, region_label, profile.get('name'))
            with open(filename, 'w') as jsonfile:
                json.dump(listing.to_json(), jsonfile, default=datetime.isoformat)
            result = (RESULT_SOMETHING, service, region_label, operation.name, profile.get('name'), operation.resource_type)
        else:
            result = (RESULT_NOTHING, service, region_label, operation.name, profile.get('name'), operation.resource_type)
        return {
            "result": result,
            "listing": listing,
            "service": service,
            "region_label": region_label,
            "operation_name": operation.name,
        }
    except Exception as exc:  # pylint:disable=broad-except
        duration = time() - start_time
        if verbose > 1:
            print(what, '...exception:', exc)
            print("timing [failure]:", duration, what)
        if verbose > 2:
            print_exc()
        message = str(exc)
        normalized_message = message.strip()
        exc_type = exc.__class__.__name__
        exc_repr = repr(exc)
        result_type = RESULT_NO_ACCESS if any(err in message for err in ACCESS_DENIED_STRINGS) else RESULT_ERROR
        if exc_type in ("ClientException", "ServerException") and (
            not normalized_message
            or normalized_message in ("ClientException()", "ServerException()")
            or exc_repr in ("ClientException()", "ServerException()")
        ):
            result_type = RESULT_NOTHING
        if any(err in message for err in NOT_AVAILABLE_STRINGS):
            result_type = RESULT_NOTHING
        # For exceptions that we treat as "no resources" (e.g. generic Client/Server exceptions
        # or region/product not available), return RESULT_NOTHING without exposing the raw
        # exception text in the final printed tuple. For real errors or access-denied cases
        # keep the exception repr so debugging information remains available.
        if result_type == RESULT_NOTHING:
            last_field = operation.resource_type
        else:
            last_field = repr(exc)
        return {
            "result": (result_type, service, region_label, operation.name, profile.get('name'), last_field),
            "listing": None,
            "service": service,
            "region_label": region_label,
            "operation_name": operation.name,
        }


def do_list_files(filenames, verbose=0):
    for listing_filename in filenames:
        listing = AliyunListing.from_json(json.load(open(listing_filename, 'rb')))
        resources = listing.resources
        for resource_type, value in resources.items():
            print(listing.service, listing.region, listing.operation, resource_type, str(len(value)))
            if verbose > 0:
                for item in value:
                    if isinstance(item, dict):
                        id_key = None
                        for guess in [
                            'Id',
                            'ID',
                            'id',
                            'InstanceId',
                            'ResourceId',
                            'Name',
                        ]:
                            if guess in item:
                                id_key = guess
                                break
                        if id_key:
                            print('    - ', item.get(id_key))
                        else:
                            print('    - ', item)
                    else:
                        print('    - ', item)
