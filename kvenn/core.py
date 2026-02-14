#!/usr/bin/env python3

import argparse
import sys

from . import file_handlers
from . import utils

OP_DIFFERENCE = '-'
OP_UNION = '+'
OP_INTERSECTION = 'x'
OP_SYM_DIFF = 'd'

OPERATIONS = {
    OP_DIFFERENCE: OP_DIFFERENCE,
    'difference': OP_DIFFERENCE,
    
    OP_UNION: OP_UNION,
    '+': OP_UNION,
    'u': OP_UNION,
    'union': OP_UNION,

    OP_INTERSECTION: OP_INTERSECTION,
    'x': OP_INTERSECTION,
    'intersection': OP_INTERSECTION,

    OP_SYM_DIFF: OP_SYM_DIFF,
    'unique': OP_SYM_DIFF,
    'distinct': OP_SYM_DIFF,
}

def extract_source_name_parts(source_name):
    parts = {}
    rest_of_source = source_name
    if '::' in rest_of_source:
        rest_of_source, qualifier = rest_of_source.rsplit('::', 1)
        parts['fields'] = qualifier.split(',')
    
    parts['file_path'] = rest_of_source

    if '.' in rest_of_source:
        rest_of_source, extension = rest_of_source.rsplit('.', 1)
        parts['extension'] = extension
        parts['path_no_extension'] = rest_of_source
    else:
        parts['path_no_extension'] = rest_of_source
    
    return parts

def load_source(source, handler_options):
    source_parts = extract_source_name_parts(source)

    # Get the file object
    if source_parts['path_no_extension'] == '-':
        f = sys.stdin
    else:
        f = open(source_parts['file_path'], 'r')

    # Now determine the handler
    ext = source_parts.get('extension', None)
    fields = source_parts.get('fields', None)

    if ext == 'csv':
        if fields is None:
            sys.stderr.write('Warning: doing raw text comparison on a csv file that usually uses fields\n')
            return file_handlers.TextHandler(f)
        return file_handlers.CSVHandler(f, keys=fields, **handler_options)
    elif ext in ('json', 'ndjson'):
        if fields is None:
            sys.stderr.write('Warning: doing raw text comparison on a JSON file that usually uses fields\n')
            return file_handlers.TextHandler(f)
        return file_handlers.NDJsonHandler(f, keys=fields)
    return file_handlers.TextHandler(f)

class MultiMap():
    def __init__(self, *maps):
        self.maps = list(maps)

    def add(self, m):
        self.maps.append(m)

    def get(self, key):
        for m in self.maps:
            map_value = m.get(key)
            if map_value is not None:
                return map_value
        # if no value then the key itself must be the value
        return key

    def get_iter_for_keys(self, keys):
        for key in keys:
            value = self.get(key)
            yield value

def compute(sources, operation, handler_options):
    operation = OPERATIONS.get(operation, None)

    first_handler = None
    values_mm = MultiMap()
    fields_union = set()
    first_fields = None
    sets = []
    for source in sources:
        handler = load_source(source, handler_options)

        handler_result, handler_fields = handler.read()
        utils.consume_iter(map(lambda x: fields_union.add(x), handler_fields))

        if first_handler is None:
            first_handler = handler
            first_fields = handler_fields

        # Support two types of sources, set-based (with no value) and dict maps
        if type(handler_result) == set:
            sets.append(handler_result)
        else:
            key_set = set(handler_result.keys())
            values_mm.add(handler_result)
            sets.append(key_set)

    if operation == OP_DIFFERENCE:
        result = sets[0]
        result.difference_update(*sets[1:])
    elif operation == OP_UNION:
        result = sets[0]
        result.update(*sets[1:])
    elif operation == OP_INTERSECTION:
        result = sets[0]
        result.intersection_update(*sets[1:])
    elif operation == OP_SYM_DIFF:
        result = set()
        for index, primary in enumerate(sets):
            others = sets[0:index] + sets[index + 1:]
            difference = primary.copy()
            difference.difference_update(*others)
            result.update(difference)
    else:
        raise ValueError('Unsupported operation "{}"'.format(operation))

    return result, values_mm, first_handler, first_fields, fields_union

def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('sets', nargs="+", help='Each file is a set and each line in the file is a member of the set')
    parser.add_argument('-n', '--non-empty', action='store_true', default=False, help='non-empty values only')
    parser.add_argument('-s', '--strip', action='store_true', default=False, help='strip surrounding whitespace')
    parser.add_argument('-x', '--filter', action='store_true', default=False, help='strip and filter to non-empty')
    parser.add_argument('--force-string-keys', action='store_true', default=False, help='JSON set keys should be forced to a string type')
    parser.add_argument('-f', '--format', default=None, help='Output handler (csv,json/ndjson,text) default=whatever your first input was')
    parser.add_argument('-o', '--operation',
        choices=['+', '-', 'x', 'd', 'union', 'difference', 'intersection', 'unique'],
        default='+',
        help="""
            Operation to perform on the sets
            [-] Subtract sets 1...N from set 0
            [+] Get the union of sets 0...N
            [x] Get the intersection of sets 0...N
            [d] Symmetric difference (disjunctive union). Elements from all sets which are not in any others.
        """
    )
    args = parser.parse_args()


    handler_options = {
        'should_strip': args.filter or args.strip,
        'should_drop_empty':  args.filter or args.non_empty,
        'force_string_keys': args.force_string_keys,
    }
    # Attempt to allow a user to explicitly set output format, setting it to text
    #  if there are other types doens't really work so we won't allow it. we'll
    #  also have to do some hacky behavior to support these with text input so...
    #  doubt we'll have a valid use-case but i'm throwing my future self a bone cause
    #  i always regret not making things configurable
    output_handler = None
    if args.format is not None:
        if args.format.lower() == 'csv':
            output_handler = file_handlers.CSVHandler
        elif args.format.lower() == 'json':
            output_handler = file_handlers.NDJsonHandler

    result, values_mm, first_handler, first_fields, fields_union = compute(
        args.sets, args.operation, handler_options
    )

    if output_handler is None:
        output_handler = first_handler

    operation = OPERATIONS.get(args.operation, None)
    try:
        sorted_result = sorted(list(result))
    except TypeError:
        # We were unable to sort due to comparing keys across types being invalid (probably a None)
        sorted_result = result
    if operation == OP_DIFFERENCE:
        output_fields = first_fields
    else:
        output_fields = fields_union
    output_handler.output(sys.stdout, values_mm.get_iter_for_keys(sorted_result), fields=output_fields)
