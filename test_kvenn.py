import io
import os
import sys
import json
import pytest
from unittest.mock import patch

from kvenn import core
from kvenn import file_handlers

EXAMPLE_DIR = os.path.join(os.path.dirname(__file__), 'example_data')


# --- extract_source_name_parts ---

class TestExtractSourceNameParts:
    def test_plain_text_file(self):
        parts = core.extract_source_name_parts('data.txt')
        assert parts['file_path'] == 'data.txt'
        assert parts['extension'] == 'txt'
        assert parts['path_no_extension'] == 'data'
        assert 'fields' not in parts

    def test_csv_with_fields(self):
        parts = core.extract_source_name_parts('data.csv::name,age')
        assert parts['file_path'] == 'data.csv'
        assert parts['extension'] == 'csv'
        assert parts['fields'] == ['name', 'age']

    def test_json_with_single_field(self):
        parts = core.extract_source_name_parts('data.json::id')
        assert parts['file_path'] == 'data.json'
        assert parts['extension'] == 'json'
        assert parts['fields'] == ['id']

    def test_no_extension(self):
        parts = core.extract_source_name_parts('myfile')
        assert parts['file_path'] == 'myfile'
        assert parts['path_no_extension'] == 'myfile'
        assert 'extension' not in parts

    def test_stdin_marker(self):
        parts = core.extract_source_name_parts('-')
        assert parts['path_no_extension'] == '-'

        parts = core.extract_source_name_parts('-.csv')
        assert parts['path_no_extension'] == '-'
        assert parts['extension'] == 'csv'

    def test_path_with_directory(self):
        parts = core.extract_source_name_parts('/tmp/foo/bar.csv::color')
        assert parts['file_path'] == '/tmp/foo/bar.csv'
        assert parts['extension'] == 'csv'
        assert parts['fields'] == ['color']


# --- TextHandler ---

class TestTextHandler:
    def test_read_basic(self):
        f = io.StringIO("alpha\nbeta\ngamma\n")
        handler = file_handlers.TextHandler(f)
        result, fields = handler.read()
        assert result == {'alpha', 'beta', 'gamma'}

    def test_read_with_strip(self):
        f = io.StringIO("  alpha \n beta\n")
        handler = file_handlers.TextHandler(f, should_strip=True)
        result, _ = handler.read()
        assert result == {'alpha', 'beta'}

    def test_read_drop_empty(self):
        f = io.StringIO("alpha\n\nbeta\n\n")
        handler = file_handlers.TextHandler(f, should_drop_empty=True)
        result, _ = handler.read()
        assert result == {'alpha', 'beta'}

    def test_read_deduplicates(self):
        f = io.StringIO("a\nb\na\nc\nb\n")
        handler = file_handlers.TextHandler(f)
        result, _ = handler.read()
        assert result == {'a', 'b', 'c'}

    def test_output(self):
        out = io.StringIO()
        file_handlers.TextHandler.output(out, ['x', 'y'])
        assert out.getvalue() == "x\ny\n"


# --- CSVHandler ---

class TestCSVHandler:
    def _make_handler(self, text, keys):
        return file_handlers.CSVHandler(io.StringIO(text), keys=keys)

    def test_read_single_key(self):
        text = "id,name\n1,Alice\n2,Bob\n"
        handler = self._make_handler(text, keys=['name'])
        result, fields = handler.read()
        assert 'Alice' in result
        assert 'Bob' in result
        assert result['Alice'] == {'id': '1', 'name': 'Alice'}

    def test_read_composite_key(self):
        text = "id,name\n1,Alice\n2,Bob\n"
        handler = self._make_handler(text, keys=['id', 'name'])
        result, fields = handler.read()
        assert ('1', 'Alice') in result

    def test_extract_key_single(self):
        obj = {'color': 'Red', 'id': '1'}
        assert file_handlers.CSVHandler.extract_key(obj, ['color']) == 'Red'

    def test_extract_key_multi(self):
        obj = {'a': '1', 'b': '2'}
        assert file_handlers.CSVHandler.extract_key(obj, ['a', 'b']) == ('1', '2')

    def test_extract_key_missing(self):
        obj = {'a': '1'}
        assert file_handlers.CSVHandler.extract_key(obj, ['missing']) is None


# --- NDJsonHandler ---

