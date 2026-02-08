#!/usr/bin/env python
from __future__ import print_function

from argparse import ArgumentParser

from .introspection import get_regions_for_service
from .operations import get_operations, get_services
from .report import write_report
from .query import do_list_files, do_query


def main():
    parser = ArgumentParser(
        prog='aliyun_list_all',
        description=(
            'List Aliyun resources across regions and services. '
            'Saves results into json files for later inspection.'
        )
    )
    subparsers = parser.add_subparsers(dest='command', metavar='COMMAND')

    query = subparsers.add_parser('query', description='Query Aliyun for resources', help='Query Aliyun for resources')
    query.add_argument('-s', '--service', action='append', help='Restrict querying to the given service')
    query.add_argument('-r', '--region', action='append', help='Restrict querying to the given region')
    query.add_argument('-o', '--operation', action='append', help='Restrict querying to the given operation')
    query.add_argument('-p', '--parallel', default=16, type=int, help='Number of requests to do in parallel')
    query.add_argument('-d', '--directory', default='.', help='Directory to save result listings to')
    query.add_argument('-v', '--verbose', action='count', help='Print detailed info during run')
    query.add_argument('-c', '--profile', help='Use a specific ~/.aliyun/config.json profile name')

    show = subparsers.add_parser('show', description='Show saved listings', help='Display saved listings')
    show.add_argument('listingfile', nargs='*', help='listing file(s) to load and print')
    show.add_argument('-v', '--verbose', action='count', help='print given listing files with detailed info')

    report = subparsers.add_parser('report', description='Build a report from saved listings', help='Report')
    report.add_argument('-d', '--directory', default='.', help='Directory to read listing json files from')
    report.add_argument('-f', '--format', default='html', choices=('text', 'json', 'csv', 'html'), help='Output format')
    report.add_argument('-o', '--output', help='Write report to a file instead of stdout')

    introspect = subparsers.add_parser(
        'introspect',
        description='Print introspection debugging information',
        help='Print introspection debugging information'
    )
    introspecters = introspect.add_subparsers(dest='introspect', metavar='DETAIL')

    introspecters.add_parser('list-services', description='List available Aliyun services')
    ops = introspecters.add_parser('list-operations', description='List operations for services')
    ops.add_argument('-s', '--service', action='append', help='Only list operations for the given service')
    regs = introspecters.add_parser('list-service-regions', description='List regions for services')
    regs.add_argument('-s', '--service', action='append', help='Only list regions for the given service')

    args = parser.parse_args()

    if args.command == 'query':
        if args.directory:
            import os
            try:
                os.makedirs(args.directory)
            except OSError:
                pass
            os.chdir(args.directory)
        services = args.service or get_services()
        do_query(
            services,
            selected_regions=args.region or (),
            selected_operations=args.operation or (),
            verbose=args.verbose or 0,
            parallel=args.parallel,
            profile_name=args.profile,
        )
    elif args.command == 'show':
        if args.listingfile:
            do_list_files(args.listingfile, verbose=args.verbose or 0)
        else:
            show.print_help()
            return 1
    elif args.command == 'report':
        write_report(args.directory, report_format=args.format, output=args.output)
    elif args.command == 'introspect':
        if args.introspect == 'list-services':
            for service in get_services():
                print(service)
        elif args.introspect == 'list-operations':
            for service in args.service or get_services():
                for operation in get_operations(service):
                    print(service, operation.name)
        elif args.introspect == 'list-service-regions':
            for service in args.service or get_services():
                for region in get_regions_for_service(service):
                    print(service, region)
        else:
            introspect.print_help()
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
