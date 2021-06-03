import numpy as np

def solveLinearCut(data, capacity):
    res = {}
    ignore = []
    while len(data) != len(ignore):
        for j in range(len(data)):
            if len(data) == len(ignore):
                break
            res[j] = {}
            res[j]['used'] = 0
            res[j]['chute'] = 0
            for i in range(len(data)):
                if i not in ignore:
                    if res[j]['used'] + data[i] + 30 < capacity:
                        res[j]['used'] += data[i] + 30
                        res[j]['chute'] = capacity - res[j]['used']
                        ignore.append(i)
    return len(res)

def formatData(raw_data):
    data = []
    for i,j in raw_data:
        for _ in range(int(j)):
            data.append(i)
    return data

def optimise(raw_data, capacity):
    data = formatData(raw_data)
    return solveLinearCut(data,capacity)

def sum(raw_data):
   data = np.array(raw_data, dtype='float32')
   return np.sum(data)