class TestNDJsonHandler:
    def _make_handler(self, lines, keys):
        text = '\n'.join(json.dumps(l) for l in lines)
        return file_handlers.NDJsonHandler(io.StringIO(text), keys=keys)

    def test_read_single_key(self):
        lines = [{'id': 1, 'name': 'a'}, {'id': 2, 'name': 'b'}]
        handler = self._make_handler(lines, keys=['id'])
        result, _ = handler.read()
        assert 1 in result
        assert 2 in result

    def test_read_nested_key(self):
        lines = [{'meta': {'id': 10}, 'val': 'x'}]
        handler = self._make_handler(lines, keys=['meta.id'])
        result, _ = handler.read()
        assert 10 in result

    def test_parse_key(self):
        assert file_handlers.NDJsonHandler.parse_key('a.b.c') == ['a', 'b', 'c']
        assert file_handlers.NDJsonHandler.parse_key('simple') == ['simple']

    def test_force_string_keys(self):
        lines = [{'id': 1, 'v': 'x'}]
        handler = file_handlers.NDJsonHandler(
            io.StringIO(json.dumps(lines[0])),
            keys=['id'],
            force_string_keys=True,
        )
        result, _ = handler.read()
        assert '1' in result


# --- MultiMap ---

class TestMultiMap:
    def test_get_from_first_map(self):
        mm = core.MultiMap({'a': 1}, {'a': 2})
        assert mm.get('a') == 1

    def test_get_from_second_map(self):
        mm = core.MultiMap({'a': 1}, {'b': 2})
        assert mm.get('b') == 2

    def test_get_missing_returns_key(self):
        mm = core.MultiMap({'a': 1})
        assert mm.get('missing') == 'missing'

    def test_add(self):
        mm = core.MultiMap()
        mm.add({'x': 10})
        assert mm.get('x') == 10

    def test_get_iter_for_keys(self):
        mm = core.MultiMap({'a': 1, 'b': 2})
        assert list(mm.get_iter_for_keys(['a', 'b'])) == [1, 2]

    def test_get_iter_for_keys_missing(self):
        mm = core.MultiMap()
        assert list(mm.get_iter_for_keys(['z'])) == ['z']


# --- Set operations via load_source + real files ---

class TestSetOperationsText:
    """Integration tests using example_data text files."""

    def _run(self, sources, operation):
        handler_options = {
            'should_strip': False,
            'should_drop_empty': False,
            'force_string_keys': False,
        }
        result, _, _, _, _ = core.compute(sources, operation, handler_options)
        return sorted(list(result))

    def test_union(self):
        s1 = os.path.join(EXAMPLE_DIR, 'data_1.txt')
        s2 = os.path.join(EXAMPLE_DIR, 'data_2.txt')
        result = self._run([s1, s2], '+')
        # Union should contain all unique values from both files
        assert 'Purple' in result
        assert 'Pink' in result  # only in data_2
        assert 'Coral' in result  # only in data_1
        assert len(result) == len(set(result))  # no duplicates

    def test_intersection(self):
        s1 = os.path.join(EXAMPLE_DIR, 'data_1.txt')
        s2 = os.path.join(EXAMPLE_DIR, 'data_2.txt')
        result = self._run([s1, s2], 'x')
        # Items in both: Purple, Orange, Red
        assert set(result) == {'Orange', 'Purple', 'Red'}

    def test_difference(self):
        s1 = os.path.join(EXAMPLE_DIR, 'data_1.txt')
        s2 = os.path.join(EXAMPLE_DIR, 'data_2.txt')
        result = self._run([s1, s2], '-')
        # data_1 minus data_2: items only in data_1
        for item in result:
            assert item not in {'Purple', 'Orange', 'Red'}
        assert 'Coral' in result
        assert 'Teal' in result

    def test_symmetric_difference(self):
        s1 = os.path.join(EXAMPLE_DIR, 'data_1.txt')
        s2 = os.path.join(EXAMPLE_DIR, 'data_2.txt')
        result = self._run([s1, s2], 'd')
        # Symmetric diff: items in one but not both
        common = {'Purple', 'Orange', 'Red'}
        for item in result:
            assert item not in common
        assert 'Coral' in result  # only in data_1
        assert 'Pink' in result   # only in data_2


class TestSetOperationsCSV:
    """Integration tests using example CSV files with field keys."""

    def test_csv_intersection_on_color(self):
        s1 = os.path.join(EXAMPLE_DIR, 'data_1.csv::color')
        s2 = os.path.join(EXAMPLE_DIR, 'data_2.csv::color')
        handler_options = {
            'should_strip': False,
            'should_drop_empty': False,
            'force_string_keys': False,
        }
        result, _, _, _, _ = core.compute([s1, s2], 'x', handler_options)
        # Green, Yellow, Purple are in both CSVs
        assert 'Green' in result
        assert 'Yellow' in result
        assert 'Purple' in result


class TestSetOperationsJSON:
    """Integration tests using example NDJSON files."""

    def test_json_intersection_on_color(self):
        s1 = os.path.join(EXAMPLE_DIR, 'data_1.json::color')
        s2 = os.path.join(EXAMPLE_DIR, 'data_2.json::color')
        handler_options = {
            'should_strip': False,
            'should_drop_empty': False,
            'force_string_keys': False,
        }
        result, _, _, _, _ = core.compute([s1, s2], 'x', handler_options)
        # Red and Teal appear in both JSON files
        assert 'Red' in result
        assert 'Teal' in result


