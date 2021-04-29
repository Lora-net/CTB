import argparse
import json

parser = argparse.ArgumentParser(description='convert csv file to json file')
parser.add_argument('-i', '--input', metavar='input', help='Specify input csv file name')
parser.add_argument('-o', '--output', metavar='output', help='Specify output json file name')

args, rem = parser.parse_known_args()
    
tables = {}
with open(args.input) as f:
    lines = f.readlines()
    for line in lines:
        tmp = line.strip('\n').split(',', 3)
        if tmp[0]:
            if tmp[0] not in tables:
                tables[tmp[0]] = {}
            if not tmp[3]:
                continue
            if tmp[2] in ['INTEGER', 'BOOLEAN']:
                tables[tmp[0]][tmp[1]] = int(tmp[3])
            elif tmp[2] == "REAL":
                tables[tmp[0]][tmp[1]] = float(tmp[3])
            else:
                if tmp[3].count('"') == 2:
                    try:
                        tmp[3] = eval(tmp[3])
                    except:
                        pass
                tables[tmp[0]][tmp[1]] = tmp[3]

with open(args.output, 'w') as fp:
    json.dump(tables, fp)