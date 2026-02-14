import json
import csv
import sys

from . import utils

class TextHandler():
    @classmethod
    def output(cls, f, values, **output_options):
        for value in values:
            f.write(str(value) + '\n')

    def __init__(self, f, should_strip=False, should_drop_empty=False, **kwargs):
        self.strip = should_strip
        self.non_empty = should_drop_empty
        self.f = f

    def read(self):
        s = set()
        for line in self.f.read().splitlines():
            if self.strip:
                line = line.strip()
            if self.non_empty and line == '':
                continue
            s.add(line)
        return s, {'value'}


class NDJsonHandler():
    @classmethod
    def parse_key(cls, text):
        segments = text.split('.')
        return segments

    @classmethod
    def output(cls, f, values, **output_options):
        for value in values:
            if type(value) == str:
                value = {'value': value}
            f.write(json.dumps(value) + '\n')

    def __init__(self, f, keys=None, force_string_keys=False, **kwargs):
        self.f = f
        self.keys = [NDJsonHandler.parse_key(key) for key in keys]
        self.force_string_keys = force_string_keys

    def extract_key(self, obj, keys):
        key_values = []
        key_failed = False
        for key in keys:
            o = obj
            for segment in key:
                if type(o) == dict:
                    o = o.get(segment)
                else:
                    o = None
                    break
            key_value = o
            if key_value is None:
                key_failed = True
            if self.force_string_keys:
                key_value = str(key_value)
            key_values.append(key_value)
        if len(key_values) == 1:
            return key_values[0], key_failed
        else:
            return tuple(key_values), key_failed

    def read(self):
        values = {}
        all_keys = set()
        num_keys_failed = 0
        count = 0
        for line in self.f.read().splitlines():
            entry = json.loads(line)
            key, key_failed = self.extract_key(entry, self.keys)
            values[key] = entry
            utils.consume_iter(map(lambda x: all_keys.add(x), entry.keys()))
            count += 1
            if key_failed:
                num_keys_failed += 1
        if num_keys_failed > 0 and num_keys_failed == count:
            sys.stderr.write('All key lookups failed for key={}; results may not match expected value'.format(str(self.keys)))
        return values, {'value'}


class CSVHandler():
    def __init__(self, f, keys=None, **kwargs):
        self.f = f
        self.keys = keys

    @classmethod
    def output(cls, f, values, fields=None, **output_options):
        if fields is None:
            fields = ['value']
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for value in values:
            if type(value) == str:
                value = {'value': value}
            writer.writerow(value)

    @classmethod
    def extract_key(cls, obj, keys, default=None):
        key_values = []
        key_failed = False
        for key in keys:
            key_value = obj.get(key, default)
            if key_value is None:
                key_failed = True
            key_values.append(key_value)
        if len(key_values) == 1:
            return key_values[0], key_failed
        else:
            return tuple(key_values), key_failed

    def read(self):
        values = {}
        reader = csv.DictReader(self.f)
        count = 0
        num_keys_failed = 0
        for entry in reader:
            key, key_failed = CSVHandler.extract_key(entry, self.keys)
            values[key] = entry

            count += 1
            if key_failed:
                num_keys_failed += 1

        if num_keys_failed > 0 and num_keys_failed == count:
            sys.stderr.write('All key lookups failed for key={}; results may not match expected value'.format(str(self.keys)))
        return values, reader.fieldnames
    