# --- load_source ---

DEFAULT_HANDLER_OPTIONS = {
    'should_strip': False,
    'should_drop_empty': False,
    'force_string_keys': False,
}

class TestLoadSource:
    def test_text_file(self):
        fake = io.StringIO("a\nb\n")
        with patch('builtins.open', return_value=fake):
            handler = core.load_source('data.txt', DEFAULT_HANDLER_OPTIONS)
        assert isinstance(handler, file_handlers.TextHandler)

    def test_csv_with_fields(self):
        fake = io.StringIO("id,name\n1,Alice\n")
        with patch('builtins.open', return_value=fake):
            handler = core.load_source('data.csv::name', DEFAULT_HANDLER_OPTIONS)
        assert isinstance(handler, file_handlers.CSVHandler)

    def test_csv_without_fields_falls_back_to_text(self):
        fake = io.StringIO("id,name\n1,Alice\n")
        with patch('builtins.open', return_value=fake):
            handler = core.load_source('data.csv', DEFAULT_HANDLER_OPTIONS)
        assert isinstance(handler, file_handlers.TextHandler)

    def test_json_with_fields(self):
        fake = io.StringIO('{"id": 1}\n')
        with patch('builtins.open', return_value=fake):
            handler = core.load_source('data.json::id', DEFAULT_HANDLER_OPTIONS)
        assert isinstance(handler, file_handlers.NDJsonHandler)

    def test_ndjson_with_fields(self):
        fake = io.StringIO('{"id": 1}\n')
        with patch('builtins.open', return_value=fake):
            handler = core.load_source('data.ndjson::id', DEFAULT_HANDLER_OPTIONS)
        assert isinstance(handler, file_handlers.NDJsonHandler)

    def test_json_without_fields_falls_back_to_text(self):
        fake = io.StringIO('{"id": 1}\n')
        with patch('builtins.open', return_value=fake):
            handler = core.load_source('data.json', DEFAULT_HANDLER_OPTIONS)
        assert isinstance(handler, file_handlers.TextHandler)

    def test_no_extension_returns_text(self):
        fake = io.StringIO("line\n")
        with patch('builtins.open', return_value=fake):
            handler = core.load_source('myfile', DEFAULT_HANDLER_OPTIONS)
        assert isinstance(handler, file_handlers.TextHandler)

    def test_stdin_source(self):
        fake_stdin = io.StringIO("a\nb\n")
        with patch.object(sys, 'stdin', fake_stdin):
            handler = core.load_source('-', DEFAULT_HANDLER_OPTIONS)
        assert isinstance(handler, file_handlers.TextHandler)


# --- Output methods ---

class TestCSVHandlerOutput:
    def test_output_with_dicts(self):
        out = io.StringIO()
        file_handlers.CSVHandler.output(out, [
            {'name': 'Alice', 'age': '30'},
            {'name': 'Bob', 'age': '25'},
        ], fields=['name', 'age'])
        assert out.getvalue() == "name,age\r\nAlice,30\r\nBob,25\r\n"

    def test_output_wraps_plain_strings(self):
        out = io.StringIO()
        file_handlers.CSVHandler.output(out, ['hello'])
        assert out.getvalue() == "value\r\nhello\r\n"

    def test_output_default_fields(self):
        out = io.StringIO()
        file_handlers.CSVHandler.output(out, [{'value': 'x'}])
        lines = out.getvalue().splitlines()
        assert lines[0] == 'value'


class TestNDJsonHandlerOutput:
    def test_output_with_dicts(self):
        out = io.StringIO()
        file_handlers.NDJsonHandler.output(out, [
            {'id': 1, 'name': 'Alice'},
        ])
        assert json.loads(out.getvalue().strip()) == {'id': 1, 'name': 'Alice'}

    def test_output_wraps_plain_strings(self):
        out = io.StringIO()
        file_handlers.NDJsonHandler.output(out, ['hello'])
        assert json.loads(out.getvalue().strip()) == {'value': 'hello'}


# --- compute error path and structured-data operations ---

class TestComputeErrors:
    def test_unsupported_operation_raises(self):
        fake = io.StringIO("a\nb\n")
        with patch('builtins.open', return_value=fake):
            with pytest.raises(ValueError, match='Unsupported operation'):
                core.compute(['data.txt'], 'bogus', DEFAULT_HANDLER_OPTIONS)


