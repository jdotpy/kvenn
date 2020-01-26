kvenn
=========

CLI Tool for doing set-operations on lines of input. Each line is treated as an item in a set. Each input is treated as a set.

## Usage

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

