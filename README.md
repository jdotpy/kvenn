kvenn
=========

CLI Tool for doing set-operations on lines of input. Each line is treated as an item in a set. Each input is treated as a set.

## Usage

Help output:

    usage: kvenn [-h] [-n] [-s] [-f]
                 [-o {+,-,x,d,union,difference,intersection,unique}]
                 sets [sets ...]

    positional arguments:
      sets                  Each file is a set and each line in the file is a
                            member of the set

    optional arguments:
      -h, --help            show this help message and exit
      -n, --non-empty       non-empty values only
      -s, --strip           strip surrounding whitespace
      -f, --filter          strip and filter to non-empty
      -o {+,-,x,d,union,difference,intersection,unique}, --operation {+,-,x,d,union,difference,intersection,unique}
                            Operation to perform on the sets [-] Subtract sets
                            1...N from set 0 [+] Get the union of sets 0...N [x]
                            Get the intersection of sets 0...N [d] Symmetric
                            difference (disjunctive union). Elements from all sets
                            which are not in any others.

## Example

Unique values in a file

    kvenn <input>


Unique values in two or more files (Also `--union`)

    kvenn <input1> <input2> <inputN>


Values found in both files

    kvenn <input1> <input2> --operation intersection


Values found in only one file

    kvenn <input1> <input2> <inputN> --operation unique


Values found in only one file

    kvenn <input1> <input2> <inputN> --operation unique


Subtract values in B (and C, D.. etc) from A. (Unique values from A)

    kvenn <inputA> <inputB> [<inputC>] --operation subtract