class TestComputeStructuredData:
    """Test compute with CSV/JSON sources across all operations."""

    CSV_1 = "color,id\nRed,1\nGreen,2\nBlue,3\n"
    CSV_2 = "color,id\nGreen,2\nBlue,3\nYellow,4\n"

    def _run_csv(self, operation):
        f1 = io.StringIO(self.CSV_1)
        f2 = io.StringIO(self.CSV_2)
        with patch('builtins.open', side_effect=[f1, f2]):
            result, mm, _, _, _ = core.compute(
                ['a.csv::color', 'b.csv::color'], operation, DEFAULT_HANDLER_OPTIONS
            )
        return result, mm

    def test_csv_union(self):
        result, mm = self._run_csv('+')
        assert result == {'Red', 'Green', 'Blue', 'Yellow'}
        assert mm.get('Green')['id'] == '2'

    def test_csv_difference(self):
        result, _ = self._run_csv('-')
        assert result == {'Red'}

    def test_csv_intersection(self):
        result, _ = self._run_csv('x')
        assert result == {'Green', 'Blue'}

    def test_csv_symmetric_difference(self):
        result, _ = self._run_csv('d')
        assert result == {'Red', 'Yellow'}

    JSON_1 = '\n'.join([json.dumps(r) for r in [
        {'color': 'Red', 'v': 1},
        {'color': 'Green', 'v': 2},
    ]])
    JSON_2 = '\n'.join([json.dumps(r) for r in [
        {'color': 'Green', 'v': 2},
        {'color': 'Blue', 'v': 3},
    ]])

    def _run_json(self, operation):
        f1 = io.StringIO(self.JSON_1)
        f2 = io.StringIO(self.JSON_2)
        with patch('builtins.open', side_effect=[f1, f2]):
            result, mm, _, _, _ = core.compute(
                ['a.json::color', 'b.json::color'], operation, DEFAULT_HANDLER_OPTIONS
            )
        return result, mm

    def test_json_union(self):
        result, _ = self._run_json('+')
        assert result == {'Red', 'Green', 'Blue'}

    def test_json_difference(self):
        result, _ = self._run_json('-')
        assert result == {'Red'}

    def test_json_intersection(self):
        result, _ = self._run_json('x')
        assert result == {'Green'}

    def test_json_symmetric_difference(self):
        result, _ = self._run_json('d')
        assert result == {'Red', 'Blue'}


# --- Cross-format and multi-source ---

class TestCrossFormat:
    def test_intersection_csv_and_json(self):
        csv_data = io.StringIO("color,id\nRed,1\nGreen,2\nBlue,3\n")
        json_data = io.StringIO('\n'.join([
            json.dumps({'color': 'Green', 'v': 10}),
            json.dumps({'color': 'Blue', 'v': 20}),
            json.dumps({'color': 'Yellow', 'v': 30}),
        ]))
        with patch('builtins.open', side_effect=[csv_data, json_data]):
            result, _, _, _, _ = core.compute(
                ['a.csv::color', 'b.json::color'], 'x', DEFAULT_HANDLER_OPTIONS
            )
        assert result == {'Green', 'Blue'}


class TestThreeSources:
    def test_intersection_across_three_files(self):
        f1 = io.StringIO("Red\nGreen\nBlue\n")
        f2 = io.StringIO("Green\nBlue\nYellow\n")
        f3 = io.StringIO("Blue\nYellow\nPurple\n")
        with patch('builtins.open', side_effect=[f1, f2, f3]):
            result, _, _, _, _ = core.compute(
                ['a.txt', 'b.txt', 'c.txt'], 'x', DEFAULT_HANDLER_OPTIONS
            )
        # Blue is the only value present in all three
        assert result == {'Blue'}

    def test_union_across_three_files(self):
        f1 = io.StringIO("Red\nGreen\n")
        f2 = io.StringIO("Green\nBlue\n")
        f3 = io.StringIO("Blue\nYellow\n")
        with patch('builtins.open', side_effect=[f1, f2, f3]):
            result, _, _, _, _ = core.compute(
                ['a.txt', 'b.txt', 'c.txt'], '+', DEFAULT_HANDLER_OPTIONS
            )
        assert result == {'Red', 'Green', 'Blue', 'Yellow'}


# --- OPERATIONS lookup ---

class TestOperationsMapping:
    def test_all_aliases_resolve(self):
        assert core.OPERATIONS['+'] == core.OP_UNION
        assert core.OPERATIONS['u'] == core.OP_UNION
        assert core.OPERATIONS['union'] == core.OP_UNION
        assert core.OPERATIONS['-'] == core.OP_DIFFERENCE
        assert core.OPERATIONS['difference'] == core.OP_DIFFERENCE
        assert core.OPERATIONS['x'] == core.OP_INTERSECTION
        assert core.OPERATIONS['d'] == core.OP_SYM_DIFF
        assert core.OPERATIONS['unique'] == core.OP_SYM_DIFF
        assert core.OPERATIONS['distinct'] == core.OP_SYM_DIFF
