import csv, io
import pandas as pd

root = '../data'

def read_mm():
    # fix the 3 movies that the default reader wrongfully splits into 6 lines
    with open(root + '/movies_metadata.csv', encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))

    # merge records that were split by a line break in overview
    fixed = [rows[0]]
    bad_rows = 0 
    for row in rows[1:]:
        if len(fixed[-1]) < len(rows[0]):          # previous row is incomplete
            first_half = fixed.pop()
            row = first_half[:-1] + [first_half[-1] + ' ' + row[0].strip()] + row[1:]
            bad_rows += 1
        fixed.append(row)

    # let pandas read the repaired data
    buf = io.StringIO()
    csv.writer(buf).writerows(fixed)
    buf.seek(0)

    mm = pd.read_csv(buf)
    
    print(f"There were {bad_rows} movies that were split and needed to be fixed")
    
    return mm