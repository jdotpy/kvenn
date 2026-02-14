kvenn
=========

CLI Tool for doing set-operations on lines of input. Each line is treated as an item in a set. Each input is treated as a set.

## Usage


    usage: kvenn [-h] [-n] [-s] [-x] [--force-string-keys] [-f FORMAT]
                 [-o {+,-,x,d,union,difference,intersection,unique}]
                 sets [sets ...]

    positional arguments:
      sets                  Each file is a set and each line in the file is a
                            member of the set

    optional arguments:
      -h, --help            show this help message and exit
      -n, --non-empty       non-empty values only
      -s, --strip           strip surrounding whitespace
      -x, --filter          strip and filter to non-empty
      --force-string-keys   JSON set keys should be forced to a string type
      -f, --format FORMAT   Output handler (csv,json/ndjson,text)
                            default=whatever your first input was
      -o {+,-,x,d,union,difference,intersection,unique,stats}, --operation {+,-,x,d,union,difference,intersection,unique,stats}
                            Operation to perform on the sets [-] Subtract sets
                            1...N from set 0 [+] Get the union of sets 0...N [x]
                            Get the intersection of sets 0...N [d] Symmetric
                            difference (disjunctive union). Elements from all sets
                            which are not in any others. [stats] Print a summary
                            of all operations and per-source breakdowns.


## Input Formats

kvenn supports three input formats. The format is detected from the file extension.

### Plain text

Each line is treated as a set member. No special syntax needed.

    kvenn file1.txt file2.txt

### CSV

Use `::` to specify which column(s) to use as the set key:

    kvenn data1.csv::color data2.csv::color

Multiple key columns are supported:

    kvenn data1.csv::id,color data2.csv::id,color

### NDJSON (newline-delimited JSON)

Works the same as CSV — use `::` to specify the key field(s):

    kvenn data1.json::id data2.json::id

Nested keys use dot notation:

    kvenn data1.json::meta.id data2.json::meta.id

Files with `.json` or `.ndjson` extensions are both supported.

### Output format

By default the output format matches the first input file. Override with `-f`:

    kvenn data1.csv::color data2.csv::color -f json


## Examples


Unique values in a file

    kvenn <input>

Unique values in two or more files (Also `--operation union`)

    kvenn <input1> <input2> <inputN>


Values found in both files

    kvenn <input1> <input2> --operation intersection


Values found in only one file

    kvenn <input1> <input2> <inputN> --operation unique


Subtract values in B (and C, D.. etc) from A. (Unique values from A)

    kvenn <inputA> <inputB> [<inputC>] --operation difference


Get a summary of all set operations at once

    kvenn data_1.txt data_2.txt --operation stats

    All (2 sources, 17 total unique items):
      Union:                       17    (e.g. Purple)
      Intersection:                 3    (e.g. Purple)
      Difference (A - B):           7    (e.g. Teal)
      Symmetric difference:        14    (e.g. Teal)

    Source 1 - data_1.txt:
      Total:        10
      Unique:        7    (e.g. Teal)

    Source 2 - data_2.txt:
      Total:        10
      Unique:        7    (e.g. Pink)


## Development

    make install-dev
    make test
