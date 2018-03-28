#!/usr/bin/env python

import os
import json
import copy
import argparse

from jq import jq
import jsonschema
import requests


DEFAULT_RPC_URL = 'http://127.0.0.1:1337'


class FixResolver(jsonschema.RefResolver):
    def __init__(self, schema_data, schema_path):
        super(FixResolver, self).__init__(
            base_uri=schema_path,
            referrer=None
        )
        self.store[schema_path] = schema_data


class TestRunner(object):

    def __init__(self, directory, rpc_url):
        directory = directory or ''
        self.directory = directory
        self.tests_dir = os.path.join(directory, 'tests')
        self.rpc_url = rpc_url
        self.session = requests.Session()

    def run_all(self):
        for filename in os.listdir(self.tests_dir):
            test_path = os.path.join(self.tests_dir, filename)
            self.run_method(test_path)

    def run_method(self, test_path):
        with open(test_path) as f:
            test_data = json.load(f)

        tests_dir = os.path.dirname(test_path)
        print('Test Method: {}'.format(test_data['title']))
        schema_path = os.path.join(tests_dir, test_data['schema']['$ref'])
        with open(schema_path) as f:
            schema_data = json.load(f)

        for test_case in test_data['tests']:
            self.run_test_case(
                test_case,
                schema_data['request'],
                schema_data['response'],
                schema_path,
            )

    def run_test_case(
            self,
            test_case,
            request_schema,
            response_schema,
            schema_path
    ):
        print('Test Case: {}'.format(test_case['title']))
        schema_base_uri = 'file://{}/'.format(
            os.path.dirname(os.path.abspath(schema_path))
        )
        request_payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': test_case['request']['method'],
            'params': test_case['request']['params'],
        }
        request_resolver = FixResolver(request_schema, schema_base_uri)
        jsonschema.validate(
            request_payload,
            request_schema,
            resolver=request_resolver,
        )

        expected_response = copy.deepcopy(test_case['expectedResponse'])
        expected_response['jsonrpc'] = "2.0"
        expected_response['id'] = 1
        response_resolver = FixResolver(response_schema, schema_base_uri)
        jsonschema.validate(
            expected_response,
            response_schema,
            resolver=response_resolver,
        )

        resp = self.session.post(self.rpc_url, json=request_payload)
        assert_data = {
            'receivedResponse': resp.json(),
            'expectedResponse': expected_response
        }
        for assertion in test_case['asserts']:
            assertion_result = jq(assertion['program']).transform(
                assert_data
            )
            print("{} : {}".format(
                assertion['description'],
                assertion_result
            ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--rpc-url',
        default=DEFAULT_RPC_URL,
        help=u'JSONRPC server URL [default: {}]'.format(DEFAULT_RPC_URL)
    )
    parser.add_argument(
        '--directory',
        help='The tests/schemas directory (run all methods)'
    )
    parser.add_argument(
        '--tests',
        nargs='*',
        help=u'The test file path list'
    )
    args = parser.parse_args()

    runner = TestRunner(args.directory, args.rpc_url)
    if args.tests:
        for test_path in args.tests:
            runner.run_method(test_path)
    else:
        runner.run_all()


if __name__ == '__main__':
    main()
